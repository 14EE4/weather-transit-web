# -*- coding: utf-8 -*-
"""
benchmarks/evaluate_models.py
================================================================================
**실제 32차원 피처** 기준 ONNX 모델 공정 비교 평가 스크립트 (v2).

v1 → v2 핵심 변경
  1. 원천 데이터   : data/2025_서울25개구_교통날씨_전처리_2.csv (209,875행 × 33열)
  2. 피처          : "25차원 + 상수 0 더미 7" 폐기 → **실제 32차원**
                     (공간 인프라 4 + same_day_last_week 3 을 실측값으로 채움)
  3. 분할          : 사양서 §6.1 Temporal Split (train ≤ 09-30 / valid ≤ 11-15 / test ≥ 11-16)
                     — 전처리 CSV `분할` 컬럼(valid 10-01~10-31 / test 11-01~)은 사용하지 않음
  4. is_holiday    : 2025 대한민국 실제 공휴일 캘린더(19일) 적용 — `is_weekend` 와 분리
  5. 단일 소스     : district_code / 인프라 4종 / 공휴일 캘린더를 `main.py` 에서 직접 import
                     → 학습↔서빙 피처 정의 드리프트 원천 차단
  6. 레거시 참고치 : 25차원 배포 모델은 학습 당시 분포(is_holiday 상수 0) 결과를 1행 더 병기
  7. 피처 스키마   : `feature_schema.json`(SSoT) 을 읽어 **차원·순서·타깃·분할 경계를 assert**
                     (경로 자동 탐색 / `--schema PATH` / 환경변수 `FEATURE_SCHEMA_PATH`)

비교 대상 (기본값, `--model LABEL=PATH` 로 추가/덮어쓰기 가능)
    * production_25d : benchmarks/original/lgb_{mode}_demand.onnx   (배포본, 25차원)
      → `models/lgb_{mode}_demand.onnx` 와 **바이트 동일(SHA256)** 이므로 별도 평가하지 않습니다.
    * tuned_32d_real : benchmarks/2026-10-14/lgb_{mode}_demand.onnx (신규 후보, v2 32차원 실피처)
      → Colab(`benchmarks/CastTransit.ipynb` [Cell 7]) 산출 3종이 `benchmarks/2026-10-14/` 에 반입되어 있습니다.
      (구 배치 위치 `benchmarks/2026-10-12/tuned_real/` 은 안내 README 만 남은 종료 폴더)
    * tuned_32d_v1   : benchmarks/2026-10-12/tuned/lgb_{mode}_demand.onnx (구 후보, v1 배치)

  ⚠️ 세대별 **피처 배치가 다릅니다.** 각 모델은 자기 배치로만 평가해야 합니다(인덱스 어긋남 방지).
     * `v2-32d-real`  : 사양서 §3.2 순서 (8/8/5/11) — 인프라 4 + `same_day_last_week_*` 3 실측
     * `v1-32d-dummy7`: v1 배치 (8/8/1/3/3/2 + 상수 0 더미 7) → **정보량은 25차원과 동일**
     * `25d-subset`   : v2 32차원에서 [17..20](공간 인프라 4) + [27..29](same_day 3) 제외
     → `MODEL_LAYOUTS` 가 라벨별 배치를 지정하며(미지정 = v2), `--layout LABEL=v1|v2` 로 덮어쓸 수 있습니다.
  ⚠️ 구 후보(`tuned_32d_v1`)와 배포본(25차원)은 `is_holiday` 가 **상수 0인 데이터로 학습**되었으므로,
     학습 분포 기준 참고치(`reference_ih0`)를 함께 기록합니다.

산출물: benchmarks/results/comparison_{timestamp}.json / .md
        (R² / RMSE / MAE / MAPE(실측 0 제외) / 단건 ONNX 추론 레이턴시(ms))

실행:
    python benchmarks/evaluate_models.py                    # 배포본 / v1 32d / v2 32d 실피처 3종 동시 비교
    python benchmarks/evaluate_models.py --model tuned_32d_real=benchmarks/2026-10-14
    python benchmarks/evaluate_models.py --layout tuned_32d_real=v1   # 배치 강제(인덱스 어긋남 주의)
    python benchmarks/evaluate_models.py --schema benchmarks/2026-10-14/feature_schema.json  # SSoT 경로 명시
================================================================================
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import onnxruntime as ort

# ------------------------------------------------------------------ 경로 정의
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 피처 정의의 유일한 소스 = 서빙 코드(main.py) + 피처 스키마(feature_schema.json, SSoT)
from main import DISTRICT_CODE_MAP, DISTRICT_INFRA, KR_HOLIDAYS  # noqa: E402
from feature_schema import (  # noqa: E402
    legacy_25d_cols,
    legacy_25d_indices,
    load_schema,
    resolve_schema_path,
    schema_feature_cols,
    validate_expected_order,
    validate_split_bounds,
    validate_targets,
)

CSV_PATH = ROOT / "data" / "2025_서울25개구_교통날씨_전처리_2.csv"
BENCH_DIR = ROOT / "benchmarks"
RESULTS_DIR = BENCH_DIR / "results"

# 평가 대상(수단) -> CSV 타깃 컬럼 (ONNX 파일명 접두사와 동일)
TARGETS = {
    "bike": "따릉이_대여",
    "bus": "버스_승차",
    "subway": "지하철_승차",
}

# 래그/이동통계 계산용 (노트북 [Cell 4-B] LAG_TARGETS 와 키 이름까지 동일)
LAG_TARGETS = {
    "bike": "따릉이_대여",
    "bus": "버스_승차",
    "sub": "지하철_승차",
}

# same_day_last_week 접미사 (노트북 [Cell 4-B] 와 동일한 명명 규칙)
SAME_DAY_SUFFIX = {
    "따릉이_대여": "bike",
    "버스_승차": "bus",
    "지하철_승차": "sub",
}

# Temporal Split 경계 (docs/AI_MODEL_SPEC.md §6.1 · 공식)
TRAIN_END = "2025-09-30"
VAL_END = "2025-11-15"
TEST_START = "2025-11-16"
TEST_END = "2025-12-31"

# 32차원 피처 순서 (main.py::build_feature_vector 인덱스 0~31 과 완전 일치)
FEATURE_COLS_32 = [
    # [0..7] 시계열 및 캘린더 피처
    "month_sin", "month_cos", "hour_sin", "hour_cos",
    "dayofweek", "is_weekend", "is_holiday", "is_rush_hour",
    # [8..15] 기상 관측 및 파생 피처
    "temperature", "wind_speed", "humidity", "precipitation",
    "is_raining", "rain_intensity", "sensible_temp", "discomfort_index",
    # [16..20] 공간(위치) 인코딩 피처
    "district_code", "district_subway_stations", "district_bus_stops",
    "district_bike_racks", "commercial_density",
    # [21..31] 시계열 래그 및 이동통계 피처
    "따릉이_대여_lag_1h", "버스_승차_lag_1h", "지하철_승차_lag_1h",
    "따릉이_대여_roll_3h", "버스_승차_roll_3h", "지하철_승차_roll_3h",
    "same_day_last_week_bike", "same_day_last_week_bus", "same_day_last_week_sub",
    "temp_diff_1h", "rain_diff_1h",
]

# main.py::prepare_session_input 이 25차원 세션에 전달하는 인덱스와 동일한 서브셋
# (인덱스 정의의 단일 소스 = feature_schema.LEGACY_25D_INDICES)
LEGACY_25D_INDICES = list(legacy_25d_indices())
FEATURE_COLS_25 = [FEATURE_COLS_32[i] for i in LEGACY_25D_INDICES]
IS_HOLIDAY_INDEX = FEATURE_COLS_32.index("is_holiday")

# v1 배치(구 후보 `2026-10-12/tuned`) 정의: 25차원 + 상수 0 더미 7
# - 구 스크립트(`ef1d03d:benchmarks/evaluate_models.py`)의 FEATURE_COLS + infra_dummy_0..6 과 동일
# - 더미는 상수 0 이므로 25차원 행렬 뒤에 0 열을 붙여 재현한다(정보량 = 25차원).
V1_DUMMY_COLS = [f"infra_dummy_{i}" for i in range(32 - len(FEATURE_COLS_25))]
FEATURE_COLS_32_V1 = FEATURE_COLS_25 + V1_DUMMY_COLS

# 기본 모델 세트 (라벨 -> 폴더). CLI `--model LABEL=PATH` 로 덮어쓸 수 있다.
MODEL_SETS: dict[str, Path] = {
    "production_25d": BENCH_DIR / "original",
    # 2026-10-14 Colab 학습 산출물(v2 실제 32차원 실피처, feature_schema.json 동봉)
    "tuned_32d_real": BENCH_DIR / "2026-10-14",
    # 구 후보(v1): 25차원 + 상수 0 더미 7 — 참고 보관 자산이지만 배치만 맞추면 비교 가능
    "tuned_32d_v1": BENCH_DIR / "2026-10-12" / "tuned",
}

# 라벨별 피처 배치(32차원 모델에만 적용). 미지정 라벨은 v2(사양서 §3.2 실피처)로 평가한다.
# 25차원 모델은 배치와 무관하게 FEATURE_COLS_25 를 사용한다(입력 텐서 자체가 좁은 층위).
MODEL_LAYOUTS: dict[str, str] = {
    "tuned_32d_v1": "v1",
}
LAYOUT_ORDER = ("v2", "v1")  # `--layout` 허용값(문서·검증용)
BASELINE_LABEL = "production_25d"  # 델타 기준(배포본 25차원)

# `is_holiday` 가 상수 0 인 데이터로 학습된 **레거시** 자산만 참고치(reference_ih0)를 병기합니다.
# (2026-10-14 이후 신규 학습 자산은 실제 공휴일 19일 캘린더로 학습되므로 참고치가 무의미)
LEGACY_IH0_LABELS = frozenset({"production_25d", "tuned_32d_v1"})

# 레이턴시 측정 반복 횟수(웜업 20회 제외)
LATENCY_ITERS = 200


# ------------------------------------------------------------ 피처 엔지니어링
def load_and_engineer(csv_path: Path) -> pd.DataFrame:
    """노트북 [Cell 3] 정제 + [Cell 4-A]·[Cell 4-B] 피처 엔지니어링을 재현한다.

    반환값은 실제 32차원 피처(더미 없음)가 모두 채워진 DataFrame 이며,
    컬럼 순서는 `main.py::build_feature_vector` 의 인덱스 0~31 과 일치한다.
    """
    df = pd.read_csv(csv_path)
    print(f"[load] 원천 데이터: {df.shape} | 파일: {csv_path.name}")

    # ---- [Cell 3] 결측치 도메인 정제 ----
    # 지하철 심야 운휴(01~05시)는 결측이 아니라 구조적 0
    df.loc[df["시간"].isin([1, 2, 3, 4, 5]), ["지하철_승차", "지하철_하차"]] = 0
    df["강수량(mm)"] = df["강수량(mm)"].fillna(0.0)
    for c in ["기온(°C)", "풍속(m/s)", "습도(%)"]:
        df[c] = df[c].interpolate(method="linear")
    df["버스_승차"] = df["버스_승차"].interpolate(method="linear").bfill().ffill()
    df["따릉이_대여"] = df["따릉이_대여"].fillna(0)

    # ---- 정렬 (래그·이동통계 산출의 전제) ----
    df["기준_날짜"] = pd.to_datetime(df["기준_날짜"])
    df["기준_일시"] = pd.to_datetime(df["기준_일시"])
    df = df.sort_values(["구", "기준_일시"]).reset_index(drop=True)

    # ---- 블록 1. 시계열 및 캘린더 피처 (8) ----
    df["month"] = df["기준_날짜"].dt.month
    df["dayofweek"] = df["기준_날짜"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    # is_holiday = 실제 대한민국 공휴일(주말과 별개 지표). main.py::KR_HOLIDAYS 단일 소스.
    holiday_dates = {pd.Timestamp(d) for days in KR_HOLIDAYS.values() for d in days}
    df["is_holiday"] = df["기준_날짜"].isin(holiday_dates).astype(int)
    df["is_rush_hour"] = df["시간"].isin([8, 9, 18, 19]).astype(int)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["hour_sin"] = np.sin(2 * np.pi * df["시간"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["시간"] / 24.0)

    # ---- 블록 2. 기상 관측 및 파생 피처 (8) ----
    df["temperature"] = df["기온(°C)"]
    df["wind_speed"] = df["풍속(m/s)"].clip(lower=0.1)   # 서빙: max(wind, 0.1)
    df["humidity"] = df["습도(%)"]
    df["precipitation"] = df["강수량(mm)"]
    df["is_raining"] = (df["precipitation"] > 0.0).astype(int)
    # 서빙과 동일한 경계: <=0 → 0, <3 → 1, <=10 → 2, 그 외 → 3
    df["rain_intensity"] = np.select(
        [df["precipitation"] <= 0.0, df["precipitation"] < 3.0, df["precipitation"] <= 10.0],
        [0, 1, 2], default=3,
    ).astype(int)
    _v = df["wind_speed"] ** 0.16
    df["sensible_temp"] = (
        13.12 + 0.6215 * df["temperature"] - 11.37 * _v
        + 0.3965 * df["temperature"] * _v
    )
    df["discomfort_index"] = (
        1.8 * df["temperature"] - 0.55 * (1 - df["humidity"] / 100.0)
        * (1.8 * df["temperature"] - 26.0) + 32.0
    )

    # ---- 블록 3. 공간(위치) 인코딩 피처 (5) — main.py 단일 소스 ----
    unknown = sorted(set(df["구"].unique()) - set(DISTRICT_CODE_MAP))
    assert not unknown, f"main.py::DISTRICT_CODE_MAP 에 없는 지역: {unknown}"
    df["district_code"] = df["구"].map(DISTRICT_CODE_MAP).astype(int)
    infra = (
        pd.DataFrame(DISTRICT_INFRA).T
        .rename(columns={
            "subway_stations": "district_subway_stations",
            "bus_stops": "district_bus_stops",
            "bike_racks": "district_bike_racks",
        })[["district_subway_stations", "district_bus_stops",
            "district_bike_racks", "commercial_density"]]
    )
    n_rows = len(df)
    df = df.merge(infra, left_on="구", right_index=True, how="left")
    assert len(df) == n_rows, "인프라 조인으로 행 수가 변했습니다."
    assert df["district_subway_stations"].notna().all(), "인프라 조인 누락(main.py::DISTRICT_INFRA 확인)"
    df = df.sort_values(["구", "기준_일시"]).reset_index(drop=True)

    # ---- 블록 4. 시계열 래그 및 이동통계 피처 (11) ----
    for col in LAG_TARGETS.values():
        df[f"{col}_lag_1h"] = df.groupby("구")[col].shift(1)
        df[f"{col}_roll_3h"] = df.groupby("구")[col].transform(
            lambda x: x.rolling(3, min_periods=1).mean()
        )
    # 구별 첫 관측치(01-01 01시)의 lag 결측 → 3시간 이동평균으로 보정
    for col in LAG_TARGETS.values():
        df[f"{col}_lag_1h"] = df[f"{col}_lag_1h"].fillna(df[f"{col}_roll_3h"])
    df["temp_diff_1h"] = df.groupby("구")["temperature"].diff().fillna(0.0)
    df["rain_diff_1h"] = df.groupby("구")["precipitation"].diff().fillna(0.0)

    # same_day_last_week: 하루 23개 시간대(01~23시)이므로 행 shift(168) 이 아니라
    #                     7일 전 타임스탬프 기준 self-merge 로 계산한다.
    prev = df[["구", "기준_일시"] + list(LAG_TARGETS.values())].copy()
    prev["기준_일시"] = prev["기준_일시"] + pd.Timedelta(days=7)
    prev = prev.rename(columns={
        "따릉이_대여": "same_day_last_week_bike",
        "버스_승차": "same_day_last_week_bus",
        "지하철_승차": "same_day_last_week_sub",
    })
    n_rows = len(df)
    df = df.merge(prev, on=["구", "기준_일시"], how="left")
    assert len(df) == n_rows, "same_day_last_week 조인으로 행 수가 변했습니다(키 중복 확인)."
    # 2025-01-01~01-07 구간은 7일 전 데이터가 없으므로 lag_1h 로 프록시 대체
    for col in LAG_TARGETS.values():
        dst = f"same_day_last_week_{SAME_DAY_SUFFIX[col]}"
        df[dst] = df[dst].fillna(df[f"{col}_lag_1h"]).fillna(0.0)

    # ---- 무결성 검증 ----
    assert len(FEATURE_COLS_32) == 32, f"32차원이 아닙니다: {len(FEATURE_COLS_32)}"
    assert len(FEATURE_COLS_25) == 25, f"25차원 서브셋이 아닙니다: {len(FEATURE_COLS_25)}"
    missing = df[FEATURE_COLS_32].isna().sum()
    assert int(missing.sum()) == 0, f"피처 결측 잔존:\n{missing[missing > 0]}"
    assert np.isfinite(df[FEATURE_COLS_32].to_numpy(dtype=np.float64)).all(), "피처에 inf/NaN 존재"
    print(
        f"[feat] 실제 32차원 확정 | 결측 0 | 공휴일 {int(df['is_holiday'].sum()):,}행 "
        f"({df['is_holiday'].mean() * 100:.2f}%) | 인프라 4종·same_day 3종 실측 조인 완료"
    )
    return df


# ------------------------------------------------------------------ 지표 계산
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """R2 / RMSE / MAE / MAPE(실측 0 제외) 계산."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    residual = y_true - y_pred
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    nz = y_true != 0  # MAPE 는 실측 0(심야 운휴 등) 제외
    mape = float(np.mean(np.abs(residual[nz] / y_true[nz])) * 100.0) if nz.any() else float("nan")
    return {"r2": r2, "rmse": rmse, "mae": mae, "mape_pct_nonzero": mape, "n": int(y_true.size)}


