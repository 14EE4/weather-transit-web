import unittest

from services.circuit_breaker import CircuitBreaker
from services.factchat_briefing import FactChatBriefingService
from services.mcda_evaluator import (
    MODE_EVALUATORS,
    evaluate_mode,
    evaluate_subway,
    get_score_meta,
)


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class TestSolidPhase3(unittest.TestCase):
    def test_circuit_breaker_state_transitions(self):
        cb = CircuitBreaker("TEST_API", failure_threshold=2, recovery_timeout=0.0)
        self.assertEqual(cb.state, "CLOSED")
        self.assertTrue(cb.can_execute())

        cb.record_failure("timeout 1")
        self.assertEqual(cb.state, "CLOSED")
        cb.record_failure("timeout 2")
        self.assertEqual(cb.state, "OPEN")

        # recovery_timeout=0.0이므로 즉시 HALF_OPEN 프로빙 허용
        self.assertTrue(cb.can_execute())
        self.assertEqual(cb.state, "HALF_OPEN")

        cb.record_success()
        self.assertEqual(cb.state, "CLOSED")

    def test_mcda_evaluator_registry_ocp(self):
        self.assertEqual(set(MODE_EVALUATORS.keys()), {"subway", "bus", "bike"})
        import main  # ensure configure_mcda_context has been called

        self.assertEqual(
            evaluate_mode("subway", 25000, 0.0, "강남구"),
            evaluate_subway(25000, 0.0, "강남구"),
        )
        self.assertEqual(get_score_meta("subway", 90)[0], "최우선 추천")
        with self.assertRaises(ValueError):
            evaluate_mode("hyperloop", 1000, 0.0, "강남구")

    def test_factchat_briefing_service_dip(self):
        # 1) API 키가 없으면 네트워크 호출 없이 XAI 폴백
        calls = []

        def fake_post(*args, **kwargs):
            calls.append((args, kwargs))
            return _DummyResponse(
                200,
                {"choices": [{"message": {"content": "테스트 LLM 브리핑 응답입니다."}}]},
            )

        svc_no_key = FactChatBriefingService(api_key="", http_post=fake_post)
        briefing, status, _ = svc_no_key.generate_briefing(
            origin={"name": "강남역"},
            dest={"name": "홍대입구역"},
            w_ctx={"rain": 0.0, "temp": 20.0},
            ai_cong={"subway_crowd": 50, "bus_crowd": 45},
            routes=[{"id": "r1", "title": "2호선 직통", "total_minutes": 30, "total_fare_krw": 1400, "transfer_count": 0, "crowd_percent": 50, "comfort_score": 85}],
        )
        self.assertEqual(status, "XAI_RULE_ENGINE")
        self.assertEqual(briefing["source"], "LANGGRAPH_XAI_ENGINE")
        self.assertEqual(len(calls), 0)

        # 2) 유효한 키 + 200 응답 시 주입된 http_post 호출 및 캐싱
        svc_live = FactChatBriefingService(
            api_key="test-valid-key-1234567890",
            model_name="gpt-6-luna",
            http_post=fake_post,
        )
        b1, s1, _ = svc_live.generate_briefing(
            origin={"name": "강남역"},
            dest={"name": "홍대입구역"},
            w_ctx={"rain": 0.0, "temp": 20.0},
            ai_cong={"subway_crowd": 50, "bus_crowd": 45},
            routes=[{"id": "r1", "title": "2호선 직통", "total_minutes": 30, "total_fare_krw": 1400, "transfer_count": 0, "crowd_percent": 50, "comfort_score": 85}],
        )
        self.assertEqual(s1, "FACTCHAT_LLM_LIVE")
        self.assertEqual(b1["summary"], "테스트 LLM 브리핑 응답입니다.")
        self.assertEqual(len(calls), 1)

        # 동일 요청은 캐시 히트
        _, s2, _ = svc_live.generate_briefing(
            origin={"name": "강남역"},
            dest={"name": "홍대입구역"},
            w_ctx={"rain": 0.0, "temp": 20.0},
            ai_cong={"subway_crowd": 50, "bus_crowd": 45},
            routes=[{"id": "r1", "title": "2호선 직통", "total_minutes": 30, "total_fare_krw": 1400, "transfer_count": 0, "crowd_percent": 50, "comfort_score": 85}],
        )
        self.assertEqual(s2, "FACTCHAT_BAZE_GATEWAY")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
