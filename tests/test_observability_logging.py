import unittest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from in_memory_log_handler import InMemoryLogHandler
from logging_utils import mask_sensitive_text, sanitize_exception
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

    def test_sensitive_info_masking(self):
        """공공 API 키 및 인증 토큰 민감정보 마스킹 검증 (LOGGING_POLICY.md §7)"""
        # 1. 공공데이터포털 serviceKey 마스킹
        url_with_key = "http://ws.bus.go.kr/api/rest/stationinfo?serviceKey=184d553816a7f8e4356e4552548603dd2d51d356797890e549b515f518e8c2b9&tmX=126.97"
        masked_url = mask_sensitive_text(url_with_key)
        self.assertNotIn("184d553816a7f8e4356e4552548603dd2d51d356797890e549b515f518e8c2b9", masked_url)
        self.assertIn("serviceKey=184d****", masked_url)

        # 2. Authorization Bearer 마스킹
        auth_header = "Authorization: Bearer sk-proj-1234567890abcdef"
        masked_auth = mask_sensitive_text(auth_header)
        self.assertNotIn("1234567890abcdef", masked_auth)
        self.assertIn("Bearer sk-p****", masked_auth)

        # 3. 인메모리 링버퍼 emit 시 자동 마스킹 검증
        logger = logging.getLogger("test_masking_logger")
        logger.addHandler(self.handler)
        logger.warning("External API call to %s", url_with_key)
        self.assertTrue(len(self.handler.buffer) > 0)
        last_entry = self.handler.buffer[-1]
        self.assertNotIn("184d553816a7f8e4356e4552548603dd2d51d356797890e549b515f518e8c2b9", last_entry["message"])
        self.assertIn("serviceKey=184d****", last_entry["message"])

    def test_sanitize_exception_empty_and_domain(self):
        """빈 메시지 예외(httpx.ReadTimeout 등) 클래스명 보존 및 도메인 분류 검증"""
        self.assertEqual(sanitize_exception(httpx.ReadTimeout("")), "ReadTimeout")
        self.assertEqual(sanitize_exception(httpx.ConnectTimeout("")), "ConnectTimeout")

        val_msg = sanitize_exception(ValueError("bad url serviceKey=184d553816a7f8e4secret"))
        self.assertIn("ValueError", val_msg)
        self.assertIn("serviceKey=184d****", val_msg)
        self.assertNotIn("184d553816a7f8e4secret", val_msg)

        # 새 간결 로그 문자열이 의도한 도메인 배지로 분류되는지 확인
        self.assertEqual(
            self.handler._detect_domain(
                "weather_transit_api.kma_forecast",
                "KMA Grid [PCP] 2026111823 error: ReadTimeout (기존 예보 폴백)",
            ),
            "기상청",
        )
        self.assertEqual(
            self.handler._detect_domain(
                "weather_transit_api",
                "Seoul Bus API error: ReadTimeout (스냅샷/배차 폴백)",
            ),
            "버스",
        )
        self.assertEqual(
            self.handler._detect_domain(
                "weather_transit_api",
                "Seoul Subway API error: ReadTimeout (배차 폴백)",
            ),
            "지하철",
        )
        self.assertEqual(
            self.handler._detect_domain(
                "weather_transit_api",
                "Seoul bike API error: ReadTimeout (스냅샷 폴백)",
            ),
            "따릉이",
        )

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

    def test_admin_dashboard_and_status_stage2(self):
        """관리자 대시보드(/health/dashboard) 및 /api/v1/admin/status에 Stage 1(32d)·Stage 2(16d) 표시 검증"""
        dash_resp = self.client.get("/health/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        html = dash_resp.text
        self.assertIn("Stage 1 (자치구)", html)
        self.assertIn("Stage 2 (지점별)", html)
        self.assertIn("32d×16d Verified", html)
        self.assertIn("point-share-loaded-text", html)

        status_resp = self.client.get("/api/v1/admin/status")
        self.assertEqual(status_resp.status_code, 200)
        st = status_resp.json()
        self.assertIn("models_loaded", st)
        self.assertIn("point_share_models", st)
        self.assertIn("point_counts", st["point_share_models"])

    def test_nearby_bus_header_4_returns_info_no_warning(self):
        """서울 버스 getStationByPos 결과 없음(headerCd=4) 시 WARNING 대신 INFO 및 status=success 반환 검증"""
        mock_res = MagicMock()
        mock_res.raise_for_status = MagicMock()
        mock_res.json.return_value = {
            "msgHeader": {"headerCd": "4", "headerMsg": "결과가 없습니다."},
            "msgBody": {"itemList": None},
        }
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_res

        with patch.object(main, "DATA_GO_KR_BUS_KEY", "test-dummy-bus-key"), \
             patch("httpx.AsyncClient", return_value=mock_client), \
             self.assertLogs("weather_transit_api", level="INFO") as cm:
            resp = self.client.get(
                "/api/v1/transit/bus/stations/nearby?lat=37.4000&lng=127.1000&radius=600"
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["source"], "SEOUL_BUS_NO_DATA")
        self.assertEqual(data["stations"], [])
        self.assertFalse(any("WARNING" in msg for msg in cm.output))
        self.assertTrue(any("getStationByPos 결과 없음 (4:" in msg for msg in cm.output))


if __name__ == "__main__":
    unittest.main()