def onnx_input_dim(session: ort.InferenceSession) -> int:
    return int(session.get_inputs()[0].shape[1])


def measure_latency(session: ort.InferenceSession, x_row: np.ndarray, iters: int = LATENCY_ITERS) -> float:
    """단건(1행) 추론 평균 레이턴시(ms). 웜업 20회 후 iters 회 측정."""
    name = session.get_inputs()[0].name
    for _ in range(20):
        session.run(None, {name: x_row})
    t0 = time.perf_counter()
    for _ in range(iters):
        session.run(None, {name: x_row})
    t1 = time.perf_counter()
    return (t1 - t0) / iters * 1000.0


# ------------------------------------------------------------ 자산 인벤토리(SHA256)
def sha256_file(path: Path) -> str:
    """파일 SHA256 (자산 동일성 판정용)."""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_inventory() -> dict[str, str]:
    """`benchmarks/` 하위 ONNX 자산 + 배포 슬롯 `models/` 의 SHA256 인벤토리.

    배포 슬롯(`models/`)이 `benchmarks/original/` 과 바이트 동일하면 별도 평가 행을 만들
    필요가 없으므로, 중복 여부를 결과 리포트(JSON/MD)에 함께 남긴다.
    """
    inventory: dict[str, str] = {}
    for base in (BENCH_DIR, ROOT / "models"):
        if not base.exists():
            continue
        for onnx_path in sorted(base.rglob("lgb_*_demand.onnx")):
            rel = onnx_path.relative_to(ROOT).as_posix()  # 리포트는 OS 무관하게 '/' 표기
            inventory[rel] = sha256_file(onnx_path)
    return inventory


