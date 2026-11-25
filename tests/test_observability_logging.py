import unittest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from in_memory_log_handler import InMemoryLogHandler
from logging_utils import mask_sensitive_text, sanitize_exception, SensitiveInfoMaskingFilter
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

        # 4. 서울 열린데이터광장 지하철·따릉이 URL 경로 내 API 키 마스킹 (Issue #144 SEC-05)
        subway_url = "http://swopenAPI.seoul.go.kr/api/subway/1234567890abcdef/json/realtimeStationArrival/0/16/%EA%B0%95%EB%82%A8"
        masked_subway = mask_sensitive_text(subway_url)
        self.assertNotIn("1234567890abcdef", masked_subway)
        self.assertIn("/api/subway/1234****/json/", masked_subway)

        bike_url = "http://openapi.seoul.go.kr:8088/abcd1234efgh5678/json/bikeList/1/1000/"
        masked_bike = mask_sensitive_text(bike_url)
        self.assertNotIn("abcd1234efgh5678", masked_bike)
        self.assertIn(":8088/abcd****/json/bikeList/", masked_bike)

        # 5. 루트/콘솔 핸들러 필터(SensitiveInfoMaskingFilter) 동작 검증
        rec = logging.LogRecord(
            name="httpx",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="HTTP Request: GET %s",
            args=(subway_url,),
            exc_info=None,
        )
        self.assertTrue(SensitiveInfoMaskingFilter().filter(rec))
        self.assertNotIn("1234567890abcdef", rec.getMessage())
        self.assertIn("/api/subway/1234****/json/", rec.getMessage())

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

    def test_phase2a_bounded_cache_and_input_validation(self):
        """Phase 2-A 인메모리 캐시 상한(LRU/FIFO 퇴거) 및 Pydantic 입력 상한 검증"""
        store = {}
        main._bounded_cache_set(store, "k1", 1, max_size=2)
        main._bounded_cache_set(store, "k2", 2, max_size=2)
        main._bounded_cache_set(store, "k3", 3, max_size=2)
        self.assertEqual(list(store.keys()), ["k2", "k3"])

        r_dist = self.client.post(
            "/api/v1/predict/recommendation",
            json={"district": "가" * 100, "hour": 8},
        )
        self.assertEqual(r_dist.status_code, 422)

        huge_items = [
            {"id": f"s{i}", "name": "강남역", "stop_type": "subway", "district": "강남구"}
            for i in range(3001)
        ]
        r_batch = self.client.post(
            "/api/v1/predict/map-crowds",
            json={"hour": 8, "items": huge_items},
        )
        self.assertEqual(r_batch.status_code, 422)


if __name__ == "__main__":
    unittest.main()
