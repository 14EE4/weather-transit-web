# -*- coding: utf-8 -*-
"""
피처 스키마(SSoT) 정합성 검증 테스트

검증 대상
  1. `feature_schema.json` 규격(차원 == feature_cols 수, 중복 없음)
  2. 순서 3자 일치: 스키마 == `main.py::FEATURE_ORDER_32` == `benchmarks/evaluate_models.py::FEATURE_COLS_32`
  3. 25차원 레거시 서브셋 정의 일치(`feature_schema.LEGACY_25D_INDICES` == 서빙/평가 인덱스)
  4. 실제 ONNX 자산 입력 차원(배포 슬롯 32 / 레거시 원본 25 / v1 후보 32)
  5. 타깃 매핑 · 분할 경계 · 공휴일 캘린더(19일)
  6. 네거티브 가드(순서 뒤바뀜·v1 배치 오적용·차원 불일치 → 즉시 실패)
  7. `/health` 스키마 검증 노출(`feature_schema.status`)

실행:
    python tests/test_feature_schema.py
"""
import sys
import json
from pathlib import Path

# Windows console UTF-8 reconfigure
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import onnxruntime as ort  # noqa: E402

import feature_schema as fs  # noqa: E402
from main import (  # noqa: E402
    FEATURE_ORDER_32,
    KR_HOLIDAYS,
    WeatherInput,
    app,
    build_feature_vector,
    prepare_session_input,
)
from benchmarks.evaluate_models import (  # noqa: E402
    FEATURE_COLS_25,
    FEATURE_COLS_32,
    FEATURE_COLS_32_V1,
    LEGACY_25D_INDICES,
)

SCHEMA_PATH = fs.resolve_schema_path()
LEGACY_INDICES = list(fs.legacy_25d_indices())


def _load_schema() -> dict:
    schema = fs.load_schema()
    assert schema is not None, "feature_schema.json 을 찾지 못했습니다."
    return schema


def test_schema_spec():
    """[Test 1] 스키마 규격 — 차원 == len(feature_cols), 중복 없음, model_version 존재."""
    print("\n[Test 1] feature_schema.json 규격 검증...")
    schema = _load_schema()
    cols = fs.schema_feature_cols(schema)
    print(f"  ✅ 경로: {SCHEMA_PATH.as_posix()}")
    print(f"  ✅ model_version: {schema.get('model_version')} | 차원: {schema.get('feature_dim')}")
    assert schema.get("feature_dim") == len(cols), "feature_dim 과 feature_cols 수가 다릅니다."
    assert len(set(cols)) == len(cols), "feature_cols 에 중복이 있습니다."
    assert schema.get("model_version"), "model_version 이 없습니다."
    print(f"  ✅ 중복 피처 없음 | order={schema.get('order')}")


def test_order_three_way_match():
    """[Test 2] 순서 3자 일치 — 스키마 ↔ main.py ↔ evaluate_models.py."""
    print("\n[Test 2] 피처 순서 3자 일치 검증 (스키마 / main.py / evaluate_models.py)...")
    schema = _load_schema()
    checked = fs.validate_expected_order(schema, FEATURE_ORDER_32, "main.py::FEATURE_ORDER_32")
    assert checked == FEATURE_COLS_32, "main.py 와 evaluate_models.py 의 순서가 다릅니다."
    assert len(FEATURE_COLS_32) == 32, f"32차원이 아닙니다: {len(FEATURE_COLS_32)}"
    print("  ✅ 스키마.feature_cols == main.py::FEATURE_ORDER_32 == evaluate_models.FEATURE_COLS_32 (32차원)")

    # build_feature_vector 가 만드는 실제 벡터 길이도 코드 상수와 일치해야 한다.
    vec = build_feature_vector("강남구", 8, WeatherInput(temp=14.0, rain=2.8, humidity=86.0, wind=3.8))
    assert len(vec) == len(FEATURE_ORDER_32) == 32, f"조립 벡터 차원 불일치: {len(vec)}"
    print(f"  ✅ build_feature_vector 조립 차원: {len(vec)}")