# ---------------------------------------------------------------- 결과 포매팅
def _md_schema_line(results: dict) -> str:
    """피처 스키마(SSoT) 검증 결과를 한 줄로 요약 — 리포트 재현성/게이트 근거."""
    spec = results.get("feature_spec", {}).get("schema") or {}
    if not spec.get("enabled"):
        return "미발견 → 내장 `FEATURE_COLS_32` 상수 사용 (순서 검증 생략)"
    checks = " / ".join(spec.get("checks", []))
    return (
        f"`{spec.get('path')}` (model_version={spec.get('model_version')}, "
        f"{spec.get('feature_dim')}차원) — **{spec.get('status')}** · {checks}"
    )


def _md_table(results: dict) -> str:
    lines = [
        "| 모델 | 수단 | 입력차원 | 피처 배치 | R² | RMSE | MAE | MAPE(실측0제외) | 레이턴시(ms) | 파일(byte) |",
        "| :--- | :---: | :---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, blk in results["models"].items():
        for mode, m in blk["targets"].items():
            lines.append(
                f"| {label} | {mode} | {m['input_dim']} | {m['layout']} | {m['r2']:.4f} | {m['rmse']:.3f} | "
                f"{m['mae']:.3f} | {m['mape_pct_nonzero']:.2f}% | {m['latency_ms_1row']:.3f} | "
                f"{m['file_size_bytes']} |"
            )
    return "\n".join(lines)


def _md_reference_section(results: dict) -> list[str]:
    """레거시 모델(배포본 25차원 / 구 후보 v1 32차원)의 `is_holiday = 0` 참고치 섹션을 만든다.

    레거시 모델은 `is_holiday` 가 상수 0 인 데이터로 학습되었기 때문에 실제 공휴일을
    넣어도 예측이 바뀌지 않을 수 있다. 이 경우 표 대신 진단 한 줄만 남긴다.
    """
    rows, identical = [], []
    for label, blk in results["models"].items():
        for mode, m in blk["targets"].items():
            ref = m.get("reference_ih0")
            if not ref:
                continue
            same = abs(ref["r2"] - m["r2"]) < 5e-5 and abs(ref["rmse"] - m["rmse"]) < 5e-3
            if same:
                identical.append(f"{label}/{mode}")
            else:
                rows.append(
                    f"| {label} | {mode} | {ref['r2']:.4f} | {ref['rmse']:.3f} | "
                    f"{ref['mae']:.3f} | {ref['mape_pct_nonzero']:.2f}% |"
                )
    if not rows:
        if not identical:
            return []
        return [
            "## 레거시 모델 `is_holiday = 0` 참고치 (배포본 25차원 / v1 32차원)",
            "",
            f"- `{', '.join(identical)}`: 값 동일 — 레거시 모델은 `is_holiday` 가 상수 0 인 "
            "데이터로 학습되어 해당 피처를 전혀 사용하지 않습니다(주말 정보는 `is_weekend` 로 별도 존재).",
            "",
        ]
    return [
        "## 레거시 모델 `is_holiday = 0` 참고치 (배포본 25차원 / v1 32차원 · 학습 당시 분포)",
        "",
        "| 모델 | 수단 | R² | RMSE | MAE | MAPE(실측0제외) |",
        "| :--- | :---: | ---: | ---: | ---: | ---: |",
        *rows,
        "",
    ]


def _md_delta_section(results: dict) -> list[str]:
    """배포본(25차원) 대비 델타 — 수단별 우열을 한눈에 판정하기 위한 요약."""
    base = results["models"].get(BASELINE_LABEL)
    if not base or not base["targets"]:
        return []
    rows: list[str] = []
    for label, blk in results["models"].items():
        if label == BASELINE_LABEL:
            continue
        for mode, m in blk["targets"].items():
            b = base["targets"].get(mode)
            if not b:
                continue
            rows.append(
                f"| {label} ({m['layout']}) | {mode} | {m['r2'] - b['r2']:+.4f} | "
                f"{m['rmse'] - b['rmse']:+.3f} | {m['mae'] - b['mae']:+.3f} | "
                f"{m['mape_pct_nonzero'] - b['mape_pct_nonzero']:+.2f}%p |"
            )
    if not rows:
        return []
    return [
        f"## `{BASELINE_LABEL}`(배포본 25차원) 대비 델타",
        "",
        "- R² 는 **양수(+) = 개선**, RMSE / MAE / MAPE 는 **음수(−) = 개선** 입니다.",
        "- `tuned_32d_v1`(v1 배치)은 25차원 뒤에 **상수 0 더미 7** 을 붙인 구조이므로 "
        "**정보량이 25차원과 동일**합니다 → 델타는 전부 **Optuna 튜닝 효과**입니다.",
        "- `tuned_32d_real`(v2 배치)은 인프라 4 + `same_day_last_week_*` 3이 실측값이므로 "
        "**튜닝 + 차원 증가 + 원천 데이터(`전처리_2`) 효과가 혼재**합니다(순수 차원 효과 아님).",
        "",
        "| 모델 (배치) | 수단 | ΔR² | ΔRMSE | ΔMAE | ΔMAPE |",
        "| :--- | :---: | ---: | ---: | ---: | ---: |",
        *rows,
        "",
    ]


def _md_asset_section(results: dict) -> list[str]:
    """SHA256 인벤토리 섹션 — `models/`(배포 슬롯) 와 벤치마크 자산의 동일/중복 여부."""
    inventory: dict = results.get("asset_sha256") or {}
    if not inventory:
        return []
    groups: dict[str, list[str]] = {}
    for path, digest in inventory.items():
        groups.setdefault(digest, []).append(path)
    dups = {digest: paths for digest, paths in groups.items() if len(paths) > 1}
    lines = [
        "## 자산 무결성 (SHA256)",
        "",
        f"- ONNX 자산 {len(inventory)}개 스캔 (`benchmarks/` 모델 폴더 + 배포 슬롯 `models/`).",
    ]
    if dups:
        for digest, paths in sorted(dups.items()):
            lines.append(
                f"- **동일 자산** `{digest[:16]}…`: " + " ≡ ".join(f"`{p}`" for p in paths)
                + " → 배포 슬롯은 별도 평가 행을 만들지 않습니다."
            )
    else:
        lines.append("- 바이트 동일(중복) 자산 없음.")
    lines.append("")
    return lines


def parse_model_overrides(pairs: list[str]) -> dict[str, Path]:
    """`--model LABEL=PATH` 인자를 (라벨 -> 절대경로) 딕셔너리로 변환."""
    out: dict[str, Path] = {}
    for raw in pairs:
        label, sep, path = raw.partition("=")
        assert sep and path.strip(), f"--model 형식은 LABEL=PATH 입니다: {raw}"
        out[label.strip()] = (ROOT / path.strip()).resolve()
    return out


# ------------------------------------------------------- 피처 스키마(SSoT) 검증
def verify_feature_schema(explicit_path: str | None) -> dict:
    """`feature_schema.json`(SSoT)을 읽어 이 스크립트의 피처 정의와 대조한다.

    검증 항목: ① feature_cols 순서·차원 == 코드 상수(`FEATURE_COLS_32` 또는 25차원 배치면 `FEATURE_COLS_25`)
              ② targets 매핑 == `TARGETS`
              ③ split 경계 == 사양서 §6.1(`TRAIN_END`/`VAL_END`/`TEST_START`/`TEST_END`)
              ④ 32차원 스키마면 25차원 레거시 서브셋 명칭 == `FEATURE_COLS_25`

    반환값은 결과 리포트에 그대로 실린다(`feature_spec.schema`). 불일치면 예외로 중단.
    스키마 미발견 시에는 내장 상수로만 진행하고 `status='skipped'` 로 기록한다.
    """
    info: dict = {"enabled": False, "path": None, "status": "skipped"}
    schema_path = resolve_schema_path(explicit_path)
    if schema_path is None:
        print(
            "[schema] feature_schema.json 미발견 → 내장 FEATURE_COLS_32 상수를 사용합니다 "
            "(검증 생략. `--schema PATH` 또는 FEATURE_SCHEMA_PATH 로 지정 가능)"
        )
        return info

    try:
        display = schema_path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        display = str(schema_path)

    schema = load_schema(schema_path)
    cols = schema_feature_cols(schema)
    validate_targets(schema, TARGETS)
    validate_split_bounds(schema, TRAIN_END, VAL_END, TEST_START, TEST_END)

    common_checks = [
        "targets 매핑 일치 (bike/bus/subway)",
        f"split 경계 일치 (train≤{TRAIN_END} / valid≤{VAL_END} / test={TEST_START}~{TEST_END})",
    ]
    if len(cols) == len(FEATURE_COLS_32):
        validate_expected_order(
            schema, FEATURE_COLS_32, "benchmarks/evaluate_models.py::FEATURE_COLS_32"
        )
        subset = legacy_25d_cols(schema)
        assert subset == FEATURE_COLS_25, (
            "25차원 레거시 서브셋 피처명 불일치\n"
            f"  - 스키마: {subset}\n  - 평가 스크립트: {FEATURE_COLS_25}"
        )
        layout_note = "32차원 실피처 배치(사양서 §3.2)"
        checks = [
            f"feature_cols {len(cols)}차원 순서 == evaluate_models.py::FEATURE_COLS_32",
            *common_checks,
            f"25차원 레거시 서브셋 {len(subset)}개 명칭 일치",
        ]
    elif len(cols) == len(FEATURE_COLS_25):
        validate_expected_order(
            schema, FEATURE_COLS_25, "benchmarks/evaluate_models.py::FEATURE_COLS_25"
        )
        layout_note = "25차원 서빙 서브셋 배치(레거시/25차원 재학습본)"
        checks = [
            f"feature_cols {len(cols)}차원 순서 == evaluate_models.py::FEATURE_COLS_25",
            *common_checks,
            "배포 슬롯 25차원 모델과 동일 배치(서빙 정렬 가능)",
        ]
    else:
        raise FeatureSchemaError(
            f"지원하지 않는 스키마 차원입니다: {len(cols)} "
            f"(32차원 실피처 또는 25차원 서빙 서브셋만 지원)"
        )

    info.update({
        "enabled": True,
        "path": display,
        "model_version": schema.get("model_version"),
        "status": "PASS",
        "feature_dim": len(cols),
        "layout": layout_note,
        "checks": checks,
    })
    print(
        f"[schema] PASS — {display} (model_version={info['model_version']}, {len(cols)}차원 · "
        f"{layout_note}) | 순서·타깃·분할 assert 통과"
    )
    return info


def parse_layout_overrides(pairs: list[str]) -> dict[str, str]:
    """`--layout LABEL=v1|v2` 인자를 (라벨 -> 배치) 딕셔너리로 변환."""
    out: dict[str, str] = {}
    for raw in pairs:
        label, sep, layout = raw.partition("=")
        assert sep and layout.strip(), f"--layout 형식은 LABEL=v1|v2 입니다: {raw}"
        value = layout.strip().lower()
        assert value in LAYOUT_ORDER, f"지원하지 않는 배치입니다({value}): {LAYOUT_ORDER}"
        out[label.strip()] = value
    return out


# ------------------------------------------------------------------- 엔트리
def main() -> None:
    parser = argparse.ArgumentParser(
        description="실제 32차원 피처 기준 ONNX 모델 공정 비교 평가 (v2)"
    )
    parser.add_argument("--csv", default=str(CSV_PATH), help="원천 CSV 경로")
    parser.add_argument(
        "--model", action="append", default=[], metavar="LABEL=PATH",
        help="평가할 모델 폴더를 라벨=경로로 추가/덮어쓰기 (반복 가능)",
    )
    parser.add_argument(
        "--layout", action="append", default=[], metavar="LABEL=v1|v2",
        help="라벨별 피처 배치 덮어쓰기 (v1=25차원+상수 0 더미 7 / v2=사양서 §3.2 32차원, 기본 v2)",
    )
    parser.add_argument(
        "--schema", default=None, metavar="PATH",
        help="피처 스키마(feature_schema.json) 경로 — 미지정 시 자동 탐색 "
             "(models/ → benchmarks/2026-10-14/), FEATURE_SCHEMA_PATH 환경변수로도 지정 가능",
    )
    args = parser.parse_args()

    model_sets = dict(MODEL_SETS)
    model_sets.update(parse_model_overrides(args.model))
    model_layouts = dict(MODEL_LAYOUTS)
    model_layouts.update(parse_layout_overrides(args.layout))

    csv_path = Path(args.csv)
    try:  # 로그/산출물에는 가능한 한 레포 상대경로를 남긴다
        csv_display = str(csv_path.resolve().relative_to(ROOT))
    except ValueError:
        csv_display = str(csv_path)

    # 피처 스키마(SSoT) 검증 — 무거운 CSV 로드 이전에 순서/차원을 확정한다.
    schema_info = verify_feature_schema(args.schema)

    df = load_and_engineer(csv_path)

    # ---- 사양서 §6.1 Temporal Split ----
    train_mask = df["기준_날짜"] <= TRAIN_END
    val_mask = (df["기준_날짜"] > TRAIN_END) & (df["기준_날짜"] <= VAL_END)
    test_mask = df["기준_날짜"] > VAL_END
    test_dates = df.loc[test_mask, "기준_날짜"]
    print(
        f"[split] train={int(train_mask.sum()):,} val={int(val_mask.sum()):,} "
        f"test={int(test_mask.sum()):,} | test {test_dates.min().date()} ~ {test_dates.max().date()}"
    )

    # 모든 모델군이 **동일한 테스트 행**에서 만들어지므로 차이는 피처 배치(구성)뿐이다.
    X32 = df.loc[test_mask, FEATURE_COLS_32].astype(np.float32).to_numpy()
    X25 = df.loc[test_mask, FEATURE_COLS_25].astype(np.float32).to_numpy()
    # v1 배치 = 25차원 + 상수 0 더미 7 (더미는 정보량 0 이므로 0 열을 덧붙여 재현)
    X32_V1 = np.hstack(
        [X25, np.zeros((X25.shape[0], len(V1_DUMMY_COLS)), dtype=np.float32)]
    )

    # 레거시(25차원 배포본 / v1 배치) 모델은 학습 당시 is_holiday 가 상수 0 이었으므로,
    # 자기 학습 분포 기준 참고치를 위해 is_holiday 열만 0 으로 둔 변형을 준비한다.
    def _ih0(mat: np.ndarray) -> np.ndarray:
        out = mat.copy()
        out[:, IS_HOLIDAY_INDEX] = 0.0
        return out

    X_BY_LAYOUT = {"v2-32d-real": X32, "v1-32d-dummy7": X32_V1, "25d-subset": X25}
    X_IH0_BY_LAYOUT = {"v1-32d-dummy7": _ih0(X32_V1), "25d-subset": _ih0(X25)}

    def pick_input(dim: int, layout: str) -> tuple[np.ndarray | None, str]:
        """(ONNX 입력 차원, 라벨 배치) -> (평가 행렬, 실제 사용 배치 라벨)."""
        if dim == len(LEGACY_25D_INDICES):  # 25차원 레거시 서브셋(배포본)
            return X25, "25d-subset"
        if dim == len(FEATURE_COLS_32):  # 32차원(배치에 따라 v1/v2)
            key = "v1-32d-dummy7" if layout == "v1" else "v2-32d-real"
            return X_BY_LAYOUT[key], key
        return None, f"unsupported-{dim}"

    y_true = {mode: df.loc[test_mask, col].to_numpy() for mode, col in TARGETS.items()}

    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "csv": csv_display,
        "evaluator": "benchmarks/evaluate_models.py (v2 · 세대별 피처 배치 병기)",
        "feature_spec": {
            "version": "v2-32d-real (상수 0 더미 7 폐기)",
            "n_features": len(FEATURE_COLS_32),
            "feature_cols_32": FEATURE_COLS_32,
            "feature_cols_25_subset": FEATURE_COLS_25,
            "feature_cols_32_v1": FEATURE_COLS_32_V1,
            "layouts": {
                "v2-32d-real": "사양서 §3.2 순서 (8/8/5/11) 실제 32차원 실피처",
                "v1-32d-dummy7": "v1 배치 (25차원 8/8/1/3/3/2 + 상수 0 더미 7) — 정보량 = 25차원",
                "25d-subset": "배포본 25차원 부분집합 (공간 인프라 4 + same_day 3 제외)",
            },
            "holiday_calendar": sorted({d for days in KR_HOLIDAYS.values() for d in days}),
            "schema": schema_info,
            "source_of_truth": (
                "feature_schema.json (피처 순서·차원) + "
                "main.py (DISTRICT_CODE_MAP / DISTRICT_INFRA / KR_HOLIDAYS)"
            ),
        },
        "split": {
            "source": "docs/AI_MODEL_SPEC.md §6.1 (spec_dates)",
            "train": f"2025-01-01 ~ {TRAIN_END}",
            "val": f"2025-10-01 ~ {VAL_END}",
            "test": f"{TEST_START} ~ {TEST_END}",
        },
        "n_test": int(test_mask.sum()),
        "asset_sha256": asset_inventory(),
        "models": {},
    }

    for label, folder in model_sets.items():
        folder = Path(folder)
        requested_layout = model_layouts.get(label, "v2")
        assert requested_layout in LAYOUT_ORDER, (
            f"라벨 `{label}` 의 배치 `{requested_layout}` 는 지원하지 않습니다: {LAYOUT_ORDER}"
        )
        block: dict = {
            "dir": str(folder),
            "requested_layout": requested_layout,
            "targets": {},
        }
        results["models"][label] = block
        for mode in TARGETS:
            onnx_path = folder / f"lgb_{mode}_demand.onnx"
            if not onnx_path.exists():
                print(f"[skip] 파일 없음: {onnx_path}")
                continue
            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            dim = onnx_input_dim(sess)
            X, used_layout = pick_input(dim, requested_layout)
            if X is None:
                print(f"[skip] 미지원 차원 {dim}: {onnx_path}")
                continue
            ins = sess.get_inputs()[0].name
            pred = np.clip(sess.run(None, {ins: X})[0].reshape(-1), 0.0, None)
            m = regression_metrics(y_true[mode], pred)
            m["input_dim"] = dim
            m["layout"] = used_layout
            m["file_size_bytes"] = onnx_path.stat().st_size
            m["sha256"] = sha256_file(onnx_path)
            m["latency_ms_1row"] = round(measure_latency(sess, X[:1]), 4)
            # is_holiday 가 상수 0 인 데이터로 학습된 자산(배포본 25d / v1)만 참고치를 남긴다.
            # ⚠️ 새로 학습된 25차원 자산(예: tuned_25d)은 공휴일 실값을 학습했으므로 제외한다.
            ref_X = X_IH0_BY_LAYOUT.get(used_layout) if label in LEGACY_IH0_LABELS else None
            if ref_X is not None:
                pred0 = np.clip(sess.run(None, {ins: ref_X})[0].reshape(-1), 0.0, None)
                m["reference_ih0"] = regression_metrics(y_true[mode], pred0)
            block["targets"][mode] = m
            print(
                f"[eval] {label:26s} {mode:6s} R2={m['r2']:.4f} RMSE={m['rmse']:8.3f} "
                f"MAE={m['mae']:7.3f} MAPE={m['mape_pct_nonzero']:6.2f}% dim={dim} "
                f"layout={used_layout:14s} {m['latency_ms_1row']:.3f}ms"
            )

    # ---- 저장 ----
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"comparison_{stamp}.json"
    md_path = RESULTS_DIR / f"comparison_{stamp}.md"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# ONNX 모델 비교 분석 결과 (세대별 피처 배치 — 25d / v1 32d / v2 32d 실피처)",
        "",
        f"- 생성시각: {results['generated_at']}",
        f"- 평가 데이터: `{results['csv']}`",
        f"- Test 구간: {results['split']['test']} (n={results['n_test']:,}, source={results['split']['source']})",
        f"- 피처: {results['feature_spec']['version']} — v2 32차원 실피처(더미 0 없음), 공휴일 캘린더 19일 적용",
        f"- 피처 스키마(SSoT): {_md_schema_line(results)}",
        "- 모델은 각자 **자기 세대의 피처 배치**로 평가했습니다(v1 배치는 25차원 + 상수 0 더미 7 재현).",
        "- MAPE 는 실측 0(심야 운휴 등) 제외.",
        "",
        _md_table(results),
        "",
    ]
    md += _md_delta_section(results)
    md += _md_reference_section(results)
    md += _md_asset_section(results)
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"\n[저장] {json_path.relative_to(ROOT)}")
    print(f"[저장] {md_path.relative_to(ROOT)}")
    inventory = results["asset_sha256"]
    unique_assets = len(set(inventory.values()))
    print(
        f"[asset] ONNX {len(inventory)}개 스캔 · 고유 자산 {unique_assets}개"
        f"(동일 파일 {len(inventory) - unique_assets}건 · 배포 슬롯 models/ 는 original/ 과 동일)"
    )
    print("\n" + _md_table(results))


if __name__ == "__main__":
    main()