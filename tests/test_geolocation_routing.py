import unittest
from fastapi.testclient import TestClient

import main
from multimodal_router import multimodal_routing_engine


class TestGeolocationRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.registry.load_models()
        cls.client = TestClient(main.app)

    def test_resolve_station_with_gps(self):
        """GPS 좌표와 함께 '내 위치 (GPS)' 쿼리를 넘겼을 때 gps 거점 타입과 인접 지하철역이 매핑되어야 함"""
        gangnam_coords = [127.0276, 37.4979]
        res = multimodal_routing_engine.resolve_station(
            query="내 위치 (GPS)",
            coords=gangnam_coords,
            station_type="gps",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["station_type"], "gps")
        self.assertEqual(res["name"], "내 위치 (GPS)")
        self.assertEqual(res["coords"], gangnam_coords)
        self.assertIsNotNone(res.get("nearest_subway"))
        self.assertIn("강남", res["nearest_subway"]["name"])

    def test_resolve_station_district_from_gps_coords(self):
        """내 위치 쿼리와 좌표 입력 시 해당 좌표에 가장 인접한 자치구로 자동 역지오코딩되어야 함"""
        samseong_coords = [127.0631, 37.5088]  # 삼성역/강남구
        district = multimodal_routing_engine.resolve_station_district(
            station_name="내 위치 (GPS)",
            coords=samseong_coords,
        )
        self.assertEqual(district, "강남구")

        ydp_coords = [126.8963, 37.5264]  # 영등포구청/영등포구
        district_yd = multimodal_routing_engine.resolve_station_district(
            station_name="현재 위치",
            coords=ydp_coords,
        )
        self.assertEqual(district_yd, "영등포구")

    def test_multimodal_search_from_gps_origin(self):
        """내 위치(GPS)에서 목적지(시청역)로 경로 검색 시 First-Mile 도보 세그먼트가 포함되어야 함"""
        gangnam_coords = [127.0276, 37.4979]
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="내 위치 (GPS)",
            to_query="시청역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.5, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
            from_coords=gangnam_coords,
            from_type="gps",
        )
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(len(res["routes"]), 1)

        # 최소한 지하철 경로에서 출발지('내 위치 (GPS)')에서 인접 역('강남역')까지의 도보 세그먼트 확인
        subway_route = next((r for r in res["routes"] if r["id"] == "route-subway-optimal"), None)
        self.assertIsNotNone(subway_route)
        first_seg = subway_route["segments"][0]
        self.assertEqual(first_seg["mode"], "walk")
        self.assertIn("내 위치", first_seg["from_name"])
        self.assertIn("강남", first_seg["to_name"])

    def test_multimodal_api_endpoint_with_gps(self):
        """POST /api/v1/routes/multimodal-search API로 GPS 출발지 요청 시 200 OK 응답 검증"""
        payload = {
            "from_station": "내 위치 (GPS)",
            "to_station": "서울역",
            "from_coords": [127.0276, 37.4979],
            "from_type": "gps",
            "district": "강남구",
            "hour": 15,
        }
        res = self.client.post("/api/v1/routes/multimodal-search", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("routes", data)
        self.assertGreater(len(data["routes"]), 0)


if __name__ == "__main__":
    unittest.main()
