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

import main as app_main  # noqa: E402
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
    with TestClient(app_main.app) as client:
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


def test_predict_points_batch_matches_single_point():
    if not point_share_engine.is_loaded:
        assert point_share_engine.load() is True

    district_volumes = {
        "강남구": {"subway": 48000.0, "bus": 15000.0, "bike": 350.0},
        "서초구": {"subway": 25000.0, "bus": 12000.0, "bike": 220.0},
        "중구": {"subway": 32000.0, "bus": 11000.0, "bike": 180.0},
    }
    items = [
        {"id": "sub-gn", "name": "강남역", "stop_type": "subway", "district": "강남구", "base_crowd": 84},
        {"id": "sub-gd", "name": "교대역", "stop_type": "subway", "district": "서초구", "base_crowd": 85},
        {"id": "sub-hy", "name": "학여울역", "stop_type": "subway", "district": "강남구", "base_crowd": 53},
        {"id": "bus-sr", "name": "서울역버스환승센터", "stop_type": "bus", "district": "중구", "point_id": "101000003", "base_crowd": 85},
        {"id": "bike-hd", "name": "현대고등학교 건너편", "stop_type": "bike", "district": "강남구", "point_id": "2301", "base_crowd": 70},
    ]
    batch = point_share_engine.predict_points_batch(
        items=items,
        district_volumes=district_volumes,
        hour=15,
        temp=14.0,
        rain=0.0,
        wind=2.0,
        humidity=55.0,
    )
    assert len(batch) == len(items)
    for it in items:
        single = point_share_engine.predict_point(
            mode=it["stop_type"],
            district=it["district"],
            hour=15,
            temp=14.0,
            rain=0.0,
            wind=2.0,
            humidity=55.0,
            district_volume=district_volumes[it["district"]][it["stop_type"]],
            station_name=it["name"],
            point_id=it.get("point_id"),
            base_crowd=it.get("base_crowd"),
        )
        assert single is not None
        assert batch[it["id"]]["crowd"] == single["crowd"]
        assert batch[it["id"]]["predicted_volume"] == single["predicted_volume"]
        assert batch[it["id"]]["point_share_pct"] == single["point_share_pct"]
    print("[Test 5] predict_points_batch == predict_point 100% 일치 PASS")


def test_map_crowds_batch_endpoint_and_shared_cache():
    app_main._map_crowds_cache.clear()
    with TestClient(app_main.app) as client:
        req_payload = {
            "hour": 15,
            "weather": {"temp": 14.0, "rain": 0.0, "humidity": 55.0, "wind": 2.0},
            "items": [
                {"id": "sub-1002000222", "name": "강남역", "stop_type": "subway", "district": "강남구", "base_crowd": 84},
                {"id": "sub-1002000223", "name": "교대역", "stop_type": "subway", "district": "서초구", "base_crowd": 85},
                {"id": "sub-1003000346", "name": "학여울역", "stop_type": "subway", "district": "강남구", "base_crowd": 53},
            ],
        }
        r1 = client.post("/api/v1/predict/map-crowds", json=req_payload)
        assert r1.status_code == 200
        j1 = r1.json()
        assert j1["status"] == "success"
        assert j1["cache_hit"] is False
        assert j1["computed_count"] == 3
        assert j1["total_cached_in_slot"] == 3
        assert j1["items"]["sub-1002000222"]["crowd"] > j1["items"]["sub-1003000346"]["crowd"]
        assert j1["items"]["sub-1002000223"]["crowd"] > j1["items"]["sub-1003000346"]["crowd"]

        # 다른 사용자가 동일 시간대·유사 기온으로 접속 시 서버 캐시 즉시 적중 확인
        req_payload_user2 = {
            "hour": 15,
            "weather": {"temp": 14.4, "rain": 0.0, "humidity": 58.0, "wind": 2.2},
            "items": req_payload["items"],
        }
        r2 = client.post("/api/v1/predict/map-crowds", json=req_payload_user2)
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2["cache_hit"] is True
        assert j2["computed_count"] == 0
        assert j2["cache_key"] == j1["cache_key"]
        assert j2["items"] == j1["items"]
        print(
            f"[Test 6] /api/v1/predict/map-crowds 배치 추론 & 공용 캐시 PASS: "
            f"강남={j1['items']['sub-1002000222']} | 교대={j1['items']['sub-1002000223']} | "
            f"학여울={j1['items']['sub-1003000346']} | User2 cache_hit={j2['cache_hit']} ({j2['latency_ms']}ms)"
        )


def main():
    test_engine_load_and_status()
    test_same_district_differentiation()
    test_transfer_bus_bike_matching()
    test_fastapi_endpoints()
    test_predict_points_batch_matches_single_point()
    test_map_crowds_batch_endpoint_and_shared_cache()
    print("\nALL STAGE 2 POINT-SHARE SERVING TESTS PASSED!")


if __name__ == "__main__":
    main()
