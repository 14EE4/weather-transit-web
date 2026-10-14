# -*- coding: utf-8 -*-
"""
feature_schema.py
================================================================================
`feature_schema.json` 로더 · 검증 모듈 — 피처 **차원·순서의 단일 진실 공급원(SSoT)**.

배경
----
학습(Colab `benchmarks/CastTransit.ipynb`), 평가(`benchmarks/evaluate_models.py`),
서빙(`main.py`)이 각자 피처 순서를 하드코딩하고 있어 드리프트 위험이 있었습니다.
실제로 v1 32차원 자산(25차원 + 상수 0 더미 7)을 v2 배치로 추론하면 인덱스 17 이후가
어긋나 예측이 붕괴합니다(실측 R² −0.59 / −0.93 / 0.19 — `docs/TODO.md` §4).

이 모듈은 스키마 파일을 읽어 **차원·순서·타깃·분할 경계를 assert** 하는 단일 경로를
제공합니다. 서빙은 기동 시, 평가 스크립트는 실행 시 검증하며, 불일치는 즉시 실패합니다.

스키마 탐색 순서 (`resolve_schema_path`)
    1. 명시 인자(`explicit`)           — `evaluate_models.py --schema`
    2. 환경변수 `FEATURE_SCHEMA_PATH`  — 컨테이너/배포 재정의용
    3. `models/feature_schema.json`    — 배포 슬롯(32차원 자산 교체 시 자연 승격)
    4. `benchmarks/2026-10-14/feature_schema.json` — 현행 v2 학습 산출물

사용
----
    from feature_schema import load_schema, validate_expected_order

    schema = load_schema()
    if schema:
        validate_expected_order(schema, FEATURE_ORDER_32, "main.py::FEATURE_ORDER_32")
================================================================================
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable, Optional, Sequence

BASE_DIR = Path(__file__).resolve().parent

SCHEMA_FILENAME = "feature_schema.json"
SCHEMA_ENV_VAR = "FEATURE_SCHEMA_PATH"

# 탐색 우선순위(위에서부터). 실제 사용 경로는 `resolve_schema_path()` 참조.
SCHEMA_CANDIDATES: tuple[Path, ...] = (
    BASE_DIR / "models" / SCHEMA_FILENAME,
    BASE_DIR / "benchmarks" / "2026-10-14" / SCHEMA_FILENAME,
)

# 25차원 레거시(배포본) 서브셋 인덱스 — v2 32차원 기준 위치.
# main.py::prepare_session_input 이 25차원 세션에 전달하는 인덱스와 동일하며,
# 32차원에서 [17..20](공간 인프라 4) + [27..29](same_day_last_week 3) 을 제외한 부분집합입니다.
LEGACY_25D_INDICES: tuple[int, ...] = tuple(range(17)) + (21, 22, 23, 24, 25, 26, 30, 31)

_SPLIT_RANGE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*[~-]\s*(\d{4}-\d{2}-\d{2})\s*$")


class FeatureSchemaError(ValueError):
    """`feature_schema.json` 부재·규격 위반 또는 코드와의 불일치."""


# --------------------------------------------------------------- 경로 · 로드
def resolve_schema_path(explicit: Optional[object] = None) -> Optional[Path]:
    """스키마 파일 경로를 결정한다(없으면 `None`).

    `explicit` 가 주어지면 그 경로를 최우선으로 사용하며, 파일이 없으면 예외를 던진다
    (사용자가 명시한 경로를 조용히 무시하지 않기 위함).
    """
    if explicit:
        path = Path(str(explicit)).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        if not path.is_file():
            raise FeatureSchemaError(f"지정한 피처 스키마 파일이 없습니다: {path}")
        return path

    env_path = os.getenv(SCHEMA_ENV_VAR)
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        if not path.is_file():
            raise FeatureSchemaError(
                f"{SCHEMA_ENV_VAR} 로 지정한 피처 스키마 파일이 없습니다: {path}"
            )
        return path

    for candidate in SCHEMA_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def load_schema(explicit: Optional[object] = None) -> Optional[dict]:
    """스키마 JSON 을 로드한다. 파일이 없으면 `None`, 규격 위반이면 `FeatureSchemaError`."""
    path = resolve_schema_path(explicit)
    if path is None:
        return None
    try:
        with path.open("r", encoding="utf-8") as fp:
            schema = json.load(fp)
    except json.JSONDecodeError as exc:  # 손상된 스키마는 즉시 실패
        raise FeatureSchemaError(f"피처 스키마 JSON 파싱 실패({path}): {exc}") from exc
    if not isinstance(schema, dict):
        raise FeatureSchemaError(f"피처 스키마 최상위가 객체(dict)가 아닙니다: {path}")
    return schema


# ------------------------------------------------------------------- 검증
def schema_feature_cols(schema: dict) -> list[str]:
    """스키마의 피처 순서를 검증 후 반환한다(차원·중복 검사 포함)."""
    if not isinstance(schema, dict):
        raise FeatureSchemaError("피처 스키마가 객체(dict)가 아닙니다.")
    cols = schema.get("feature_cols")
    if not isinstance(cols, list) or not cols or not all(isinstance(c, str) for c in cols):
        raise FeatureSchemaError("feature_cols 가 비어 있지 않은 문자열 리스트가 아닙니다.")

    dim = schema.get("feature_dim")
    if dim is not None and dim != len(cols):
        raise FeatureSchemaError(
            f"feature_dim({dim}) 과 len(feature_cols)({len(cols)}) 가 다릅니다."
        )
    duplicates = sorted({c for c in cols if cols.count(c) > 1})
    if duplicates:
        raise FeatureSchemaError(f"feature_cols 에 중복된 피처명이 있습니다: {duplicates}")
    return list(cols)


def _describe_order_diff(schema_cols: Sequence[str], expected_cols: Sequence[str]) -> str:
    """불일치 지점을 사람이 읽을 수 있게 요약(첫 어긋난 인덱스 + 누락/추가 항목)."""
    limit = min(len(schema_cols), len(expected_cols))
    lines: list[str] = []
    for i in range(limit):
        if schema_cols[i] != expected_cols[i]:
            lines.append(
                f"  - 첫 불일치 인덱스 [{i}]: 스키마='{schema_cols[i]}' vs 코드='{expected_cols[i]}'"
            )
            break
    if len(schema_cols) != len(expected_cols):
        lines.append(f"  - 차원 수: 스키마 {len(schema_cols)} vs 코드 {len(expected_cols)}")
    missing = [c for c in schema_cols if c not in set(expected_cols)]
    extra = [c for c in expected_cols if c not in set(schema_cols)]
    if missing:
        lines.append(f"  - 코드에 없는 스키마 피처: {missing}")
    if extra:
        lines.append(f"  - 스키마에 없는 코드 피처: {extra}")
    return "\n".join(lines) if lines else "  - (차이는 있으나 상세 산출 실패)"


def validate_expected_order(
    schema: dict, expected_cols: Iterable[str], expected_label: str
) -> list[str]:
    """스키마 피처 순서와 코드의 순서를 대조한다. 불일치면 `FeatureSchemaError`."""
    schema_cols = schema_feature_cols(schema)
    expected = list(expected_cols)
    if schema_cols == expected:
        return schema_cols
    version = schema.get("model_version", "?")
    raise FeatureSchemaError(
        f"피처 순서 불일치 — 스키마(model_version={version}) vs {expected_label}\n"
        f"{_describe_order_diff(schema_cols, expected)}\n"
        "  → 순서가 다르면 예측이 조용히 붕괴합니다(v1 32d 자산을 v2 배치로 넣으면 R²<0)."
    )


def validate_targets(schema: dict, expected: dict) -> dict:
    """스키마 `targets`(수단 → 타깃 컬럼) 매핑을 대조한다."""
    targets = schema.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise FeatureSchemaError("스키마에 targets(수단 → 타깃 컬럼) 매핑이 없습니다.")
    if dict(targets) != dict(expected):
        raise FeatureSchemaError(f"타깃 매핑 불일치 — 스키마 {targets} vs 코드 {expected}")
    return dict(targets)


def validate_split_bounds(
    schema: dict,
    train_end: str,
    val_end: str,
    test_start: str,
    test_end: Optional[str] = None,
) -> dict:
    """스키마 `split` 문자열('2025-01-01~2025-09-30')을 사양서 경계와 대조한다."""
    split = schema.get("split")
    if not isinstance(split, dict):
        raise FeatureSchemaError("스키마에 split 경계 정보가 없습니다.")
    parsed: dict[str, list[str]] = {}
    for key in ("train", "valid", "test"):
        raw = split.get(key)
        match = _SPLIT_RANGE_RE.match(str(raw)) if raw is not None else None
        if not match:
            raise FeatureSchemaError(
                f"split.{key} 형식이 'YYYY-MM-DD~YYYY-MM-DD' 가 아닙니다: {raw!r}"
            )
        parsed[key] = [match.group(1), match.group(2)]

    mismatches = []
    if parsed["train"][1] != train_end:
        mismatches.append(f"train 종료: 스키마 {parsed['train'][1]} vs 코드 {train_end}")
    if parsed["valid"][1] != val_end:
        mismatches.append(f"valid 종료: 스키마 {parsed['valid'][1]} vs 코드 {val_end}")
    if parsed["test"][0] != test_start:
        mismatches.append(f"test 시작: 스키마 {parsed['test'][0]} vs 코드 {test_start}")
    if test_end is not None and parsed["test"][1] != test_end:
        mismatches.append(f"test 종료: 스키마 {parsed['test'][1]} vs 코드 {test_end}")
    if mismatches:
        raise FeatureSchemaError("분할 경계 불일치 — " + " / ".join(mismatches))
    return split


# --------------------------------------------------------------- 편의 헬퍼
def legacy_25d_indices() -> tuple[int, ...]:
    """25차원 레거시 서브셋 인덱스(32차원 기준 위치)."""
    return LEGACY_25D_INDICES


def legacy_25d_cols(schema: dict) -> list[str]:
    """스키마 32차원에서 25차원 레거시 서브셋의 피처명을 뽑는다."""
    cols = schema_feature_cols(schema)
    max_index = max(LEGACY_25D_INDICES)
    if len(cols) <= max_index:
        raise FeatureSchemaError(
            f"스키마 차원({len(cols)})이 25차원 서브셋 인덱스(최대 {max_index})를 담지 못합니다."
        )
    return [cols[i] for i in LEGACY_25D_INDICES]


def schema_summary(
    schema: Optional[dict],
    path: Optional[Path] = None,
    model_input_dims: Optional[dict] = None,
    status: Optional[str] = None,
) -> dict:
    """`/health`·리포트용 스키마 요약(민감정보 없음)."""
    input_dims = {k: int(v) for k, v in (model_input_dims or {}).items()}

    if path is not None:
        try:
            display = path.resolve().relative_to(BASE_DIR).as_posix()
        except ValueError:
            display = str(path)
    else:
        display = None

    if not schema:
        return {
            "path": display,
            "status": status or "not-found",
            "feature_dim": None,
            "model_input_dims": input_dims,
        }
    cols = schema_feature_cols(schema)
    return {
        "path": display,
        "status": status or "verified",
        "model_version": schema.get("model_version"),
        "feature_dim": len(cols),
        "order": schema.get("order"),
        "targets": schema.get("targets"),
        "split": schema.get("split"),
        "model_input_dims": input_dims,
    }