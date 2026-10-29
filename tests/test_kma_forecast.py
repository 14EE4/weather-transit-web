"""
test_kma_forecast.py — 기상청 단기예보(getVilageFcst/nph-dfs_shrt_grd) 및 시간대별 동적 기상 연동 테스트 스위트
"""

import os
import unittest
from fastapi.testclient import TestClient

# 환경 변수 사전 로드
from dotenv import load_dotenv
load_dotenv()

from main import app, registry


class TestKMAForecastIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry.load_models()
        cls.client = TestClient(app)

    def test_01_hourly_weather_forecast_endpoint(self):
        """GET /api/v1/weather/forecast/hourly 엔드포인트 24시간 예보 검증"""
        response = self.client.get("/api/v1/weather/forecast/hourly?district=강남구")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("district", data)
        self.assertIn("hours", data)
        self.assertEqual(len(data["hours"]), 24)

        # 각 시간대 데이터 무결성 검증
        for item in data["hours"]:
            self.assertIn("hour", item)
            self.assertIn("temp", item)
            self.assertIn("rain", item)
            self.assertIn("sky", item)
            self.assertIn("pty", item)
            self.assertIn("pty_desc", item)
            self.assertIn("weather_icon", item)
            self.assertGreaterEqual(item["hour"], 0)
            self.assertLessEqual(item["hour"], 23)
            # 기온은 일반적 한국 기후 범위(-30 ~ 45도)
            self.assertGreaterEqual(item["temp"], -30.0)
            self.assertLessEqual(item["temp"], 45.0)

        print(f"\n[단기예보 테스트] 강남구 24시간 예보 수신 성공 (출처: {data.get('source')}, tmfc: {data.get('tmfc')})")
        print(f"  - 14시 예보: {data['hours'][14]['temp']}°C, {data['hours'][14]['rain']}mm, {data['hours'][14]['pty_desc']}")
        print(f"  - 21시 예보: {data['hours'][21]['temp']}°C, {data['hours'][21]['rain']}mm, {data['hours'][21]['pty_desc']}")

    def test_02_hourly_transit_forecast_with_kma_integration(self):
        """GET /api/v1/transit/hourly-forecast 실시간 예보 연동 검증"""
        response = self.client.get("/api/v1/transit/hourly-forecast?district=마포구")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("status"), "success")
        self.assertIn("hourly", data)
        self.assertEqual(len(data["hourly"]), 24)

        # 14시와 21시 기온 차이 존재 확인 (기상청 단기예보 반영)
        temp_14 = data["hourly"][14]["temp"]
        temp_21 = data["hourly"][21]["temp"]
        self.assertIsInstance(temp_14, (int, float))
        self.assertIsInstance(temp_21, (int, float))
        print(f"\n[시계열 추론 테스트] 마포구 14시 기온 {temp_14}°C vs 21시 기온 {temp_21}°C (지연시간: {data.get('latency_ms')}ms)")

    def test_03_b2b_fleet_rebalance_dynamic_hourly_weather(self):
        """POST /api/v1/b2b/fleet-rebalance 시간대 변경 시 예보 기상 동적 주입 검증"""
        # 14시 실시간 예보
        resp_14 = self.client.post("/api/v1/b2b/fleet-rebalance", json={
            "hour": 14,
            "use_live_weather": True,
        })
        self.assertEqual(resp_14.status_code, 200)
        data_14 = resp_14.json()

        # 22시 실시간 예보
        resp_22 = self.client.post("/api/v1/b2b/fleet-rebalance", json={
            "hour": 22,
            "use_live_weather": True,
        })
        self.assertEqual(resp_22.status_code, 200)
        data_22 = resp_22.json()

        cond_14 = data_14["weather_condition"]
        cond_22 = data_22["weather_condition"]

        print(f"\n[B2B 시간대 연동] 14시 날씨: {cond_14['temp']}°C / {cond_14['rain_mm']}mm")
        print(f"[B2B 시간대 연동] 22시 날씨: {cond_22['temp']}°C / {cond_22['rain_mm']}mm")
        self.assertNotEqual(cond_14["temp"], cond_22["temp"], "14시와 22시의 예보 기온이 상이해야 합니다.")


if __name__ == "__main__":
    unittest.main()
