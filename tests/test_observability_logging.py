import unittest
from in_memory_log_handler import InMemoryLogHandler
from fastapi.testclient import TestClient
import main
from multimodal_router import multimodal_routing_engine


class TestObservabilityAndGracefulDegradation(unittest.TestCase):
    def setUp(self):
        self.handler = InMemoryLogHandler()
        self.client = TestClient(main.app)

    def test_domain_detection_accuracy(self):
        """도메인 오분류(시스템명 'weather'로 인한 기상청 쏠림) 교정 검증"""
        # 1. 버스 관련 에러
        d1 = self.handler._detect_domain(
            "weather_transit_api",
            "Nearby bus station API error: Server error '503 Service Temporarily Unavailable' for url 'http://ws.bus.go.kr/api/rest/stationinfo/getStationByPos'"
        )
        self.assertEqual(d1, "버스")

        # 2. 서킷브레이커 오픈
        d2 = self.handler._detect_domain(
            "weather_transit_api",
            "[CircuitBreaker:SEOUL_BUS] 연속 실패 3회 발생! 서킷을 OPEN 상태로 차단합니다"
        )
        self.assertEqual(d2, "서킷브레이커")

        # 3. LangGraph 멀티모달
        d3 = self.handler._detect_domain(
            "weather-transit-backend.multimodal",
            "fetch_public_transit_transfer_routes error: HTTPConnectionPool"
        )
        self.assertEqual(d3, "LangGraph")

        # 4. 순수 기상청
        d4 = self.handler._detect_domain(
            "weather_transit_api",
            "기상청 API허브 초단기실황 조회 완료 (temp: 14.5°C)"
        )
        self.assertEqual(d4, "기상청")

    def test_nearby_bus_stations_graceful_degradation(self):
        """서울시 버스 API 일시 장애/서킷 오픈 시 502 에러가 아닌 200 OK 빈 목록 Fallback 검증"""
        resp = self.client.get(
            "/api/v1/transit/bus/stations/nearby?lat=37.5000&lng=127.0270&radius=500"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn("stations", data)
        self.assertIsInstance(data["stations"], list)

    def test_factchat_fallback_reason_in_trace(self):
        """FactChat LLM Fallback 시 langgraph_trace 및 ai_briefing에 fallback_reason 전달 검증"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="역삼역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.0, "rain": 0.0, "wind": 1.5, "bike_enabled": True},
            ai_congestion={"subway_crowd": 55, "bus_crowd": 50, "bike_crowd": 30},
        )
        self.assertEqual(res["status"], "success")
        briefing = res.get("ai_briefing") or {}
        trace = res.get("langgraph_trace") or []

        # 4단계 FactChat 노드 트레이스 확인
        fc_step = next((t for t in trace if t.get("node") == "factchat_llm_briefing_node"), None)
        self.assertIsNotNone(fc_step)
        self.assertIn("fallback_reason", fc_step)
        self.assertIn("fallback_reason", briefing)


if __name__ == "__main__":
    unittest.main()
