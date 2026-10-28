import unittest
from fastapi.testclient import TestClient

import main
from multimodal_router import multimodal_routing_engine


class TestMultimodalRoutingEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.registry.load_models()
        cls.client = TestClient(main.app)

    def test_clear_weather_enables_bike_first_mile(self):
        """맑은 날(rain=0.0) 호출 시 Weather Gate가 CLEAR_MULTIMODAL로 분기하고 따릉이 복합 후보 생성 및 합리적 효용 정렬을 수행해야 함"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="서울역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.5, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["weather_gate"], "CLEAR_MULTIMODAL")
        self.assertTrue(res["weather_context"]["bike_enabled"])
        self.assertGreaterEqual(len(res["routes"]), 3)
        top_route = res["routes"][0]
        self.assertTrue(top_route["is_ai_recommended"])
        self.assertTrue(any("bike" in r["modes_used"] for r in res["routes"]))
        self.assertEqual(len(res["langgraph_trace"]), 4)

        # 서울역 -> 홍대입구역처럼 공항철도 무환승 직통(7분, 1,550원)이 따릉이 복합(19분, 2,550원)보다 압도적으로 유리한 경우 직통 지하철이 1순위로 선정되어야 함
        seoul_hongdae = multimodal_routing_engine.run_multimodal_search(
            from_query="서울역",
            to_query="홍대입구역",
            district="용산구",
            hour=15,
            weather_context={"temp": 5.7, "rain": 0.0, "humidity": 40.0, "wind": 2.0},
        )
        self.assertEqual(seoul_hongdae["routes"][0]["id"], "route-subway-optimal")
        self.assertTrue(seoul_hongdae["routes"][0]["is_ai_recommended"])

        # 단거리(강남역 -> 역삼역) 맑은 날에는 따릉이 논스톱 에코 라이딩이 1순위로 선정되어야 함
        short_trip = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="역삼역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.5, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
        )
        self.assertEqual(short_trip["routes"][0]["id"], "route-ai-bike-direct")
        self.assertTrue(short_trip["routes"][0]["is_ai_recommended"])

    def test_rainy_weather_blocks_bike_via_weather_gate(self):
        """우천 시(rain=10.5mm) Weather Gate가 RAIN_SAFE_ONLY로 분기하여 따릉이(PM) 후보를 자동 배제해야 함"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="서울역",
            district="강남구",
            hour=18,
            weather_context={"temp": 13.0, "rain": 10.5, "humidity": 85.0, "wind": 4.5},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["weather_gate"], "RAIN_SAFE_ONLY")
        self.assertFalse(res["weather_context"]["bike_enabled"])
        for route in res["routes"]:
            self.assertNotIn("bike", route["modes_used"])
        summary = res["ai_briefing"]["summary"]
        self.assertTrue(
            any(kw in summary for kw in ("강수", "비", "우천", "따릉이", "지하철")),
            f"Unexpected briefing summary: {summary}",
        )

    def test_fastapi_post_and_get_multimodal_endpoints(self):
        """FastAPI POST 및 GET /api/v1/routes/multimodal-search 엔드포인트 스키마 및 32D ONNX 연동 검증"""
        post_resp = self.client.post(
            "/api/v1/routes/multimodal-search",
            json={
                "from_station": "홍대입구역",
                "to_station": "여의도역",
                "district": "마포구",
                "hour": 9,
                "weather": {"temp": 17.0, "rain": 0.0, "humidity": 55.0, "wind": 2.0},
            },
        )
        self.assertEqual(post_resp.status_code, 200)
        data = post_resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["origin"]["name"], "홍대입구역")
        self.assertEqual(data["destination"]["name"], "여의도역")
        self.assertIn("ai_briefing", data)
        self.assertIn("routes", data)
        self.assertGreater(len(data["routes"]), 0)

        get_resp = self.client.get(
            "/api/v1/routes/multimodal-search?from_station=잠실역&to_station=건대입구역&district=송파구&hour=19&rain=8.0&temp=14.0"
        )
        self.assertEqual(get_resp.status_code, 200)
        g_data = get_resp.json()
        self.assertEqual(g_data["weather_gate"], "RAIN_SAFE_ONLY")
        self.assertFalse(g_data["weather_context"]["bike_enabled"])

    def test_no_origin_backtracking_in_first_mile(self):
        """서울역 등 환승 거점에서 출발 시 따릉이 First-Mile 이후 지하철이 다시 출발역(서울역)으로 되돌아오는 제자리걸음이 없어야 함"""
        for dest in ["강남역", "홍대입구역", "여의도역", "구로역"]:
            res = multimodal_routing_engine.run_multimodal_search(
                from_query="서울역",
                to_query=dest,
                district="용산구",
                hour=9,
                weather_context={"temp": 18.0, "rain": 0.0, "humidity": 50.0, "wind": 1.5},
            )
            for route in res["routes"]:
                if "bike" in route["modes_used"] and "subway" in route["modes_used"]:
                    subway_segs = [s for s in route["segments"] if s["mode"] == "subway"]
                    for seg in subway_segs:
                        self.assertNotEqual(
                            seg["to_name"],
                            "서울역",
                            f"Backtracking to 서울역 detected in {route['title']} -> {seg}",
                        )
                        self.assertNotEqual(
                            seg["from_name"],
                            "서울역",
                            f"Circular return to 서울역 detected in {route['title']} -> {seg}",
                        )

    def test_non_seoul_origin_excludes_bike_and_no_distant_jump(self):
        """서울 외 지역(예: 송내역, 부평역, 수원역) 출발 시 따릉이(서울시 전용)가 자동 배제되고 원거리 점프 직선이 없어야 함"""
        for origin_q, dest_q in [("송내역", "중동역"), ("부평역", "홍대입구역"), ("수원역", "강남역")]:
            res = multimodal_routing_engine.run_multimodal_search(
                from_query=origin_q,
                to_query=dest_q,
                district="구로구",
                hour=15,
                weather_context={"temp": 18.0, "rain": 0.0, "humidity": 45.0, "wind": 1.8},
            )
            self.assertEqual(res["status"], "success")
            self.assertFalse(res["weather_context"]["origin_in_seoul"])
            self.assertFalse(res["weather_context"]["bike_enabled"])
            for r in res["routes"]:
                self.assertNotIn("bike", r["modes_used"])
                for seg in r["segments"]:
                    self.assertNotIn("서울식물원", seg.get("to_name", ""))
                    self.assertNotIn("서울식물원", seg.get("from_name", ""))


if __name__ == "__main__":
    unittest.main()

