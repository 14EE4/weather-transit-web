# -*- coding: utf-8 -*-
"""
tests/test_timeseries_cache.py
================================================================================
시계열 래그(Lag) 및 기상 차분 실시간 캐시 레이어 전용 단위/통합 테스트
================================================================================
"""

import time
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from main import app, build_feature_vector, WeatherInput, DISTRICT_STATS
from timeseries_cache import timeseries_cache, TimeseriesCacheManager, HOURLY_DIURNAL_FACTORS


def test_weather_diff_calculation():
    """1. 기상 급변 시 1시간 기상 차분값(temp_diff_1h, rain_diff_1h) 동적 산출 검증"""
    district = "마포구"
    now = datetime.now()
    prev_1h = now - timedelta(hours=1)

    # 1시간 전: 맑음, 기온 22.0°C, 강수량 0.0mm
    timeseries_cache.record_weather(district, temp=22.0, rain=0.0, dt=prev_1h)

    # 현재: 돌발 폭우, 기온 16.0°C, 강수량 15.0mm
    temp_diff, rain_diff = timeseries_cache.get_weather_diff_1h(
        district, current_temp=16.0, current_rain=15.0, dt=now
    )

    print(f"\n[기상 차분값 검증] 기온 변화: {temp_diff}°C, 강수량 변화: {rain_diff}mm")
    assert temp_diff == -6.0, f"Expected -6.0, got {temp_diff}"
    assert rain_diff == 15.0, f"Expected 15.0, got {rain_diff}"


def test_transit_lag_and_rolling_mean():
    """2. 대중교통 3시간 롤링 평균 및 1시간 래그 동적 집계 검증"""
    district = "서초구"
    now = datetime.now()
    t_1h = now - timedelta(hours=1)
    t_2h = now - timedelta(hours=2)
    t_3h = now - timedelta(hours=3)

    # 3시간 전, 2시간 전, 1시간 전 관측 스냅샷 순차 적재
    timeseries_cache.record_demand(district, bike_vol=100.0, bus_vol=8000.0, subway_vol=20000.0, dt=t_3h)
    timeseries_cache.record_demand(district, bike_vol=120.0, bus_vol=9000.0, subway_vol=22000.0, dt=t_2h)
    timeseries_cache.record_demand(district, bike_vol=140.0, bus_vol=10000.0, subway_vol=24000.0, dt=t_1h)

    lags = timeseries_cache.get_transit_lags(district, hour=now.hour, dt=now)

    print("\n[교통 래그 & 롤링 검증]")
    print(f"  - 1h Lag: 따릉이={lags['bike_lag_1h']}, 버스={lags['bus_lag_1h']}, 지하철={lags['subway_lag_1h']}")
    print(f"  - 3h Roll Mean: 따릉이={lags['bike_roll_mean_3h']}, 버스={lags['bus_roll_mean_3h']}, 지하철={lags['subway_roll_mean_3h']}")

    # 1시간 전 값 일치 확인
    assert lags["bike_lag_1h"] == 140.0
    assert lags["bus_lag_1h"] == 10000.0
    assert lags["subway_lag_1h"] == 24000.0

    # 3시간 평균값 일치 확인: (100 + 120 + 140) / 3 = 120.0
    assert lags["bike_roll_mean_3h"] == 120.0
    # (8000 + 9000 + 10000) / 3 = 9000.0
    assert lags["bus_roll_mean_3h"] == 9000.0
    # (20000 + 22000 + 24000) / 3 = 22000.0
    assert lags["subway_roll_mean_3h"] == 22000.0


def test_cold_start_diurnal_fallback():
    """3. 기록이 전혀 없는 신규 자치구의 Cold-Start Diurnal 첨두곡선 보정 검증"""
    fresh_district = "도봉구"
    now = datetime(2026, 10, 6, 8, 0, 0)  # 출근 피크 08시 가정
    stats = DISTRICT_STATS[fresh_district]

    lags = timeseries_cache.get_transit_lags(fresh_district, hour=8, dt=now, district_stats=stats)

    # 07시 (h_lag1) 계수
    factor_sub_07 = HOURLY_DIURNAL_FACTORS["subway"][7]  # 1.65
    expected_sub_lag1 = round(stats["subway_mean"] * factor_sub_07, 1)

    print(f"\n[Cold Start 첨두곡선 검증 - {fresh_district} 08시]")
    print(f"  - 지하철 평균: {stats['subway_mean']}, 07시 계수: {factor_sub_07}")
    print(f"  - 산출된 subway_lag_1h: {lags['subway_lag_1h']} (기대값: {expected_sub_lag1})")

    assert lags["subway_lag_1h"] == expected_sub_lag1


def test_feature_vector_integration():
    """4. build_feature_vector 연동 및 32차원 출력 검증"""
    weather = WeatherInput(temp=15.0, rain=3.5, humidity=75.0, wind=2.5)
    vec32 = build_feature_vector("송파구", 18, weather)

    assert len(vec32) == 32, f"Expected 32 features, got {len(vec32)}"
    # [21..31] 시계열 래그 및 변화량 피처가 NaN 없이 정상 부동소수점인지 확인
    for idx in range(21, 32):
        val = vec32[idx]
        assert isinstance(val, (int, float)) and not (val != val), f"Feature {idx} is invalid: {val}"


def test_diagnostic_endpoint():
    """5. /api/v1/cache/timeseries-status 진단 API 검증"""
    client = TestClient(app)
    resp = client.get("/api/v1/cache/timeseries-status?district=강남구")
    assert resp.status_code == 200
    data = resp.json()

    print(f"\n[진단 API 응답 검증]: {data['status']}")
    assert data["status"] == "healthy"
    assert data["query_district"] == "강남구"
    assert "current_lags_and_diffs" in data
    assert "bike_lag_1h" in data["current_lags_and_diffs"]
    assert "temp_diff_1h" in data["current_lags_and_diffs"]


if __name__ == "__main__":
    print("=" * 70)
    print("[Timeseries Cache Layer] 단위 및 통합 테스트 시작")
    print("=" * 70)
    test_weather_diff_calculation()
    test_transit_lag_and_rolling_mean()
    test_cold_start_diurnal_fallback()
    test_feature_vector_integration()
    test_diagnostic_endpoint()
    print("\n" + "=" * 70)
    print("[성공] 시계열 캐시 레이어의 모든 검증 테스트를 완벽 통과하였습니다!")
    print("=" * 70)