def test_legacy_25d_subset():
    """[Test 3] 25차원 레거시 서브셋 인덱스·명칭 일치 + 서빙 정렬 동작."""
    print("\n[Test 3] 25차원 레거시 서브셋(배포본) 정의 일치 검증...")
    schema = _load_schema()
    assert LEGACY_INDICES == list(LEGACY_25D_INDICES), (
        f"SSoT 인덱스 {LEGACY_INDICES} vs evaluate_models {LEGACY_25D_INDICES}"
    )
    assert fs.legacy_25d_cols(schema) == FEATURE_COLS_25, "25차원 서브셋 피처명이 다릅니다."
    assert len(FEATURE_COLS_25) == 25 and len(LEGACY_INDICES) == 25
    print(f"  ✅ 인덱스 {LEGACY_INDICES}")
    print("  ✅ 피처명 25개 일치 (feature_schema.legacy_25d_cols == FEATURE_COLS_25)")

    # 서빙 정렬 A: 25차원 세션(레거시 서브셋)에는 [17..20]·[27..29] 를 뺀 25개가 순서대로 들어가야 한다.
    #  - 배포 슬롯(models/)이 32차원으로 교체된 뒤에도 이 검증이 유지되도록 **25차원 자산을 직접 지정**한다.
    legacy_asset = ROOT_DIR / "benchmarks" / "original" / "lgb_bike_demand.onnx"
    assert legacy_asset.is_file(), f"25차원 레거시 자산이 없습니다: {legacy_asset}"
    sess25 = ort.InferenceSession(str(legacy_asset), providers=["CPUExecutionProvider"])
    assert int(sess25.get_inputs()[0].shape[1]) == 25
    probe = [float(i) for i in range(32)]
    out25 = prepare_session_input(probe, sess25)
    assert out25.shape == (1, 25), f"25차원 세션 정렬 실패: {out25.shape}"
    assert out25[0].tolist() == [float(i) for i in LEGACY_INDICES], "서브셋 순서가 다릅니다."
    print(f"  ✅ 25차원 세션 정렬 shape={out25.shape} · 자산={legacy_asset.relative_to(ROOT_DIR).as_posix()}")

    # 서빙 정렬 B: 32차원 세션(사양서 배치)에는 32차원 벡터가 **변환 없이 그대로** 전달되어야 한다.
    #  - models/ 를 32차원 자산으로 교체한 뒤의 실제 배포 경로를 그대로 검증한다.
    sess32 = ort.InferenceSession(
        str(ROOT_DIR / "models" / "lgb_bike_demand.onnx"), providers=["CPUExecutionProvider"]
    )
    assert int(sess32.get_inputs()[0].shape[1]) == 32
    out32 = prepare_session_input(probe, sess32)
    assert out32.shape == (1, 32), f"32차원 세션 정렬 실패: {out32.shape}"
    assert out32[0].tolist() == probe, "32차원 벡터가 변환 없이 전달되지 않았습니다."
    print(f"  ✅ 32차원 세션 정렬 shape={out32.shape} (배포 슬롯 = 사양서 배치, 무변환 통과)")


def test_onnx_asset_dims():
    """[Test 4] ONNX 자산 입력 차원 — 배포 슬롯 32(사양서 배치) / 레거시 원본 25 / v1 후보 32."""
    print("\n[Test 4] ONNX 자산 입력 차원 검증...")
    expectations = {
        ROOT_DIR / "models": 32,
        ROOT_DIR / "benchmarks" / "original": 25,
        ROOT_DIR / "benchmarks" / "2026-10-14": 32,
        ROOT_DIR / "benchmarks" / "2026-10-12" / "tuned": 32,
    }
    for folder, expected in expectations.items():
        for mode in ("bike", "bus", "subway"):
            path = folder / f"lgb_{mode}_demand.onnx"
            assert path.is_file(), f"자산이 없습니다: {path}"
            sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            dim = int(sess.get_inputs()[0].shape[1])
            assert dim == expected, f"{path.name} 입력차원 {dim} != 기대 {expected}"
            assert sess.get_inputs()[0].name == "float_input", "입력 이름이 float_input 이 아닙니다."
        print(f"  ✅ {folder.relative_to(ROOT_DIR).as_posix()}: {expected}차원 (3종)")


def test_targets_split_holiday():
    """[Test 5] 타깃 매핑 · 분할 경계 · 공휴일 캘린더 19일."""
    print("\n[Test 5] 타깃 매핑 · 분할 경계 · 공휴일 캘린더 검증...")
    schema = _load_schema()
    targets = fs.validate_targets(
        schema, {"bike": "따릉이_대여", "bus": "버스_승차", "subway": "지하철_승차"}
    )
    split = fs.validate_split_bounds(
        schema, "2025-09-30", "2025-11-15", "2025-11-16", "2025-12-31"
    )
    holidays = sorted({d for days in KR_HOLIDAYS.values() for d in days})
    assert len(holidays) == 19, f"공휴일 캘린더가 19일이 아닙니다: {len(holidays)}"
    print(f"  ✅ targets: {targets}")
    print(f"  ✅ split: {split}")
    print(f"  ✅ 공휴일 캘린더: {len(holidays)}일 (main.py::KR_HOLIDAYS 와 동일)")


