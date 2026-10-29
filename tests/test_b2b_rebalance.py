import unittest
from fastapi.testclient import TestClient
from main import app, registry

class TestB2BFleetRebalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry.load_models()

    def test_b2b_rebalance_endpoint_rain(self):
        client = TestClient(app)
        # 1. 우천(Rain = 5.0mm) 조건 테스트
        payload = {
            "hour": 9,
            "rain_mm": 5.0,
            "temp": 15.0,
            "use_live_weather": False
        }
        res = client.post("/api/v1/b2b/fleet-rebalance", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["latency_ms"] > 0)
        self.assertEqual(len(data["district_rebalance_list"]), 25)
        # 우천 시 따릉이 회수 권고 수량이 존재해야 함
        self.assertTrue(data["total_bike_surplus_qty"] > 0)
        # 상위 회수 구역 목록 검증
        self.assertTrue(len(data["top_recall_districts"]) > 0)
        first_recall = data["top_recall_districts"][0]
        self.assertTrue(first_recall["qty"] > 0)
        print(f"B2B 우천 테스트 성공: 지연시간 {data['latency_ms']}ms, 총 회수 권고 {data['total_bike_surplus_qty']}대")

    def test_b2b_rebalance_endpoint_clear(self):
        client = TestClient(app)
        # 2. 맑은 날(Rain = 0.0mm) 피크시간대(18시) 테스트
        payload = {
            "hour": 18,
            "rain_mm": 0.0,
            "temp": 20.0,
            "use_live_weather": False
        }
        res = client.post("/api/v1/b2b/fleet-rebalance", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["district_rebalance_list"]), 25)
        print(f"B2B 맑은 날 테스트 성공: 지연시간 {data['latency_ms']}ms, 버스 배차 {data['total_bus_extra_trips']}회")

if __name__ == "__main__":
    unittest.main()

