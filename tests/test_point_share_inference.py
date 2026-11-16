# -*- coding: utf-8 -*-
"""
Stage 2 지점 점유율 분해 추론 엔진(`point_share_inference.py`) 및 FastAPI 통합 검증 테스트

실행:
    .\venv\Scripts\python.exe tests/test_point_share_inference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from point_share_inference import FEATURE_ORDER_POINT_16, point_share_engine  # noqa: E402


def test_engine_load_and_status():
    ok = point_share_engine.load()
    assert ok is True, "Stage 2 PointShareEngine 로드 실패"
    rep = point_share_engine.status_report()
    assert rep["loaded"] is True
    assert rep["schema_status"] == "verified"
    assert rep["feature_dim"] == len(FEATURE_ORDER_POINT_16) == 16
    assert rep["model_input_dims"] == {"bike": 16, "bus": 16, "subway": 16}
    assert rep["point_counts"]["subway"] >= 250
    assert rep["point_counts"]["bus"] >= 5000
    assert rep["point_counts"]["bike"] >= 2000
    print("[Test 1] PointShareEngine 로드 및 상태 검증 PASS:", rep)


def test_same_district_differentiation():
    gn = point_share_engine.predict_point(
        mode="subway",
        district="강남구",
        hour=18,
        temp=16.0,
        rain=0.0,
        wind=2.0,
        humidity=50.0,
        district_volume=48000,
        station_name="강남역",
    )
    hy = point_share_engine.predict_point(
        mode="subway",
        district="강남구",
        hour=18,
        temp=16.0,
        rain=0.0,
        wind=2.0,
        humidity=50.0,
        district_volume=48000,
        station_name="학여울역",
    )
    assert gn is not None and hy is not None
    assert gn["inference_tier"] == "POINT_EXACT_ONNX"
    assert hy["inference_tier"] == "POINT_EXACT_ONNX"
    assert gn["point_share_pct"] > hy["point_share_pct"] * 5.0
    assert gn["predicted_volume"] > hy["predicted_volume"] * 5.0
    assert gn["crowd"] > hy["crowd"]
    print(f"[Test 2] 동일 자치구 역별 차별화 PASS: 강남={gn} | 학여울={hy}")


def test_transfer_bus_bike_matching():
    js = point_share_engine.predict_point(
        mode="subway",
        district="송파구",
        hour=8,
        temp=14.0,
        rain=0.0,
        wind=2.0,
        humidity=55.0,
        district_volume=30000,
        station_name="잠실역",
    )
    assert js is not None
    assert js["inference_tier"] == "POINT_EXACT_ONNX"
    assert js["matched_point_id"] == "2호선_216,8호선_2815"

    bus_pt = point_share_engine.predict_point(
        mode="bus",
        district="중구",
        hour=8,
        temp=14.0,
        rain=0.0,
        wind=2.0,
        humidity=55.0,
        district_volume=11000,
        station_name="서울역버스환승센터",
        point_id="101000003",
    )
    assert bus_pt is not None
    assert bus_pt["inference_tier"] == "POINT_EXACT_ONNX"
    assert bus_pt["matched_point_id"] == "101000003"

    bike_pt = point_share_engine.predict_point(
        mode="bike",
        district="강남구",
        hour=18,
        temp=18.0,
        rain=0.0,
        wind=2.0,
        humidity=50.0,
        district_volume=350,
        station_name="현대고등학교 건너편",
        point_id="2301",
    )
    assert bike_pt is not None
    assert bike_pt["inference_tier"] == "POINT_EXACT_ONNX"
    assert bike_pt["matched_point_id"] == "2301"
    print(f"[Test 3] 환승역·버스(stId)·따릉이(stationNo) 매칭 PASS: 잠실={js['matched_point_id']} | 버스={bus_pt['predicted_volume']} | 따릉이={bike_pt['predicted_volume']}")


def test_fastapi_endpoints():
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        h_json = h.json()
        assert h_json["feature_schema"]["status"] == "verified"
        assert h_json["feature_schema"]["model_input_dims"] == {"bike": 32, "bus": 32, "subway": 32}
        assert h_json["point_share_models"]["loaded"] is True
        assert h_json["point_share_models"]["schema_status"] == "verified"

        r_gn = client.post(
            "/api/v1/predict/recommendation",
            json={
                "district": "강남구",
                "station": "강남역",
                "stop_type": "subway",
                "base_crowd": 88,
                "hour": 18,
                "weather": {"temp": 16.0, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
            },
        )
        assert r_gn.status_code == 200
        j_gn = r_gn.json()
        sub_gn = next(item for item in j_gn["recommendations"] if item["id"] == "subway")

        r_hy = client.post(
            "/api/v1/predict/recommendation",
            json={
                "district": "강남구",
                "station": "학여울역",
                "stop_type": "subway",
                "base_crowd": 30,
                "hour": 18,
                "weather": {"temp": 16.0, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
            },
        )
        assert r_hy.status_code == 200
        j_hy = r_hy.json()
        sub_hy = next(item for item in j_hy["recommendations"] if item["id"] == "subway")

        assert sub_gn["inference_tier"] == "POINT_EXACT_ONNX"
        assert sub_hy["inference_tier"] == "POINT_EXACT_ONNX"
        assert sub_gn["point_share_pct"] > sub_hy["point_share_pct"]
        assert sub_gn["predicted_volume"] > sub_hy["predicted_volume"]
        assert sub_gn["district_predicted_volume"] >= sub_gn["predicted_volume"]
        assert "지점 점유율" in sub_gn["reasons"][0]
        print(
            f"[Test 4] FastAPI /health & /predict/recommendation PASS: "
            f"강남역={sub_gn['predicted_volume']}명 ({sub_gn['point_share_pct']}%, 혼잡 {sub_gn['crowd']}%) vs "
            f"학여울역={sub_hy['predicted_volume']}명 ({sub_hy['point_share_pct']}%, 혼잡 {sub_hy['crowd']}%)"
        )


def main():
    test_engine_load_and_status()
    test_same_district_differentiation()
    test_transfer_bus_bike_matching()
    test_fastapi_endpoints()
    print("\nALL STAGE 2 POINT-SHARE SERVING TESTS PASSED!")


if __name__ == "__main__":
    main()