def test_negative_guards():
    """[Test 6] 네거티브 가드 — 순서 뒤바뀜 / v1 배치 오적용 / 차원 불일치는 즉시 실패해야 한다."""
    print("\n[Test 6] 네거티브 가드 검증 (실패해야 정상)...")
    schema = _load_schema()

    swapped = list(FEATURE_ORDER_32)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    try:
        fs.validate_expected_order({**schema, "feature_cols": swapped}, FEATURE_ORDER_32, "swapped")
        raise AssertionError("순서가 뒤바뀐 스키마가 통과했습니다.")
    except fs.FeatureSchemaError as exc:
        assert "[0]" in str(exc), f"진단 메시지에 불일치 인덱스가 없습니다: {exc}"
    print("  ✅ 순서 뒤바뀜 스키마 → FeatureSchemaError (인덱스 진단 포함)")

    # v1 배치(25차원 + 상수 0 더미 7)는 v2 스키마와 인덱스 17 이후가 어긋난다.
    assert FEATURE_COLS_32_V1 != FEATURE_COLS_32
    try:
        fs.validate_expected_order(
            schema, FEATURE_COLS_32_V1, "evaluate_models::FEATURE_COLS_32_V1"
        )
        raise AssertionError("v1 배치가 스키마 검증을 통과했습니다.")
    except fs.FeatureSchemaError:
        pass
    print("  ✅ v1 배치(더미 7) ↔ v2 스키마 → FeatureSchemaError (배치 오적용 차단)")

    bad = dict(schema)
    bad["feature_dim"] = len(FEATURE_ORDER_32) + 1
    try:
        fs.schema_feature_cols(bad)
        raise AssertionError("feature_dim 불일치 스키마가 통과했습니다.")
    except fs.FeatureSchemaError:
        pass
    print("  ✅ feature_dim ↔ feature_cols 불일치 → FeatureSchemaError")

    missing = dict(schema)
    missing["targets"] = {"bike": "따릉이_대여"}
    try:
        fs.validate_targets(
            missing, {"bike": "따릉이_대여", "bus": "버스_승차", "subway": "지하철_승차"}
        )
        raise AssertionError("타깃 매핑 불일치가 통과했습니다.")
    except fs.FeatureSchemaError:
        pass
    print("  ✅ targets 매핑 불일치 → FeatureSchemaError")

    try:
        fs.resolve_schema_path(str(ROOT_DIR / "benchmarks" / "does_not_exist.json"))
        raise AssertionError("존재하지 않는 명시 경로가 통과했습니다.")
    except fs.FeatureSchemaError:
        pass
    print("  ✅ 존재하지 않는 --schema 경로 → FeatureSchemaError (조용한 무시 방지)")


def test_health_exposes_schema():
    """[Test 7] `/health` 가 스키마 검증 결과를 노출하는지 확인 (배포 슬롯 = 32차원 자산)."""
    print("\n[Test 7] /health 스키마 검증 노출 확인 (TestClient 기동)...")
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        payload = client.get("/health").json()
    block = payload.get("feature_schema")
    assert block, "/health 응답에 feature_schema 블록이 없습니다."
    assert block.get("feature_dim") == 32, f"feature_dim 이 32가 아닙니다: {block}"
    assert block.get("status") == "verified", (
        f"예상 status 와 다릅니다: {block.get('status')} — 배포 슬롯(ONNX 3종)이 스키마(32차원)와 "
        "정렬되면 verified 입니다. 25차원 자산을 부분 반입했다면 legacy-subset-25d / mixed-32d/25d 가 "
        "정상이므로 이 기대값을 배포 상태에 맞춰 함께 갱신하세요."
    )
    assert set(block.get("model_input_dims", {}).values()) == {32}, "배포 모델 입력차원은 32여야 합니다."
    print(f"  ✅ /health.feature_schema: {json.dumps(block, ensure_ascii=False)}")


def test_deployment_file_list():
    """[Test 8] 컨테이너 배포 파일 목록에 `feature_schema.py`·스키마가 포함됐는지 확인.

    `main.py` 가 `feature_schema` 를 import 하므로 Dockerfile COPY 목록에서 빠지면
    컨테이너 기동이 ImportError 로 실패한다(2026-10-14 실제 발생 → 회귀 방지 테스트).
    """
    print("\n[Test 8] 컨테이너 배포 파일 목록(Dockerfile.backend) 검증...")
    dockerfile = ROOT_DIR / "Dockerfile.backend"
    assert dockerfile.is_file(), "Dockerfile.backend 가 없습니다."
    text = dockerfile.read_text(encoding="utf-8")
    copy_lines = [ln.strip() for ln in text.splitlines() if ln.strip().upper().startswith("COPY")]
    joined = "\n".join(copy_lines)
    assert "feature_schema.py" in joined, f"COPY 목록에 feature_schema.py 누락:\n{joined}"
    assert "benchmarks/2026-10-14/feature_schema.json" in joined, (
        f"COPY 목록에 피처 스키마(SSoT) 누락:\n{joined}"
    )
    print("  ✅ COPY 목록에 feature_schema.py + 피처 스키마(SSoT) 포함")


def run_tests():
    print("=" * 80)
    print("  🧩 [Weather & Transit AI] 피처 스키마(feature_schema.json) SSoT 정합성 검증")
    print("=" * 80)
    test_schema_spec()
    test_order_three_way_match()
    test_legacy_25d_subset()
    test_onnx_asset_dims()
    test_targets_split_holiday()
    test_negative_guards()
    test_health_exposes_schema()
    test_deployment_file_list()
    print("\n" + "=" * 80)
    print("  🎉 피처 스키마 정합성 검증 8종 전부 통과!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_tests()