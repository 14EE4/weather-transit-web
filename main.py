import os
import sys
import re
import math
import time
import asyncio
import logging
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import onnxruntime as ort
import httpx

from timeseries_cache import timeseries_cache
from multimodal_router import multimodal_routing_engine
from kma_forecast import (
    kma_forecast_manager,
    District24hForecast,
    HourlyForecastItem as KMAHourlyForecastItem,
)
from feature_schema import (
    FeatureSchemaError,
    legacy_25d_indices,
    load_schema,
    resolve_schema_path,
    schema_feature_cols,
    schema_summary,
    validate_expected_order,
)

# ==============================================================================
# 0. 로깅 및 환경 설정
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("weather_transit_api")

# .env 로드
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

# 공공데이터 인증키
KMA_AUTH_KEY = os.getenv("KMA_APIHUB_KEY")
SEOUL_SUBWAY_KEY = os.getenv("SEOUL_SUBWAY_API_KEY")
# 따릉이 실시간 대여정보(bikeList)용 인증키: 전용 키 우선, 없으면 서울 열린데이터광장 일반 인증키 재사용
SEOUL_BIKE_KEY = os.getenv("SEOUL_BIKE_API_KEY") or os.getenv("SEOUL_DATA_API_KEY")
DATA_GO_KR_BUS_KEY = os.getenv("DATA_GO_KR_API_KEY")

# 서울시 25개 자치구 및 수도권 주요 인접 도시 기상청 격자좌표 (nx, ny) 매핑
DISTRICT_KMA_GRID = {
    # 서울시 25개 자치구
    "강남구": {"nx": 61, "ny": 126},
    "강동구": {"nx": 62, "ny": 126},
    "강북구": {"nx": 61, "ny": 128},
    "강서구": {"nx": 58, "ny": 126},
    "관악구": {"nx": 59, "ny": 125},
    "광진구": {"nx": 62, "ny": 126},
    "구로구": {"nx": 58, "ny": 125},
    "금천구": {"nx": 59, "ny": 124},
    "노원구": {"nx": 61, "ny": 129},
    "도봉구": {"nx": 61, "ny": 129},
    "동대문구": {"nx": 61, "ny": 127},
    "동작구": {"nx": 59, "ny": 125},
    "마포구": {"nx": 59, "ny": 127},
    "서대문구": {"nx": 59, "ny": 127},
    "서초구": {"nx": 61, "ny": 125},
    "성동구": {"nx": 61, "ny": 127},
    "성북구": {"nx": 61, "ny": 127},
    "송파구": {"nx": 62, "ny": 126},
    "양천구": {"nx": 58, "ny": 126},
    "영등포구": {"nx": 58, "ny": 126},
    "용산구": {"nx": 60, "ny": 126},
    "은평구": {"nx": 59, "ny": 127},
    "종로구": {"nx": 60, "ny": 127},
    "중구": {"nx": 60, "ny": 127},
    "중랑구": {"nx": 62, "ny": 128},

    # 수도권 주요 인접 광역 관문 도시 (출퇴근 연계축)
    "성남시": {"nx": 62, "ny": 123},  # 분당구 / 판교 테크노밸리
    "광명시": {"nx": 58, "ny": 125},  # 철산 / 광명역
    "부천시": {"nx": 57, "ny": 125},  # 부천역 / 중동
    "고양시": {"nx": 57, "ny": 128},  # 일산 / 삼송
    "하남시": {"nx": 64, "ny": 126},  # 미사강변도시
    "수원시": {"nx": 60, "ny": 121},  # 수원역 / 광교
    "안양시": {"nx": 59, "ny": 123},  # 평촌 / 인덕원
    "남양주시": {"nx": 64, "ny": 128}, # 다산 / 별내
    "인천시": {"nx": 55, "ny": 124},  # 인천광역시 (부평·송도·구월)
}

# ==============================================================================
# 공공 API 서킷 브레이커 (Circuit Breaker) 및 장애 대비 복원력(Resilience) 계층
# ==============================================================================
class CircuitBreaker:
    """
    공공 API 장애 및 지연 전파 차단용 3상 서킷 브레이커 (CLOSED -> OPEN -> HALF_OPEN)
    - failure_threshold: 연속 실패 횟수 임계치 (초과 시 OPEN 전환)
    - recovery_timeout: OPEN 상태 지속 시간(초) 후 HALF_OPEN 프로빙 시도
    """
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0
        self.last_state_change = time.time()
        self.success_count = 0
        self.fallback_count = 0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                self.last_state_change = now
                logger.info(f"[CircuitBreaker:{self.name}] 쿨다운 만료 -> HALF_OPEN (프로빙 시험 요청 허용)")
                return True
            return False
        return True

    def record_success(self):
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info(f"[CircuitBreaker:{self.name}] 원격 API 정상 복구 확인 -> CLOSED 전환")
        self.failure_count = 0
        self.state = "CLOSED"
        self.success_count += 1
        self.last_state_change = time.time()

    def record_failure(self, error_msg: str = ""):
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.fallback_count += 1
        if self.state == "HALF_OPEN" or self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                logger.warning(
                    f"[CircuitBreaker:{self.name}] 연속 실패 {self.failure_count}회 발생! "
                    f"서킷을 OPEN 상태로 차단합니다 (쿨다운: {self.recovery_timeout}초). 원인: {error_msg}"
                )
            self.state = "OPEN"
            self.last_state_change = time.time()

    def get_status(self) -> dict:
        now = time.time()
        remaining_cooldown = max(0.0, self.recovery_timeout - (now - self.last_failure_time)) if self.state == "OPEN" else 0.0
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
            "remaining_cooldown_sec": round(remaining_cooldown, 1),
            "total_success": self.success_count,
            "total_fallback": self.fallback_count,
        }

# 서비스별 서킷 브레이커 인스턴스
kma_circuit_breaker = CircuitBreaker("KMA_WEATHER", failure_threshold=3, recovery_timeout=45.0)
subway_circuit_breaker = CircuitBreaker("SEOUL_SUBWAY", failure_threshold=3, recovery_timeout=30.0)
bus_circuit_breaker = CircuitBreaker("SEOUL_BUS", failure_threshold=3, recovery_timeout=30.0)
bike_circuit_breaker = CircuitBreaker("SEOUL_BIKE", failure_threshold=3, recovery_timeout=30.0)

# 공공 API 인메모리 단기 캐시 (과도한 외부 호출 방지 및 SLA 10ms 보장)
_weather_cache: dict[str, tuple[float, dict]] = {}
_subway_cache: dict[str, tuple[float, dict]] = {}
_bus_cache: dict[str, tuple[float, dict]] = {}

# 직전 정상 응답 스냅샷 (Last Known Good) 저장소 (장애 발생 시 만료 무시하고 우선 반환)
_weather_last_good: dict[str, dict] = {}
_subway_last_good: dict[str, dict] = {}
_bus_last_good: dict[str, dict] = {}

# 따릉이 전체 대여소 스냅샷 (단일 캐시: (수집시각, 대여소 목록))
_bike_snapshot_cache: Optional[tuple[float, list[dict]]] = None
_bike_snapshot_last_good: Optional[list[dict]] = None

# ==============================================================================
# 1. 서울시 25개 자치구 정수 매핑 딕셔너리 및 인프라/용량 기준 메타데이터
# ==============================================================================
DISTRICT_CODE_MAP: dict[str, int] = {
    "강남구": 0,
    "강동구": 1,
    "강북구": 2,
    "강서구": 3,
    "관악구": 4,
    "광진구": 5,
    "구로구": 6,
    "금천구": 7,
    "노원구": 8,
    "도봉구": 9,
    "동대문구": 10,
    "동작구": 11,
    "마포구": 12,
    "서대문구": 13,
    "서초구": 14,
    "성동구": 15,
    "성북구": 16,
    "송파구": 17,
    "양천구": 18,
    "영등포구": 19,
    "용산구": 20,
    "은평구": 21,
    "종로구": 22,
    "중구": 23,
    "중랑구": 24,
}

# 2025년 대한민국 공휴일 캘린더 (공휴일에 관한 법률 + 대체공휴일 + 임시공휴일·선거일)
# - 포함 19일: 신정 / 설날 연휴(+임시공휴일 01-27) / 삼일절+대체 / 어린이날·부처님오신날+대체 /
#             제21대 대통령선거일 / 현충일 / 광복절 / 개천절 / 추석 연휴+대체 / 한글날 / 성탄절
# - 제외: 노동절(05-01), 제헌절(07-17) → 2025년 기준 법정 공휴일 아님
# - 출처: 「공휴일에 관한 법률」 제2조·제3조, Office Holidays 2025, 위키백과 「대한민국의 공휴일」 대체공휴일 규정
# - ⚠️ 학습 파이프라인(`benchmarks/CastTransit.ipynb` [Cell 4-A] `KR_HOLIDAYS_2025`)과
#      반드시 동일한 집합을 유지할 것. 연도 추가 시 이 딕셔너리에 항목을 추가한다.
KR_HOLIDAYS: dict[int, frozenset[str]] = {
    2025: frozenset({
        "2025-01-01",                                # 신정
        "2025-01-27",                                # 임시공휴일(설 연휴 연결)
        "2025-01-28", "2025-01-29", "2025-01-30",    # 설날 연휴
        "2025-03-01", "2025-03-03",                  # 삼일절 + 대체공휴일
        "2025-05-05", "2025-05-06",                  # 어린이날·부처님오신날 + 대체공휴일
        "2025-06-03",                                # 제21대 대통령선거일
        "2025-06-06",                                # 현충일
        "2025-08-15",                                # 광복절
        "2025-10-03",                                # 개천절
        "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",  # 추석 연휴 + 대체공휴일
        "2025-10-09",                                # 한글날
        "2025-12-25",                                # 성탄절
    }),
}


def is_kr_public_holiday(dt: datetime) -> bool:
    """해당 일자가 대한민국 공휴일(임시공휴일·선거일·대체공휴일 포함)인지 여부.

    주말(토·일) 여부와는 별개 지표입니다. 사양서 §3.2의 `is_holiday` 피처는
    "공휴일 여부"이므로 본 함수를 단일 소스로 사용합니다.
    캘린더에 없는 연도는 False(0)를 반환하므로, 신규 연도 서빙 시
    `KR_HOLIDAYS`에 해당 연도 집합을 추가해야 합니다.
    """
    return dt.strftime("%Y-%m-%d") in KR_HOLIDAYS.get(dt.year, frozenset())


# 25개 자치구별 대중교통 인프라 가중치 (지하철 역사수, 버스 정류소수, 따릉이 거치대수, 상업지구 밀도)
# - 서울 열린데이터광장 및 서울시 교통통계연보(2024/2025) 실측 전수 동기화
DISTRICT_INFRA: dict[str, dict[str, float]] = {
    # ── 서울 25개 자치구 실측 인프라 통계 ──
    "강남구": {"subway_stations": 34.0, "bus_stops": 552.0, "bike_racks": 172.0, "commercial_density": 1.48},
    "강동구": {"subway_stations": 16.0, "bus_stops": 398.0, "bike_racks": 116.0, "commercial_density": 0.86},
    "강북구": {"subway_stations": 13.0, "bus_stops": 428.0, "bike_racks": 90.0,  "commercial_density": 0.72},
    "강서구": {"subway_stations": 23.0, "bus_stops": 628.0, "bike_racks": 212.0, "commercial_density": 0.92},
    "관악구": {"subway_stations": 9.0,  "bus_stops": 492.0, "bike_racks": 132.0, "commercial_density": 0.88},
    "광진구": {"subway_stations": 11.0, "bus_stops": 298.0, "bike_racks": 120.0, "commercial_density": 0.96},
    "구로구": {"subway_stations": 15.0, "bus_stops": 524.0, "bike_racks": 138.0, "commercial_density": 1.08},
    "금천구": {"subway_stations": 5.0,  "bus_stops": 368.0, "bike_racks": 96.0,  "commercial_density": 1.02},
    "노원구": {"subway_stations": 18.0, "bus_stops": 558.0, "bike_racks": 158.0, "commercial_density": 0.82},
    "도봉구": {"subway_stations": 8.0,  "bus_stops": 402.0, "bike_racks": 102.0, "commercial_density": 0.70},
    "동대문구": {"subway_stations": 16.0, "bus_stops": 498.0, "bike_racks": 130.0, "commercial_density": 1.05},
    "동작구": {"subway_stations": 17.0, "bus_stops": 448.0, "bike_racks": 118.0, "commercial_density": 0.92},
    "마포구": {"subway_stations": 18.0, "bus_stops": 574.0, "bike_racks": 168.0, "commercial_density": 1.28},
    "서대문구": {"subway_stations": 10.0, "bus_stops": 462.0, "bike_racks": 110.0, "commercial_density": 0.95},
    "서초구": {"subway_stations": 27.0, "bus_stops": 615.0, "bike_racks": 156.0, "commercial_density": 1.36},
    "성동구": {"subway_stations": 17.0, "bus_stops": 442.0, "bike_racks": 128.0, "commercial_density": 1.12},
    "성북구": {"subway_stations": 14.0, "bus_stops": 602.0, "bike_racks": 124.0, "commercial_density": 0.85},
    "송파구": {"subway_stations": 30.0, "bus_stops": 645.0, "bike_racks": 228.0, "commercial_density": 1.22},
    "양천구": {"subway_stations": 10.0, "bus_stops": 388.0, "bike_racks": 136.0, "commercial_density": 0.86},
    "영등포구": {"subway_stations": 21.0, "bus_stops": 516.0, "bike_racks": 184.0, "commercial_density": 1.42},
    "용산구": {"subway_stations": 15.0, "bus_stops": 356.0, "bike_racks": 106.0, "commercial_density": 1.18},
    "은평구": {"subway_stations": 16.0, "bus_stops": 518.0, "bike_racks": 142.0, "commercial_density": 0.76},
    "종로구": {"subway_stations": 19.0, "bus_stops": 386.0, "bike_racks": 126.0, "commercial_density": 1.35},
    "중구":   {"subway_stations": 26.0, "bus_stops": 248.0, "bike_racks": 114.0, "commercial_density": 1.46},
    "중랑구": {"subway_stations": 12.0, "bus_stops": 378.0, "bike_racks": 122.0, "commercial_density": 0.76},

    # ── 수도권 주요 광역 관문 도시 (출퇴근 연계축 지원) ──
    "성남시": {"subway_stations": 18.0, "bus_stops": 520.0, "bike_racks": 140.0, "commercial_density": 1.30},
    "수원시": {"subway_stations": 14.0, "bus_stops": 680.0, "bike_racks": 160.0, "commercial_density": 1.15},
    "인천시": {"subway_stations": 32.0, "bus_stops": 710.0, "bike_racks": 150.0, "commercial_density": 1.10},
    "부천시": {"subway_stations": 11.0, "bus_stops": 480.0, "bike_racks": 110.0, "commercial_density": 1.00},
    "고양시": {"subway_stations": 15.0, "bus_stops": 620.0, "bike_racks": 130.0, "commercial_density": 0.95},
    "안양시": {"subway_stations": 8.0,  "bus_stops": 380.0, "bike_racks": 95.0,  "commercial_density": 1.05},
    "광명시": {"subway_stations": 5.0,  "bus_stops": 290.0, "bike_racks": 85.0,  "commercial_density": 0.95},
    "하남시": {"subway_stations": 4.0,  "bus_stops": 260.0, "bike_racks": 80.0,  "commercial_density": 0.90},
    "남양주시": {"subway_stations": 9.0,  "bus_stops": 450.0, "bike_racks": 90.0,  "commercial_density": 0.85},
}

# 2025 서울시 25개 자치구 시간대별 통합 데이터셋(20.9만건) 분석 기반 기준 통계치
# (p95: 혼잡도 100% 기준 상한선, min: 최저 수요 하한선, mean: 기본 래그 값)
DISTRICT_STATS: dict[str, dict[str, float]] = {
    "강남구": {"bike_p95": 413.0, "bike_min": 1.0, "bike_mean": 149.2, "bus_p95": 30559.0, "bus_min": 81.0, "bus_mean": 12732.1, "subway_p95": 68613.4, "subway_min": 1636.0, "subway_mean": 23326.4},
    "강동구": {"bike_p95": 544.0, "bike_min": 1.0, "bike_mean": 207.7, "bus_p95": 10762.4, "bus_min": 26.0, "bus_mean": 4724.3, "subway_p95": 24164.8, "subway_min": 549.0, "subway_mean": 8462.7},
    "강북구": {"bike_p95": 126.0, "bike_min": 1.0, "bike_mean": 54.4, "bus_p95": 14450.4, "bus_min": 63.0, "bus_mean": 7303.9, "subway_p95": 10785.5, "subway_min": 374.0, "subway_mean": 4016.7},
    "강서구": {"bike_p95": 1617.6, "bike_min": 4.0, "bike_mean": 540.1, "bus_p95": 16366.2, "bus_min": 55.0, "bus_mean": 7227.4, "subway_p95": 19921.9, "subway_min": 627.0, "subway_mean": 7355.8},
    "관악구": {"bike_p95": 209.0, "bike_min": 1.0, "bike_mean": 84.4, "bus_p95": 23376.4, "bus_min": 108.0, "bus_mean": 11168.7, "subway_p95": 22041.5, "subway_min": 650.0, "subway_mean": 8106.8},
    "광진구": {"bike_p95": 544.0, "bike_min": 2.0, "bike_mean": 211.8, "bus_p95": 9507.6, "bus_min": 96.0, "bus_mean": 4514.7, "subway_p95": 19458.1, "subway_min": 1215.0, "subway_mean": 10489.3},
    "구로구": {"bike_p95": 517.3, "bike_min": 1.0, "bike_mean": 178.7, "bus_p95": 17649.0, "bus_min": 33.0, "bus_mean": 7694.2, "subway_p95": 22103.9, "subway_min": 623.0, "subway_mean": 8711.8},
    "금천구": {"bike_p95": 256.0, "bike_min": 1.0, "bike_mean": 73.9, "bus_p95": 14735.0, "bus_min": 23.0, "bus_mean": 5676.7, "subway_p95": 9996.0, "subway_min": 65.0, "subway_mean": 2104.0},
    "노원구": {"bike_p95": 639.3, "bike_min": 2.0, "bike_mean": 261.2, "bus_p95": 13237.4, "bus_min": 41.0, "bus_mean": 6442.0, "subway_p95": 27721.9, "subway_min": 797.0, "subway_mean": 9496.4},
    "도봉구": {"bike_p95": 226.0, "bike_min": 1.0, "bike_mean": 90.3, "bus_p95": 11041.2, "bus_min": 38.0, "bus_mean": 4979.1, "subway_p95": 10506.2, "subway_min": 202.0, "subway_mean": 3414.3},
    "동대문구": {"bike_p95": 363.0, "bike_min": 1.0, "bike_mean": 143.2, "bus_p95": 18442.4, "bus_min": 67.0, "bus_mean": 8663.7, "subway_p95": 8916.2, "subway_min": 235.0, "subway_mean": 4276.9},
    "동작구": {"bike_p95": 197.3, "bike_min": 1.0, "bike_mean": 74.3, "bus_p95": 17793.2, "bus_min": 49.0, "bus_mean": 8087.4, "subway_p95": 24188.9, "subway_min": 875.0, "subway_mean": 10633.4},
    "마포구": {"bike_p95": 565.0, "bike_min": 1.0, "bike_mean": 205.2, "bus_p95": 19060.0, "bus_min": 162.0, "bus_mean": 8504.3, "subway_p95": 29832.4, "subway_min": 1717.0, "subway_mean": 16454.7},
    "서대문구": {"bike_p95": 212.0, "bike_min": 1.0, "bike_mean": 80.1, "bus_p95": 20357.6, "bus_min": 60.0, "bus_mean": 9605.5, "subway_p95": 5693.5, "subway_min": 87.0, "subway_mean": 2381.9},
    "서초구": {"bike_p95": 377.6, "bike_min": 1.0, "bike_mean": 132.4, "bus_p95": 25430.4, "bus_min": 141.0, "bus_mean": 10803.8, "subway_p95": 33462.1, "subway_min": 822.0, "subway_mean": 13347.4},
    "성동구": {"bike_p95": 480.0, "bike_min": 1.0, "bike_mean": 166.6, "bus_p95": 10130.8, "bus_min": 25.0, "bus_mean": 4560.3, "subway_p95": 20601.1, "subway_min": 631.0, "subway_mean": 9603.3},
    "성북구": {"bike_p95": 217.0, "bike_min": 1.0, "bike_mean": 87.5, "bus_p95": 20210.0, "bus_min": 56.0, "bus_mean": 9771.0, "subway_p95": 15420.7, "subway_min": 495.0, "subway_mean": 6289.7},
    "송파구": {"bike_p95": 1112.3, "bike_min": 1.0, "bike_mean": 408.8, "bus_p95": 20060.4, "bus_min": 74.0, "bus_mean": 8795.4, "subway_p95": 34324.0, "subway_min": 1106.0, "subway_mean": 15936.9},
    "양천구": {"bike_p95": 695.0, "bike_min": 2.0, "bike_mean": 269.2, "bus_p95": 13971.4, "bus_min": 21.0, "bus_mean": 6250.3, "subway_p95": 11636.3, "subway_min": 203.0, "subway_mean": 3560.6},
    "영등포구": {"bike_p95": 1171.3, "bike_min": 2.0, "bike_mean": 400.9, "bus_p95": 22101.2, "bus_min": 64.0, "bus_mean": 9000.3, "subway_p95": 20938.3, "subway_min": 550.0, "subway_mean": 8232.2},
    "용산구": {"bike_p95": 245.3, "bike_min": 1.0, "bike_mean": 84.7, "bus_p95": 14659.0, "bus_min": 82.0, "bus_mean": 7117.4, "subway_p95": 13509.4, "subway_min": 700.0, "subway_mean": 5922.1},
    "은평구": {"bike_p95": 245.0, "bike_min": 1.0, "bike_mean": 98.2, "bus_p95": 17334.6, "bus_min": 52.0, "bus_mean": 7938.9, "subway_p95": 28149.7, "subway_min": 514.0, "subway_mean": 8649.7},
    "종로구": {"bike_p95": 366.6, "bike_min": 1.0, "bike_mean": 139.5, "bus_p95": 20021.4, "bus_min": 195.0, "bus_mean": 9046.4, "subway_p95": 45238.5, "subway_min": 921.0, "subway_mean": 16971.0},
    "중구":   {"bike_p95": 282.0, "bike_min": 1.0, "bike_mean": 102.8, "bus_p95": 13379.4, "bus_min": 103.0, "bus_mean": 6527.5, "subway_p95": 59501.0, "subway_min": 1316.0, "subway_mean": 23011.0},
    "중랑구": {"bike_p95": 291.0, "bike_min": 1.0, "bike_mean": 117.7, "bus_p95": 13237.0, "bus_min": 47.0, "bus_mean": 6013.2, "subway_p95": 13635.5, "subway_min": 364.0, "subway_mean": 4378.5},
}

def normalize_district_name(district: str) -> str:
    """프론트엔드나 사용자가 전달한 자치구 명칭(예: '강남구 역삼동', '강남구')을 표준 25개 자치구명으로 정규화"""
    district = district.strip()
    if district in DISTRICT_CODE_MAP:
        return district
    for d in DISTRICT_CODE_MAP:
        if d in district:
            return d
    # 동 및 수도권 광역 연계축 기반 매핑 지원
    dong_map = {
        # 동남권 (강남·서초·송파·강동)
        "역삼": "강남구", "삼성": "강남구", "논현": "강남구", "대치": "강남구", "압구정": "강남구", "수서": "강남구", "청담": "강남구", "도곡": "강남구", "개포": "강남구",
        "서초": "서초구", "반포": "서초구", "방배": "서초구", "양재": "서초구", "잠원": "서초구", "교대": "서초구",
        "잠실": "송파구", "방이": "송파구", "문정": "송파구", "가락": "송파구", "석촌": "송파구", "오금": "송파구",
        "천호": "강동구", "길동": "강동구", "명일": "강동구", "고덕": "강동구", "암사": "강동구", "둔촌": "강동구",
        # 도심권 (종로·중구·용산)
        "종로": "종로구", "혜화": "종로구", "인사동": "종로구", "광화문": "종로구", "대학로": "종로구", "평창": "종로구", "삼청": "종로구",
        "명동": "중구", "을지로": "중구", "소공동": "중구", "회현": "중구", "신당": "중구", "충무로": "중구", "서울역": "중구",
        "이태원": "용산구", "한남": "용산구", "용산": "용산구", "이촌": "용산구", "후암": "용산구", "남영": "용산구",
        # 서남권 (영등포·구로·금천·동작·관악·강서·양천)
        "여의도": "영등포구", "당산": "영등포구", "문래": "영등포구", "영등포": "영등포구", "신길": "영등포구", "대림": "영등포구",
        "신도림": "구로구", "구로": "구로구", "개봉": "구로구", "고척": "구로구", "오류": "구로구",
        "가산": "금천구", "독산": "금천구", "시흥": "금천구",
        "노량진": "동작구", "사당": "동작구", "상도": "동작구", "흑석": "동작구", "보라매": "동작구",
        "신림": "관악구", "봉천": "관악구", "낙성대": "관악구", "서울대": "관악구",
        "마곡": "강서구", "화곡": "강서구", "가양": "강서구", "발산": "강서구", "등촌": "강서구", "방화": "강서구",
        "목동": "양천구", "신정": "양천구", "신월": "양천구", "오목교": "양천구",
        # 서북권 (마포·서대문·은평)
        "서교": "마포구", "홍대": "마포구", "합정": "마포구", "망원": "마포구", "상암": "마포구", "연남": "마포구", "공덕": "마포구", "아현": "마포구",
        "신촌": "서대문구", "연희": "서대문구", "홍제": "서대문구", "이대": "서대문구", "남가좌": "서대문구",
        "연신내": "은평구", "불광": "은평구", "응암": "은평구", "녹번": "은평구", "구파발": "은평구",
        # 동북권 (성동·광진·동대문·중랑·성북·강북·도봉·노원)
        "성수": "성동구", "왕십리": "성동구", "옥수": "성동구", "금호": "성동구", "행당": "성동구",
        "건대": "광진구", "화양": "광진구", "구의": "광진구", "자양": "광진구", "강변": "광진구",
        "청량리": "동대문구", "회기": "동대문구", "전농": "동대문구", "장안": "동대문구", "이문": "동대문구",
        "상봉": "중랑구", "면목": "중랑구", "중화": "중랑구", "망우": "중랑구",
        "안암": "성북구", "길음": "성북구", "성북": "성북구", "돈암": "성북구", "정릉": "성북구",
        "수유": "강북구", "미아": "강북구", "번동": "강북구", "우이": "강북구",
        "창동": "도봉구", "쌍문": "도봉구", "방학": "도봉구", "도봉": "도봉구",
        "노원": "노원구", "상계": "노원구", "중계": "노원구", "하계": "노원구", "공릉": "노원구", "태릉": "노원구",
        # 수도권 인접 광역 관문 거점 (서울 직결 교통축 매핑)
        "판교": "강남구", "분당": "강남구", "성남": "강남구",
        "광명": "금천구", "철산": "금천구",
        "부천": "구로구", "부평": "구로구", "인천": "구로구", "송도": "구로구", "구월": "구로구", "청라": "구로구",
        "일산": "은평구", "고양": "은평구", "삼송": "은평구", "파주": "은평구",
        "하남": "강동구", "미사": "강동구", "위례": "강동구",
        "수원": "서초구", "광교": "서초구", "동탄": "서초구", "안양": "서초구", "평촌": "서초구", "과천": "서초구",
        "다산": "중랑구", "별내": "중랑구", "남양주": "중랑구", "구리": "중랑구",
        "의정부": "노원구", "양주": "노원구",
        "김포": "강서구",
    }
    for dong_key, d_name in dong_map.items():
        if dong_key in district:
            return d_name
    return "강남구"

def latlng_to_grid(lat: float, lng: float) -> tuple[int, int]:
    """
    기상청 공인 LCC(Lambert Conformal Conic) 투영 격자 변환 공식
    위경도(lat, lng) -> 기상청 국지 격자좌표 (nx, ny)
    """
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lng * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = math.floor(ra * math.sin(theta) + XO + 0.5)
    y = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    return int(x), int(y)

def resolve_weather_target(
    district_str: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    station: Optional[str] = None
) -> tuple[str, int, int]:
    """
    기상청 관측소 격자 좌표(nx, ny) 및 표출 지역명 판별
    - lat, lng 좌표가 전달된 경우: 기상청 LCC 공식을 통해 초정밀 국지 격자(nx, ny) 직접 산출
    - 서울시 25개 자치구 및 수도권 주요 인접 도시 매핑 지원
    """
    calc_nx, calc_ny = None, None
    if lat is not None and lng is not None and 33.0 <= lat <= 43.0 and 124.0 <= lng <= 132.0:
        calc_nx, calc_ny = latlng_to_grid(lat, lng)

    name_to_check = (station or district_str).strip()
    d_clean = district_str.strip()

    # 수도권 인접 광역 관문 거점 및 행정동/랜드마크 매핑
    satellite_cities: dict[str, tuple[str, int, int]] = {
        "성남": ("성남시", 62, 123),
        "분당": ("성남시", 62, 123),
        "판교": ("성남시", 62, 123),
        "광명": ("광명시", 58, 125),
        "철산": ("광명시", 58, 125),
        "부천": ("부천시", 57, 125),
        "중동": ("부천시", 57, 125),
        "고양": ("고양시", 57, 128),
        "일산": ("고양시", 57, 128),
        "삼송": ("고양시", 57, 128),
        "하남": ("하남시", 64, 126),
        "미사": ("하남시", 64, 126),
        "수원": ("수원시", 60, 121),
        "광교": ("수원시", 60, 121),
        "안양": ("안양시", 59, 123),
        "평촌": ("안양시", 59, 123),
        "인덕원": ("안양시", 59, 123),
        "남양주": ("남양주시", 64, 128),
        "다산": ("남양주시", 64, 128),
        "별내": ("남양주시", 64, 128),
        "인천": ("인천시", 55, 124),
        "부평": ("인천시", 55, 125),
        "송도": ("인천시", 55, 123),
        "구월": ("인천시", 55, 124),
        "청라": ("인천시", 54, 125),
    }

    for key, (city_name, nx, ny) in satellite_cities.items():
        if key in name_to_check or key in d_clean:
            return city_name, (calc_nx or nx), (calc_ny or ny)

    # 서울 25개 자치구 정규화
    norm_d = normalize_district_name(name_to_check if name_to_check != "강남구" else d_clean)
    grid = DISTRICT_KMA_GRID.get(norm_d, {"nx": 61, "ny": 126})
    return norm_d, (calc_nx or grid["nx"]), (calc_ny or grid["ny"])

# ==============================================================================
# 2. ONNX 세션 관리 및 Cold Start 방지 인메모리 로더
# ==============================================================================
class ModelRegistry:
    def __init__(self):
        self.bike_session: Optional[ort.InferenceSession] = None
        self.bus_session: Optional[ort.InferenceSession] = None
        self.subway_session: Optional[ort.InferenceSession] = None
        self.is_loaded: bool = False
        # 피처 스키마(단일 진실 공급원) — 기동 시 순서·차원 검증 결과를 보관한다.
        self.schema: Optional[dict] = None
        self.schema_path: Optional[Path] = None
        self.schema_status: str = "not-checked"
        self.model_input_dims: dict[str, int] = {}

    def load_feature_schema(self):
        """`feature_schema.json`(SSoT)을 읽어 피처 **차원·순서**를 검증한다.

        - 스키마가 없으면 경고만 남기고 진행한다(스키마 미동봉 배포와의 호환).
        - 순서가 어긋나면 `FeatureSchemaError` 로 **기동을 중단**한다(조용한 예측 붕괴 방지).
        """
        self.schema_path = resolve_schema_path()
        if self.schema_path is None:
            self.schema_status = "not-found"
            logger.warning(
                "feature_schema.json 을 찾지 못해 피처 순서 검증을 건너뜁니다 "
                "(FEATURE_SCHEMA_PATH 환경변수로 경로를 지정할 수 있습니다)."
            )
            return
        self.schema = load_schema(self.schema_path)
        if self.schema is None:  # resolve 성공 후 None 은 불가능하지만 방어적으로 처리
            self.schema_status = "not-found"
            return
        cols = validate_expected_order(
            self.schema, FEATURE_ORDER_32, "main.py::FEATURE_ORDER_32"
        )
        self.schema_status = "verified"
        logger.info(
            f"[schema] 피처 스키마 검증 통과: model_version={self.schema.get('model_version')} | "
            f"{len(cols)}차원 | order={self.schema.get('order')} | 출처={self.schema_path.as_posix()}"
        )

    def validate_model_dimensions(self):
        """로드된 ONNX 세션의 입력 차원을 스키마(SSoT)와 대조한다.

        - 스키마 차원과 동일 → 정렬 OK
        - 25차원 → 레거시 서브셋(경고: 예측은 정상, 32차원 재학습 자산으로 교체 시 자동 정렬)
        - 그 외 → `FeatureSchemaError`(잘못된 자산 반입 차단)
        """
        session_names = ("bike", "bus", "subway")
        for name in session_names:
            sess = getattr(self, f"{name}_session")
            if sess is None:
                continue
            self.model_input_dims[name] = int(sess.get_inputs()[0].shape[1])

        if self.schema is None:
            return
        schema_dim = len(schema_feature_cols(self.schema))
        legacy_indices = legacy_25d_indices()

        aligned, legacy_modes, unknown = [], [], {}
        for name in session_names:
            dim = self.model_input_dims.get(name)
            if dim is None:
                continue
            if dim == schema_dim:
                aligned.append(name)
            elif dim == len(legacy_indices):
                legacy_modes.append(name)
            else:
                unknown[name] = dim

        if unknown:
            raise FeatureSchemaError(
                f"스키마({schema_dim}차원)와 맞지 않는 모델 입력 차원: {unknown} — "
                f"{schema_dim}차원 또는 25차원 레거시 서브셋만 지원합니다."
            )
        for name in aligned:
            logger.info(f"[schema] {name}: 입력 {schema_dim}차원 — 스키마 정렬 OK")
        if legacy_modes:
            logger.warning(
                f"[schema] {legacy_modes}: 입력 25차원 레거시 서브셋으로 동작 중 "
                f"(스키마 {schema_dim}차원 중 인덱스 {list(legacy_indices)} 사용). "
                "32차원 재학습 자산으로 교체하면 자동 정렬됩니다."
            )
        if aligned and legacy_modes:
            self.schema_status = "mixed-32d/25d"
        elif legacy_modes:
            self.schema_status = "legacy-subset-25d"
        else:
            self.schema_status = "verified"

    def schema_report(self) -> dict:
        """`/health` 응답용 피처 스키마 검증 요약."""
        return schema_summary(
            self.schema,
            path=self.schema_path,
            model_input_dims=self.model_input_dims,
            status=self.schema_status,
        )

    def load_models(self):
        logger.info("Initializing ONNX Inference Sessions with CPUExecutionProvider...")
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 4
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        bike_path = MODEL_DIR / "lgb_bike_demand.onnx"
        bus_path = MODEL_DIR / "lgb_bus_demand.onnx"
        subway_path = MODEL_DIR / "lgb_subway_demand.onnx"

        for p in (bike_path, bus_path, subway_path):
            if not p.exists():
                raise FileNotFoundError(f"필수 ONNX 모델 파일이 존재하지 않습니다: {p}")

        self.bike_session = ort.InferenceSession(str(bike_path), sess_options=sess_options, providers=["CPUExecutionProvider"])
        self.bus_session = ort.InferenceSession(str(bus_path), sess_options=sess_options, providers=["CPUExecutionProvider"])
        self.subway_session = ort.InferenceSession(str(subway_path), sess_options=sess_options, providers=["CPUExecutionProvider"])

        # 피처 스키마(SSoT) 검증: 코드 순서 ↔ 스키마 ↔ 실제 ONNX 입력 차원
        self.load_feature_schema()
        self.validate_model_dimensions()

        # Cold Start 방지를 위한 더미 웜업 추론 수행
        self._warmup()
        self.is_loaded = True
        logger.info("All 3 ONNX models successfully loaded in-memory and warmed up.")

    def _warmup(self):
        for name, sess in [("bike", self.bike_session), ("bus", self.bus_session), ("subway", self.subway_session)]:
            inp_meta = sess.get_inputs()[0]
            expected_dim = inp_meta.shape[1] if len(inp_meta.shape) > 1 and isinstance(inp_meta.shape[1], int) else 25
            dummy_tensor = np.zeros((1, expected_dim), dtype=np.float32)
            _ = sess.run(None, {inp_meta.name: dummy_tensor})
            logger.info(f"Warmup executed for {name} session (input dim: {expected_dim}).")

registry = ModelRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 기동 시 인메모리 세션 생성
    registry.load_models()
    yield
    # 종료 시 세션 해제
    logger.info("Shutting down ONNX inference sessions.")

# ==============================================================================
# 3. FastAPI 애플리케이션 정의 및 CORS 설정
# ==============================================================================
app = FastAPI(
    title="Weather & Transit AI Inference Backend",
    description="2025 서울시 교통-기상 통합 빅데이터 기반 실시간 수요·혼잡도 예측 및 MCDA 추천 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 미들웨어를 모든 오리진(*)에 대해 허용하도록 구성
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 4. Pydantic 요청/응답 스키마 정의
# ==============================================================================
class WeatherInput(BaseModel):
    temp: float = Field(default=14.0, description="기온 (°C)", example=14.0)
    rain: float = Field(default=0.0, ge=0.0, description="1시간 누적 강수량 (mm)", example=2.8)
    humidity: float = Field(default=60.0, ge=0.0, le=100.0, description="습도 (%)", example=86.0)
    wind: float = Field(default=2.0, ge=0.0, description="풍속 (m/s)", example=3.8)

class PredictionRequest(BaseModel):
    district: str = Field(default="강남구", description="서울시 자치구 명칭", example="강남구")
    hour: int = Field(default=8, ge=0, le=24, description="시간대 (0~24시)", example=8)
    weather: Optional[WeatherInput] = Field(default=None, description="기상 관측 데이터")
    station: Optional[str] = Field(default=None, description="특정 역사 또는 정류소 명칭", example="강남역")
    stop_type: Optional[str] = Field(default=None, description="교통수단 유형 (subway, bus, bike)", example="subway")
    base_crowd: Optional[int] = Field(default=None, description="역/정류소 기준 혼잡도 (0~100)", example=88)

class RecommendationItem(BaseModel):
    id: str
    icon: str
    name: str
    score: int
    scoreLabel: str
    scoreColor: str
    reasons: list[str]
    estimated_time_min: int
    fare_krw: int
    crowd: int
    crowdLabel: str
    crowdColor: str
    predicted_volume: int
    predicted_demand: int

class WeatherSummary(BaseModel):
    condition: str
    description: str

class PredictionResponse(BaseModel):
    status: str = "success"
    timestamp: str
    district: str
    station: Optional[str] = None
    corridor_district: Optional[str] = None
    latency_ms: float
    weather_summary: WeatherSummary
    recommendations: list[RecommendationItem]

class SimulationRequest(BaseModel):
    simulated_rain_mm: float = Field(default=5.0, ge=0.0, description="시뮬레이션 가상 강수량 (mm)")
    simulated_temp: float = Field(default=12.0, description="시뮬레이션 기온 (°C)")
    hour: int = Field(default=9, ge=0, le=24, description="시뮬레이션 시간대 (0~24시)")

class ModalShiftSummary(BaseModel):
    bike_demand_change_rate: float
    subway_demand_change_rate: float
    bus_demand_change_rate: float
    commentary: str

class DistrictCongestionItem(BaseModel):
    district: str
    subway_crowd: int
    bus_crowd: int
    bike_crowd: int

class SimulationResponse(BaseModel):
    status: str = "success"
    latency_ms: float
    simulation_params: dict
    modal_shift_summary: ModalShiftSummary
    district_congestion: list[DistrictCongestionItem]

# ==============================================================================
# B2B 기업용 모빌리티 재배치(Fleet Rebalancing) 모델 규격
# ==============================================================================
class B2BFleetRebalanceRequest(BaseModel):
    hour: int = Field(default=9, ge=0, le=23, description="대상 시간대 (0~23시)")
    rain_mm: float = Field(default=0.0, ge=0.0, le=100.0, description="강수량 (mm/h) - 0이면 맑은 날")
    temp: float = Field(default=18.0, description="기온 (°C)")
    use_live_weather: bool = Field(default=False, description="실제 기상청 실황 기상 데이터 자동 적용 여부")

class B2BDistrictRebalanceItem(BaseModel):
    district: str
    district_code: int
    # 따릉이 (PM)
    bike_demand: float
    bike_baseline: float
    bike_delta_pct: float
    bike_status: str              # "SURPLUS" | "DEFICIT" | "STABLE"
    bike_action: str              # "RECALL" | "DEPLOY" | "MAINTAIN"
    bike_rebalance_qty: int       # 권장 조정 수량 (대수)
    # 버스
    bus_demand: float
    bus_baseline: float
    bus_delta_pct: float
    bus_status: str               # "CROWDED" | "NORMAL" | "LIGHT"
    bus_recommended_trips: int    # 배차 조정 권고 (회)
    # 지하철
    subway_demand: float
    subway_baseline: float
    subway_delta_pct: float
    # 인프라 & 가이드
    infra: dict
    urgency: str                  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    actionable_guidance: str

class B2BFleetRebalanceResponse(BaseModel):
    status: str = "success"
    latency_ms: float
    weather_condition: dict
    total_bike_surplus_qty: int
    total_bike_deficit_qty: int
    total_bus_extra_trips: int
    top_recall_districts: list[dict]
    top_deploy_districts: list[dict]
    district_rebalance_list: list[B2BDistrictRebalanceItem]

# ── 실시간 공공 API 응답 스키마 ──
class RealtimeWeatherResponse(BaseModel):
    status: str = "success"
    district: str
    station: Optional[str] = None
    nx: int
    ny: int
    base_date: str
    base_time: str
    temp: float
    rain: float
    pty: str
    pty_desc: str
    humidity: float
    wind: float
    source: str = "KMA_APIHUB_LIVE"

class SubwayArrivalItem(BaseModel):
    line: str
    destination: str
    message: str
    remaining_seconds: int
    remaining_minutes: int
    train_status: str
    updn_line: str

class SubwayArrivalResponse(BaseModel):
    status: str = "success"
    station: str
    clean_station: str
    arrivals: list[SubwayArrivalItem]
    source: str = "SEOUL_SUBWAY_LIVE"

class BusArrivalItem(BaseModel):
    route_name: str
    station_name: str
    arrival_msg1: str
    arrival_msg2: str
    station_order: Optional[str] = None
    bus_route_id: Optional[str] = None

class BusArrivalResponse(BaseModel):
    status: str = "success"
    st_id: str
    arrivals: list[BusArrivalItem]
    source: str = "SEOUL_BUS_LIVE"

class DistrictLiveCongestionItem(BaseModel):
    name: str
    district: str
    bus: int
    subway: int
    bike: int
    weather: str
    temp: float
    rain: float
    condition: str

class LiveDistrictCongestionResponse(BaseModel):
    status: str = "success"
    timestamp: str
    hour: int
    latency_ms: float
    hotspots: list[DistrictLiveCongestionItem]
    all_districts: Optional[list[DistrictLiveCongestionItem]] = None

class HourlyForecastItem(BaseModel):
    hour: str
    hour_num: int
    temp: float
    rain: float
    humidity: float
    wind: float
    subway: int
    bus: int
    bike: int
    subway_crowd: int
    bus_crowd: int
    bike_crowd: int
    is_peak: bool

class HourlyForecastResponse(BaseModel):
    status: str = "success"
    district: str
    timestamp: str
    current_hour: int
    latency_ms: float
    hourly: list[HourlyForecastItem]
    forecast: Optional[list[HourlyForecastItem]] = None

# ==============================================================================
# 5. 사양서 규격의 32차원 Feature Vector 조립 함수 (build_feature_vector)
# ==============================================================================
# 피처 **이름과 순서의 코드 측 정의** — `build_feature_vector` 가 만드는 벡터 순서와 1:1 대응.
# `feature_schema.json`(SSoT) 이 있으면 기동 시 이 순서와 assert 대조한다
# (`ModelRegistry.load_feature_schema`) → 학습/평가/서빙 순서 드리프트 차단.
FEATURE_ORDER_32 = [
    # [0..7] 시계열 및 캘린더 피처
    "month_sin", "month_cos", "hour_sin", "hour_cos",
    "dayofweek", "is_weekend", "is_holiday", "is_rush_hour",
    # [8..15] 기상 관측 및 파생 피처
    "temperature", "wind_speed", "humidity", "precipitation",
    "is_raining", "rain_intensity", "sensible_temp", "discomfort_index",
    # [16..20] 공간(위치) 인코딩 피처
    "district_code", "district_subway_stations", "district_bus_stops",
    "district_bike_racks", "commercial_density",
    # [21..31] 시계열 래그 및 이동통계 피처
    "따릉이_대여_lag_1h", "버스_승차_lag_1h", "지하철_승차_lag_1h",
    "따릉이_대여_roll_3h", "버스_승차_roll_3h", "지하철_승차_roll_3h",
    "same_day_last_week_bike", "same_day_last_week_bus", "same_day_last_week_sub",
    "temp_diff_1h", "rain_diff_1h",
]

def build_feature_vector(
    district: str,
    hour: int,
    weather: WeatherInput,
    dt: Optional[datetime] = None
) -> list[float]:
    """
    사양서(docs/AI_INFERENCE_MODEL_SPEC.md §3.2) 규격의 32차원 Feature Vector 조립 함수
    
    구성 (총 32차원):
    1. 시계열 및 캘린더 피처 (8차원):
       month_sin, month_cos, hour_sin, hour_cos, dayofweek, is_weekend, is_holiday, is_rush_hour
    2. 기상 관측 및 파생 피처 (8차원):
       temperature, wind_speed, humidity, precipitation, is_raining, rain_intensity, sensible_temp, discomfort_index
    3. 공간(위치) 인코딩 피처 (5차원):
       district_code, district_subway_stations, district_bus_stops, district_bike_racks, commercial_density
    4. 시계열 래그(Lag) 및 이동통계 피처 (11차원):
       bike_lag_1h, bus_lag_1h, subway_lag_1h,
       bike_roll_mean_3h, bus_roll_mean_3h, subway_roll_mean_3h,
       same_day_last_week_bike, same_day_last_week_bus, same_day_last_week_sub,
       temp_diff_1h, rain_diff_1h
    """
    if dt is None:
        dt = datetime.now()

    # 시간 정규화 (0시와 24시는 24시/0시 순환에 반영)
    h_norm = 0 if hour == 24 else hour
    month = dt.month
    dayofweek = dt.weekday()  # 0(월) ~ 6(일)
    is_weekend = 1 if dayofweek in (5, 6) else 0
    # is_holiday: 실제 대한민국 공휴일 캘린더(2025) 기준. 주말과는 별개 지표이며,
    #             학습 파이프라인(`benchmarks/CastTransit.ipynb`)과 동일 정의를 사용한다.
    is_holiday = 1 if is_kr_public_holiday(dt) else 0
    is_rush_hour = 1 if hour in (8, 9, 18, 19) else 0

    # 1. 시계열 및 캘린더 피처 (8)
    month_sin = math.sin(2.0 * math.pi * month / 12.0)
    month_cos = math.cos(2.0 * math.pi * month / 12.0)
    hour_sin = math.sin(2.0 * math.pi * h_norm / 24.0)
    hour_cos = math.cos(2.0 * math.pi * h_norm / 24.0)

    # 2. 기상 관측 및 파생 피처 (8)
    t = float(weather.temp)
    w = max(float(weather.wind), 0.1)  # 0 미만 방지
    hum = float(weather.humidity)
    rain = max(float(weather.rain), 0.0)

    is_raining = 1 if rain > 0.0 else 0
    if rain <= 0.0:
        rain_intensity = 0
    elif rain < 3.0:
        rain_intensity = 1
    elif rain <= 10.0:
        rain_intensity = 2
    else:
        rain_intensity = 3

    # 체감온도 공식: 13.12 + 0.6215*T - 11.37*(V^0.16) + 0.3965*T*(V^0.16)
    v_pow = w ** 0.16
    sensible_temp = 13.12 + 0.6215 * t - 11.37 * v_pow + 0.3965 * t * v_pow

    # 불쾌지수 공식: 1.8*T - 0.55*(1 - H/100)*(1.8*T - 26) + 32
    discomfort_index = 1.8 * t - 0.55 * (1.0 - hum / 100.0) * (1.8 * t - 26.0) + 32.0

    # 3. 공간 인코딩 피처 (5)
    norm_district = normalize_district_name(district)
    district_code = float(DISTRICT_CODE_MAP.get(norm_district, 0))
    infra = DISTRICT_INFRA.get(norm_district, DISTRICT_INFRA["강남구"])
    district_subway_stations = float(infra["subway_stations"])
    district_bus_stops = float(infra["bus_stops"])
    district_bike_racks = float(infra["bike_racks"])
    commercial_density = float(infra["commercial_density"])

    # 4. 시계열 래그 및 이동통계 피처 (11) - 실시간 시계열 캐시 및 동적 집계 파이프라인
    stats = DISTRICT_STATS.get(norm_district, DISTRICT_STATS["강남구"])
    transit_lags = timeseries_cache.get_transit_lags(norm_district, hour, dt, stats)

    bike_lag_1h = float(transit_lags["bike_lag_1h"])
    bus_lag_1h = float(transit_lags["bus_lag_1h"])
    subway_lag_1h = float(transit_lags["subway_lag_1h"])
    bike_roll_mean_3h = float(transit_lags["bike_roll_mean_3h"])
    bus_roll_mean_3h = float(transit_lags["bus_roll_mean_3h"])
    subway_roll_mean_3h = float(transit_lags["subway_roll_mean_3h"])
    same_day_last_week_bike = float(transit_lags["same_day_last_week_bike"])
    same_day_last_week_bus = float(transit_lags["same_day_last_week_bus"])
    same_day_last_week_sub = float(transit_lags["same_day_last_week_sub"])

    temp_diff_1h, rain_diff_1h = timeseries_cache.get_weather_diff_1h(
        norm_district, current_temp=t, current_rain=rain, dt=dt
    )

    vector_32 = [
        # [0..7] 시계열 및 캘린더 피처
        month_sin, month_cos, hour_sin, hour_cos,
        float(dayofweek), float(is_weekend), float(is_holiday), float(is_rush_hour),
        # [8..15] 기상 관측 및 파생 피처
        t, w, hum, rain,
        float(is_raining), float(rain_intensity), sensible_temp, discomfort_index,
        # [16..20] 공간(위치) 인코딩 피처
        district_code, district_subway_stations, district_bus_stops,
        district_bike_racks, commercial_density,
        # [21..31] 시계열 래그 및 이동통계 피처
        bike_lag_1h, bus_lag_1h, subway_lag_1h,
        bike_roll_mean_3h, bus_roll_mean_3h, subway_roll_mean_3h,
        same_day_last_week_bike, same_day_last_week_bus, same_day_last_week_sub,
        temp_diff_1h, rain_diff_1h
    ]
    # 코드 상수(FEATURE_ORDER_32)와 실제 조립 순서·차원이 어긋나면 즉시 실패시킨다.
    # (기동 시 feature_schema.json 과도 대조되므로 학습↔서빙 드리프트가 조용히 통과하지 못한다.)
    assert len(vector_32) == len(FEATURE_ORDER_32), (
        f"피처 벡터 차원 불일치: 조립 {len(vector_32)} vs 정의 {len(FEATURE_ORDER_32)}"
    )
    return vector_32

def prepare_session_input(vector_32: list[float], session: ort.InferenceSession) -> np.ndarray:
    """
    32차원 피처 벡터를 로드된 ONNX 모델의 입력 텐서 차원에 맞게 정렬하여 반환합니다.
    - 학습 모델 세션이 25차원(레거시 배포본)을 기대하는 경우:
      [0..15](시간+날씨), [16](구코드), [21..26](1h/3h 래그 6개), [30..31](기온/강수 변화량 2개) = 25차원
      → 인덱스 정의의 단일 소스는 `feature_schema.legacy_25d_indices()` 입니다.
    - 32차원을 직접 지원하는 경우: 전체 32차원 전달
    """
    expected_dim = int(session.get_inputs()[0].shape[1])
    legacy_indices = legacy_25d_indices()
    if expected_dim == len(legacy_indices):  # 25차원 레거시 서브셋
        vec = [vector_32[i] for i in legacy_indices]
        return np.array([vec], dtype=np.float32)
    elif expected_dim == len(FEATURE_ORDER_32):  # 32차원 = 스키마 정렬
        return np.array([vector_32], dtype=np.float32)
    else:
        if len(vector_32) >= expected_dim:
            return np.array([vector_32[:expected_dim]], dtype=np.float32)
        padded = vector_32 + [0.0] * (expected_dim - len(vector_32))
        return np.array([padded], dtype=np.float32)

# ==============================================================================
# 6. 혼잡도 지수(0~100%) 및 MCDA 추천 스코어링 알고리즘
# ==============================================================================
def get_crowd_label(val: int) -> str:
    if val < 45:
        return "여유"
    elif val <= 75:
        return "보통"
    return "혼잡"

# ==============================================================================
# 6. 다기준 의사결정(MCDA) 추천 알고리즘 및 캘리브레이션 (AHP 기반)
# ==============================================================================
# 20.9만 건 서울시 교통카드-기상 실측 빅데이터 및 AHP(Analytic Hierarchy Process) 분석 기반 가중치:
# 기준 1: 기상 안전/쾌적성 (Weather Safety): 57.14% (w = 0.5714)
# 기준 2: 정시성/신뢰성 (Punctuality): 28.57% (w = 0.2857)
# 기준 3: 공간 쾌적도/혼잡도 (Crowd Comfort): 14.29% (w = 0.1429)
# 쌍대비교 일관성 지표: lambda_max = 3.00, CI = 0.000, CR = 0.000 < 0.10 (완벽한 일관성 충족)
AHP_CRITERIA_WEIGHTS = {
    "weather_safety": 0.5714,
    "punctuality": 0.2857,
    "crowd_comfort": 0.1429,
}

def get_crowd_color(val: int) -> str:
    if val < 45:
        return "#10B981"  # Emerald
    elif val <= 75:
        return "#38BDF8"  # Sky
    return "#F43F5E"      # Rose

def evaluate_subway(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """지하철 혼잡도(0~100%), 실측 캘리브레이션 MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["subway_p95"]
    v_min = stats["subway_min"]

    # 1) 혼잡도 계산: C_m = min(100, max(5, ((V - min) / (p95 - min)) * 100))
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) 실측 데이터 기반 MCDA 추천 스코어 (20.9만 건 실측 검증):
    # 지하철은 지하 터널 주행으로 직접 우천 노출 0점, 정시 운행률 99.2% 실측 기반 지연 리스크 2.0점, 혼잡도 페널티 0.40 * crowd
    weather_penalty = 0.0
    delay_risk = 2.0
    crowd_penalty = 0.40 * crowd
    score = int(round(max(25.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유 (Explainability)
    reasons = []
    if rain > 0:
        reasons.append("실측 정시성 99.2% 유지로 우천 도로 정체 완전 회피")
        reasons.append("지하 역사 이동으로 강수 및 빗길 미끄러짐 노출 최소화")
        if crowd > 75:
            reasons.append(f"우천 모달 시프트 집중으로 차내 혼잡도({crowd}%) 높음, 안전 유의")
        else:
            reasons.append("출퇴근 배차 간격 2.5~3분 유지로 신속한 이동")
    else:
        reasons.append("정시성 99.2% 유지로 가장 신뢰도 높은 이동 수단")
        reasons.append(f"현재 자치구 역사 혼잡도 {crowd}% 수준")
        reasons.append("중장거리 이동 시 최적 소요 시간 보장")

    return crowd, score, reasons

def evaluate_bus(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """버스 혼잡도(0~100%), 실측 캘리브레이션 MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["bus_p95"]
    v_min = stats["bus_min"]

    # 1) 혼잡도 계산
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) 실측 데이터 기반 MCDA 추천 스코어:
    # 버스는 노면 수막현상 감속 페널티 min(30, 3.5*rain + 5), 간선/지선 도로 통행속도 15~25% 감속 지연 리스크 12.0 + 2.5*rain, 혼잡도 페널티 0.35 * crowd
    weather_penalty = min(30.0, 3.5 * rain + (5.0 if rain > 0 else 0.0))
    delay_risk = 12.0 + 2.5 * rain
    crowd_penalty = 0.35 * crowd
    score = int(round(max(10.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유
    reasons = []
    if rain > 0:
        delay_est = round(3.5 + 1.2 * rain, 1)
        reasons.append(f"우천 노면 감속 및 도로 정체로 평균 {delay_est}분 지연 예상")
        reasons.append("간선/지선 교차로 및 주요 대로 병목 구간 통과")
        reasons.append("승하차 시 우산 이용 불편 및 차내 혼잡 가중")
    else:
        reasons.append("정상 도로 소통으로 목적지 인접 하차 편리")
        reasons.append(f"현재 노선 차내 혼잡도 {crowd}% 수준 운행 중")
        reasons.append("환승 할인 및 단거리 이동 접근성 우수")

    return crowd, score, reasons

def evaluate_bike(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """따릉이 혼잡도(0~100%), 실측 캘리브레이션 MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["bike_p95"]
    v_min = stats["bike_min"]

    # 1) 혼잡도 계산 (대여율)
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) 실측 20.9만 건 데이터 기반 캘리브레이션 MCDA 스코어:
    # 실측치: 강수 발생 시 즉시 -73.6%(0.1~1.0mm), -84.5%(1.0~3.0mm), -89.3%(3.0~5.0mm) 급감 반영
    # Step-and-Slope 곡선: rain > 0 시 즉시 40점 기본 감점 + 12.0*rain 추가 감점 (최대 85점 감점)
    weather_penalty = min(85.0, (40.0 + 12.0 * rain) if rain > 0 else 0.0)
    delay_risk = 8.0
    crowd_penalty = 0.15 * crowd
    score = int(round(max(5.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유
    reasons = []
    if rain > 0:
        if rain < 1.0:
            reasons.append(f"소우(강수량 {rain:.1f}mm)에도 실측 따릉이 이용객 73.6% 급감 패턴 관측")
            reasons.append("노면 미끄러짐 및 빗길 제동거리 증가로 안전사고 주의")
            reasons.append("우천 안전을 위해 지하철/버스 이용 권장")
        else:
            reasons.append(f"강수량 {rain:.1f}mm로 노면 수막현상 및 미끄러짐 위험 극심 (실측 이용률 85% 이상 급감)")
            reasons.append("우천 시 시야 제한 및 급제동 위험으로 자전거 운행 매우 부적합")
            reasons.append("지하철 또는 대체 대중교통 이용 강력 권고")
    else:
        reasons.append("쾌적한 날씨로 단거리 친환경 이동에 최적")
        reasons.append(f"현재 거치대 여유도 {100 - crowd}% 수준으로 대여 원활")
        reasons.append("교통 체증 없는 전용 자전거 도로 이용 권장")

    return crowd, score, reasons

def get_score_meta(mode_id: str, score: int) -> tuple[str, str]:
    """점수에 따른 라벨 및 테마 색상 반환"""
    if mode_id == "subway":
        if score >= 85:
            return "최우선 추천", "#38BDF8"
        elif score >= 70:
            return "추천", "#38BDF8"
        return "보통", "#FB923C"
    elif mode_id == "bus":
        if score >= 80:
            return "최우선 추천", "#38BDF8"
        elif score >= 65:
            return "추천", "#38BDF8"
        elif score >= 45:
            return "주의 필요", "#FB923C"
        return "비추천", "#F43F5E"
    else:  # bike
        if score >= 75:
            return "최우선 추천", "#10B981"
        elif score >= 55:
            return "쾌적", "#10B981"
        elif score >= 35:
            return "주의", "#FB923C"
        return "비추천", "#94A3B8"

def calculate_station_crowd(base: int, hour: int, rain: float, stop_type: str, station_name: str) -> int:
    """특정 지하철역/정류소의 시간대 첨두곡선, 기상 강수 민감도 및 고유 분산 반영 혼잡도 계산 (지도 마커와 100% 동기화)"""
    time_mult = 1.0
    if 8 <= hour <= 9:
        time_mult = 1.25
    elif hour == 7:
        time_mult = 1.15
    elif 18 <= hour <= 19:
        time_mult = 1.22
    elif hour == 17:
        time_mult = 1.15  # 퇴근 초입 (17시)
    elif hour == 20:
        time_mult = 1.12
    elif 12 <= hour <= 13:
        time_mult = 1.02
    elif 10 <= hour <= 16:
        time_mult = 0.78
    elif 21 <= hour <= 22:
        time_mult = 0.70
    else:
        time_mult = 0.42

    st_hash = 0
    for ch in station_name:
        st_hash = ((st_hash << 5) - st_hash) + ord(ch)
        st_hash = st_hash & 0xFFFFFFFF
        if st_hash >= 0x80000000:
            st_hash -= 0x100000000
    hash_offset = (abs(st_hash) % 7) - 3

    if stop_type == "bike":
        bike_rain_penalty = int(round(-2.5 * rain * 7.5))
        crowd = int(round(base * (0.35 if (hour >= 23 or hour <= 5) else 1.0))) + bike_rain_penalty
        return max(5, min(95, crowd))
    else:
        rain_bonus = min(15, int(round(1.2 * rain * 2.2)))
        crowd = int(round(base * time_mult)) + hash_offset + rain_bonus
        return max(10, min(99, crowd))

# ==============================================================================
# 7. 엔드포인트 구현
# ==============================================================================
@app.get("/health", tags=["System"])
async def health_check():
    """서버 헬스체크, 모델 로딩 상태 및 외부 공공 API 서킷 브레이커 상태 확인"""
    return {
        "status": "ok",
        "models_loaded": registry.is_loaded,
        "feature_schema": registry.schema_report(),
        "circuit_breakers": {
            "kma_weather": kma_circuit_breaker.state,
            "seoul_subway": subway_circuit_breaker.state,
            "seoul_bus": bus_circuit_breaker.state,
        },
        "available_districts": list(DISTRICT_CODE_MAP.keys()),
        "timestamp": datetime.now().astimezone().isoformat()
    }

@app.get("/api/v1/system/circuit-breakers", tags=["System"])
async def get_circuit_breakers_status():
    """
    공공 API 장애 차단 서킷 브레이커(KMA 기상청, 서울시 지하철, 서울시 버스) 실시간 상태 및 메트릭 조회 API
    - 각 서킷의 상태(CLOSED/OPEN/HALF_OPEN), 연속 실패 횟수, 쿨다운 잔여 시간, 스냅샷 보존 현황 등 제공
    """
    return {
        "status": "success",
        "timestamp": datetime.now().astimezone().isoformat(),
        "circuit_breakers": {
            "kma_weather": kma_circuit_breaker.get_status(),
            "seoul_subway": subway_circuit_breaker.get_status(),
            "seoul_bus": bus_circuit_breaker.get_status(),
            "seoul_bike": bike_circuit_breaker.get_status(),
        },
        "snapshot_cache_counts": {
            "weather_last_good": len(_weather_last_good),
            "subway_last_good": len(_subway_last_good),
            "bus_last_good": len(_bus_last_good),
            "bike_last_good": 1 if _bike_snapshot_last_good else 0,
        }
    }

@app.get("/api/v1/cache/timeseries-status", tags=["System"])
async def get_timeseries_cache_status(district: Optional[str] = None):
    """
    시계열 래그 및 기상 차분 캐시 레이어 상태 진단 API
    - 자치구 파라미터 전달 시 해당 자치구의 실시간 11차원 시계열 피처 즉시 반환
    """
    status_info = timeseries_cache.get_status()
    if district:
        norm_d = normalize_district_name(district)
        now = datetime.now()
        stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
        lags = timeseries_cache.get_transit_lags(norm_d, now.hour, now, stats)
        diff_temp, diff_rain = timeseries_cache.get_weather_diff_1h(norm_d, current_temp=15.0, current_rain=0.0, dt=now)
        status_info["query_district"] = norm_d
        status_info["current_lags_and_diffs"] = {
            **lags,
            "temp_diff_1h": diff_temp,
            "rain_diff_1h": diff_rain
        }
    return status_info

@app.post("/api/v1/predict/recommendation", response_model=PredictionResponse, tags=["Inference"])
async def predict_recommendation(req: PredictionRequest):
    """
    기상 상황 및 시공간 특성 기반 대중교통 수요 추론 및 최적 수단 추천 API
    - 사양서 규격의 32차원 피처 벡터 조립
    - ONNX 인메모리 세션 초고속 병렬 추론
    - 수단별 혼잡도 지수 및 MCDA 추천 스코어 산출
    - 응답 지연 시간(latency_ms) 반환
    """
    if not registry.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 추론 세션이 아직 준비되지 않았습니다."
        )

    t_start = time.perf_counter()

    norm_district = normalize_district_name(req.district)
    # 기상 입력 검증 및 디폴트 보정: 기상 정보가 생략된 경우 해당 시간대(req.hour)의 기상청 단기예보 자동 반영
    weather = req.weather
    if weather is None:
        try:
            h_fcst = await kma_forecast_manager.get_hour_weather(norm_district, req.hour, auth_key=KMA_AUTH_KEY)
            weather = WeatherInput(
                temp=h_fcst.temp,
                rain=h_fcst.rain,
                humidity=75.0 if h_fcst.rain > 0 else 50.0,
                wind=2.0
            )
        except Exception:
            weather = WeatherInput()

    # 1. 32차원 피처 벡터 조립
    features_32 = build_feature_vector(norm_district, req.hour, weather)

    # 2. 세션별 텐서 준비 및 ONNX 추론 실행
    bike_tensor = prepare_session_input(features_32, registry.bike_session)
    bus_tensor = prepare_session_input(features_32, registry.bus_session)
    subway_tensor = prepare_session_input(features_32, registry.subway_session)

    try:
        bike_pred = float(registry.bike_session.run(None, {"float_input": bike_tensor})[0].flatten()[0])
        bus_pred = float(registry.bus_session.run(None, {"float_input": bus_tensor})[0].flatten()[0])
        subway_pred = float(registry.subway_session.run(None, {"float_input": subway_tensor})[0].flatten()[0])
    except Exception as e:
        logger.error(f"ONNX 추론 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ONNX Model Inference Error: {str(e)}")

    bike_demand = max(0.0, bike_pred)
    bus_demand = max(0.0, bus_pred)
    subway_demand = max(0.0, subway_pred)

    # 실시간 관측 기상 및 추론 수요 스냅샷을 시계열 캐시에 동적 적재
    timeseries_cache.record_weather(
        norm_district,
        temp=weather.temp,
        rain=weather.rain,
        humidity=weather.humidity,
        wind=weather.wind
    )
    timeseries_cache.record_demand(
        norm_district,
        bike_vol=bike_demand,
        bus_vol=bus_demand,
        subway_vol=subway_demand
    )

    # 3. 혼잡도 지수 및 MCDA 추천 스코어링 계산
    subway_crowd, subway_score, subway_reasons = evaluate_subway(subway_demand, weather.rain, norm_district)
    bus_crowd, bus_score, bus_reasons = evaluate_bus(bus_demand, weather.rain, norm_district)
    bike_crowd, bike_score, bike_reasons = evaluate_bike(bike_demand, weather.rain, norm_district)

    subway_score_lbl, subway_score_col = get_score_meta("subway", subway_score)
    bus_score_lbl, bus_score_col = get_score_meta("bus", bus_score)
    bike_score_lbl, bike_score_col = get_score_meta("bike", bike_score)

    # 4. 기상 요약
    if weather.rain >= 10.0:
        cond = "Heavy Rain"
        desc = f"시간당 {weather.rain:.1f}mm 폭우, 침수 및 미끄러짐 주의"
    elif weather.rain >= 3.0:
        cond = "Rainy"
        desc = f"시간당 {weather.rain:.1f}mm 강수, 도로 감속 및 대중교통 혼잡"
    elif weather.rain > 0.0:
        cond = "Light Rain"
        desc = f"시간당 {weather.rain:.1f}mm 약한 비, 우천 보행 주의"
    elif weather.temp >= 30.0:
        cond = "Hot"
        desc = f"현재 기온 {weather.temp:.1f}°C, 폭염 주의 및 냉방 수단 권장"
    elif weather.temp <= -5.0:
        cond = "Cold"
        desc = f"현재 기온 {weather.temp:.1f}°C, 한파 주의 및 실내 이동 권장"
    else:
        cond = "Clear"
        desc = f"현재 기온 {weather.temp:.1f}°C, 쾌적한 이동 가능"

    recommendations = [
        RecommendationItem(
            id="subway",
            icon="🚇",
            name="지하철",
            score=subway_score,
            scoreLabel=subway_score_lbl,
            scoreColor=subway_score_col,
            reasons=subway_reasons,
            estimated_time_min=28,
            fare_krw=1550,
            crowd=subway_crowd,
            crowdLabel=get_crowd_label(subway_crowd),
            crowdColor=get_crowd_color(subway_crowd),
            predicted_volume=int(round(subway_demand)),
            predicted_demand=int(round(subway_demand)),
        ),
        RecommendationItem(
            id="bus",
            icon="🚌",
            name="버스",
            score=bus_score,
            scoreLabel=bus_score_lbl,
            scoreColor=bus_score_col,
            reasons=bus_reasons,
            estimated_time_min=42,
            fare_krw=1300,
            crowd=bus_crowd,
            crowdLabel=get_crowd_label(bus_crowd),
            crowdColor=get_crowd_color(bus_crowd),
            predicted_volume=int(round(bus_demand)),
            predicted_demand=int(round(bus_demand)),
        ),
        RecommendationItem(
            id="bike",
            icon="🚲",
            name="따릉이",
            score=bike_score,
            scoreLabel=bike_score_lbl,
            scoreColor=bike_score_col,
            reasons=bike_reasons,
            estimated_time_min=55,
            fare_krw=1000,
            crowd=bike_crowd,
            crowdLabel=get_crowd_label(bike_crowd),
            crowdColor=get_crowd_color(bike_crowd),
            predicted_volume=int(round(bike_demand)),
            predicted_demand=int(round(bike_demand)),
        ),
    ]

    # 특정 역사/정류소에 대한 정밀 추론 요청인 경우 역 특성 및 가중치 반영 (알약 UI 및 팝업 일치화)
    target_stop_type = req.stop_type or ("subway" if "역" in (req.station or "") else None)
    if req.station and req.base_crowd is not None:
        station_crowd = calculate_station_crowd(
            base=req.base_crowd,
            hour=req.hour,
            rain=weather.rain,
            stop_type=target_stop_type or "subway",
            station_name=req.station
        )
        for r in recommendations:
            if target_stop_type and r.id == target_stop_type:
                r.crowd = station_crowd
                r.crowdLabel = get_crowd_label(station_crowd)
                r.crowdColor = get_crowd_color(station_crowd)
                if r.id == "subway":
                    r.predicted_volume = int(round(station_crowd * 110))
                elif r.id == "bus":
                    r.predicted_volume = int(round(station_crowd * 18))
                elif r.id == "bike":
                    r.predicted_volume = int(round(station_crowd * 0.45))
                r.reasons.insert(0, f"{req.station} 역사 고유 특성 및 실시간 기상 관측({weather.temp:.1f}°C, 강수 {weather.rain}mm) 반영 AI 추론")

    # 추천 점수 내림차순 정렬
    recommendations.sort(key=lambda x: x.score, reverse=True)

    latency_ms = (time.perf_counter() - t_start) * 1000.0

    target_info = f"{req.district}" + (f" ({req.station})" if req.station else "")
    logger.info(
        f"⚡ [AI 수요/혼잡도 추론 완료] {target_info} | 기상: {weather.temp:.1f}°C, 강수 {weather.rain:.1f}mm | 소요: {latency_ms:.2f}ms"
    )
    for r in recommendations:
        logger.info(
            f"   ▶ [{r.name}] 혼잡도: {r.crowd}% ({r.crowdLabel}) | 예측이용량: {r.predicted_volume:,}명/시 | 추천점수: {r.score}점"
        )

    return PredictionResponse(
        status="success",
        timestamp=datetime.now().astimezone().isoformat(),
        district=req.district,
        station=req.station,
        corridor_district=norm_district if norm_district != req.district else None,
        latency_ms=round(latency_ms, 2),
        weather_summary=WeatherSummary(condition=cond, description=desc),
        recommendations=recommendations,
    )

@app.post("/api/v1/simulate/weather-impact", response_model=SimulationResponse, tags=["Simulation"])
async def simulate_weather_impact(req: SimulationRequest):
    """
    가상 기상 시뮬레이터 추론 API (What-If Simulator)
    - 강수량 및 기온 변화에 따른 모달 시프트(수요 전이율) 및 25개 자치구 혼잡도 즉시 산출
    """
    if not registry.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 추론 세션이 준비되지 않았습니다."
        )

    t_start = time.perf_counter()
    w_sim = WeatherInput(temp=req.simulated_temp, rain=req.simulated_rain_mm, humidity=85.0, wind=3.0)
    w_clear = WeatherInput(temp=req.simulated_temp, rain=0.0, humidity=50.0, wind=2.0)

    # 기준 구(강남구) 모달 시프트 산출
    feat_sim = build_feature_vector("강남구", req.hour, w_sim)
    feat_clear = build_feature_vector("강남구", req.hour, w_clear)

    t_bike_sim = prepare_session_input(feat_sim, registry.bike_session)
    t_bike_clear = prepare_session_input(feat_clear, registry.bike_session)
    t_bus_sim = prepare_session_input(feat_sim, registry.bus_session)
    t_bus_clear = prepare_session_input(feat_clear, registry.bus_session)
    t_sub_sim = prepare_session_input(feat_sim, registry.subway_session)
    t_sub_clear = prepare_session_input(feat_clear, registry.subway_session)

    b_sim = float(registry.bike_session.run(None, {"float_input": t_bike_sim})[0].flatten()[0])
    b_clear = max(1.0, float(registry.bike_session.run(None, {"float_input": t_bike_clear})[0].flatten()[0]))
    bus_sim = float(registry.bus_session.run(None, {"float_input": t_bus_sim})[0].flatten()[0])
    bus_clear = max(1.0, float(registry.bus_session.run(None, {"float_input": t_bus_clear})[0].flatten()[0]))
    sub_sim = float(registry.subway_session.run(None, {"float_input": t_sub_sim})[0].flatten()[0])
    sub_clear = max(1.0, float(registry.subway_session.run(None, {"float_input": t_sub_clear})[0].flatten()[0]))

    bike_shift = (b_sim - b_clear) / b_clear
    sub_shift = (sub_sim - sub_clear) / sub_clear
    bus_shift = (bus_sim - bus_clear) / bus_clear

    # 강수 시 따릉이 이탈 효과 반영 코멘터리
    if req.simulated_rain_mm > 0:
        commentary = f"강수량 {req.simulated_rain_mm:.1f}mm 발생 시 따릉이 이용의 {abs(bike_shift)*100:.1f}%가 이탈하여 지하철과 버스로 전이됩니다."
    else:
        commentary = "강수량 0mm의 맑은 날씨로 따릉이 및 버스 등 지상 교통 이용이 안정적입니다."

    # 25개 자치구별 시뮬레이션 혼잡도 집계
    district_congestions = []
    for d in DISTRICT_CODE_MAP.keys():
        f_vec = build_feature_vector(d, req.hour, w_sim)
        sub_t = prepare_session_input(f_vec, registry.subway_session)
        bus_t = prepare_session_input(f_vec, registry.bus_session)
        bike_t = prepare_session_input(f_vec, registry.bike_session)

        s_v = float(registry.subway_session.run(None, {"float_input": sub_t})[0].flatten()[0])
        bu_v = float(registry.bus_session.run(None, {"float_input": bus_t})[0].flatten()[0])
        bi_v = float(registry.bike_session.run(None, {"float_input": bike_t})[0].flatten()[0])

        s_c, _, _ = evaluate_subway(s_v, req.simulated_rain_mm, d)
        bu_c, _, _ = evaluate_bus(bu_v, req.simulated_rain_mm, d)
        bi_c, _, _ = evaluate_bike(bi_v, req.simulated_rain_mm, d)

        district_congestions.append(
            DistrictCongestionItem(
                district=d,
                subway_crowd=s_c,
                bus_crowd=bu_c,
                bike_crowd=bi_c
            )
        )

    latency_ms = (time.perf_counter() - t_start) * 1000.0

    return SimulationResponse(
        status="success",
        latency_ms=round(latency_ms, 2),
        simulation_params={"rain_mm": req.simulated_rain_mm, "temp": req.simulated_temp, "hour": req.hour},
        modal_shift_summary=ModalShiftSummary(
            bike_demand_change_rate=round(bike_shift, 3),
            subway_demand_change_rate=round(sub_shift, 3),
            bus_demand_change_rate=round(bus_shift, 3),
            commentary=commentary,
        ),
        district_congestion=district_congestions,
    )

@app.post("/api/v1/b2b/fleet-rebalance", response_model=B2BFleetRebalanceResponse, tags=["B2B Fleet Management"])
async def calculate_fleet_rebalancing(req: B2BFleetRebalanceRequest):
    """
    B2B 기업 및 지자체 운영사용 모빌리티 재배치(Fleet Rebalancing) 분석 API
    - 기상 변화 및 시간대별 25개 자치구 AI 추론 기반 수급 불균형(Surplus/Deficit) 분석
    - 따릉이(PM) 회수/배치 추천 대수 및 버스 배차 증감 가이드 산출
    """
    if not registry.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 추론 세션이 준비되지 않았습니다."
        )

    t_start = time.perf_counter()

    # 기상 조건 설정 (실시간 또는 사용자 요청)
    rain = req.rain_mm
    temp = req.temp
    if req.use_live_weather:
        try:
            fcst_item = await kma_forecast_manager.get_hour_weather("강남구", req.hour, auth_key=KMA_AUTH_KEY)
            if fcst_item:
                rain = float(fcst_item.rain)
                temp = float(fcst_item.temp)
        except Exception as e:
            logger.warning(f"B2B 실시간 기상 조회 폴백 적용: {e}")

    w_curr = WeatherInput(temp=temp, rain=rain, humidity=85.0 if rain > 0 else 55.0, wind=3.0 if rain > 0 else 1.8)
    w_base = WeatherInput(temp=20.0, rain=0.0, humidity=50.0, wind=1.8) # 쾌적한 맑은 날 기준

    district_items = []
    total_bike_surplus = 0
    total_bike_deficit = 0
    total_bus_extra = 0

    for d_name, d_code in DISTRICT_CODE_MAP.items():
        infra = DISTRICT_INFRA.get(d_name, DISTRICT_INFRA["강남구"])
        bike_racks = float(infra.get("bike_racks", 150.0))
        bus_stops = float(infra.get("bus_stops", 450.0))
        subway_stations = float(infra.get("subway_stations", 20.0))

        # 1. 특성 벡터 생성
        f_curr = build_feature_vector(d_name, req.hour, w_curr)
        f_base = build_feature_vector(d_name, req.hour, w_base)

        # 2. AI 모델 추론
        t_bk_c = prepare_session_input(f_curr, registry.bike_session)
        t_bk_b = prepare_session_input(f_base, registry.bike_session)
        t_bu_c = prepare_session_input(f_curr, registry.bus_session)
        t_bu_b = prepare_session_input(f_base, registry.bus_session)
        t_sb_c = prepare_session_input(f_curr, registry.subway_session)
        t_sb_b = prepare_session_input(f_base, registry.subway_session)

        bk_c = max(0.0, float(registry.bike_session.run(None, {"float_input": t_bk_c})[0].flatten()[0]))
        bk_b = max(1.0, float(registry.bike_session.run(None, {"float_input": t_bk_b})[0].flatten()[0]))
        bu_c = max(0.0, float(registry.bus_session.run(None, {"float_input": t_bu_c})[0].flatten()[0]))
        bu_b = max(1.0, float(registry.bus_session.run(None, {"float_input": t_bu_b})[0].flatten()[0]))
        sb_c = max(0.0, float(registry.subway_session.run(None, {"float_input": t_sb_c})[0].flatten()[0]))
        sb_b = max(1.0, float(registry.subway_session.run(None, {"float_input": t_sb_b})[0].flatten()[0]))

        bk_delta_pct = round(((bk_c - bk_b) / bk_b) * 100, 1)
        bu_delta_pct = round(((bu_c - bu_b) / bu_b) * 100, 1)
        sb_delta_pct = round(((sb_c - sb_b) / sb_b) * 100, 1)

        # 3. 따릉이(PM) 재배치 수량 산출
        # 거치대 1개소당 평균 약 10~15대 자전거 배치 용량 가정 (scale: racks * 12)
        fleet_capacity = bike_racks * 12.0
        
        if rain >= 1.0: # 우천 시: 이용 급감 -> 잉여 기기 회수 권고
            bike_status = "SURPLUS"
            bike_action = "RECALL"
            rebalance_qty = int(fleet_capacity * min(0.65, abs(bk_delta_pct) / 100.0 * 0.7))
            total_bike_surplus += rebalance_qty
            urgency = "CRITICAL" if rain >= 4.0 else "HIGH"
            guidance = f"우천({rain:.1f}mm)으로 따릉이 수요 {abs(bk_delta_pct)}% 급감. 유휴 기기 약 {rebalance_qty}대 침수 취약지/저류지 선제 회수 권장."
        elif bk_delta_pct >= 15.0: # 맑고 피크시간대: 수요 급증 -> 추가 배치 권고
            bike_status = "DEFICIT"
            bike_action = "DEPLOY"
            rebalance_qty = int(fleet_capacity * min(0.4, (bk_delta_pct / 100.0) * 0.5))
            total_bike_deficit += rebalance_qty
            urgency = "HIGH" if bk_delta_pct >= 30.0 else "MEDIUM"
            guidance = f"쾌적 기상 및 수요 {bk_delta_pct}% 급증. 주요 역세권 거점 거치대에 {rebalance_qty}대 추가 공급 권장."
        else:
            bike_status = "STABLE"
            bike_action = "MAINTAIN"
            rebalance_qty = 0
            urgency = "LOW"
            guidance = "수급 균형 안정. 현행 거치대 유지 관리 모드."

        # 4. 버스 배차 증차 권고
        if bu_delta_pct >= 10.0 and (rain > 0 or req.hour in [8, 9, 18, 19]):
            bus_status = "CROWDED"
            extra_trips = max(1, int(bu_delta_pct / 10.0))
            total_bus_extra += extra_trips
        elif bu_delta_pct <= -15.0:
            bus_status = "LIGHT"
            extra_trips = 0
        else:
            bus_status = "NORMAL"
            extra_trips = 0

        district_items.append(B2BDistrictRebalanceItem(
            district=d_name,
            district_code=d_code,
            bike_demand=round(bk_c, 1),
            bike_baseline=round(bk_b, 1),
            bike_delta_pct=bk_delta_pct,
            bike_status=bike_status,
            bike_action=bike_action,
            bike_rebalance_qty=rebalance_qty,
            bus_demand=round(bu_c, 1),
            bus_baseline=round(bu_b, 1),
            bus_delta_pct=bu_delta_pct,
            bus_status=bus_status,
            bus_recommended_trips=extra_trips,
            subway_demand=round(sb_c, 1),
            subway_baseline=round(sb_b, 1),
            subway_delta_pct=sb_delta_pct,
            infra={
                "bike_racks": int(bike_racks),
                "bus_stops": int(bus_stops),
                "subway_stations": int(subway_stations),
            },
            urgency=urgency,
            actionable_guidance=guidance,
        ))

    # 상위 5개 회수/배치 구역 추출
    surplus_list = sorted([d for d in district_items if d.bike_action == "RECALL"], key=lambda x: x.bike_rebalance_qty, reverse=True)
    deploy_list = sorted([d for d in district_items if d.bike_action == "DEPLOY"], key=lambda x: x.bike_rebalance_qty, reverse=True)

    top_recall = [{"district": d.district, "qty": d.bike_rebalance_qty, "delta_pct": d.bike_delta_pct, "urgency": d.urgency} for d in surplus_list[:5]]
    top_deploy = [{"district": d.district, "qty": d.bike_rebalance_qty, "delta_pct": d.bike_delta_pct, "urgency": d.urgency} for d in deploy_list[:5]]

    latency = round((time.perf_counter() - t_start) * 1000, 2)

    return B2BFleetRebalanceResponse(
        latency_ms=latency,
        weather_condition={
            "rain_mm": rain,
            "temp": temp,
            "hour": req.hour,
            "is_raining": rain > 0,
        },
        total_bike_surplus_qty=total_bike_surplus,
        total_bike_deficit_qty=total_bike_deficit,
        total_bus_extra_trips=total_bus_extra,
        top_recall_districts=top_recall,
        top_deploy_districts=top_deploy,
        district_rebalance_list=district_items,
    )

HOTSPOT_DEFINITIONS = [
    {"name": "강남 역삼동", "district": "강남구"},
    {"name": "도심 명동", "district": "중구"},
    {"name": "여의도동", "district": "영등포구"},
    {"name": "홍대 서교동", "district": "마포구"},
    {"name": "성수동 카페거리", "district": "성동구"},
    {"name": "가산디지털단지", "district": "금천구"},
    {"name": "잠실 롯데월드", "district": "송파구"},
    {"name": "판교 테크노밸리", "district": "성남시"},
]

LIVE_DISTRICT_CACHE: dict[tuple, tuple[float, LiveDistrictCongestionResponse]] = {}

@app.get("/api/v1/districts/live-congestion", response_model=LiveDistrictCongestionResponse, tags=["Inference"])
async def get_live_district_congestion(
    rain: Optional[float] = None,
    temp: Optional[float] = None,
    hour: Optional[int] = None,
    include_all: bool = False,
):
    """
    서울시 주요 8대 거점 및 25개 자치구 실시간 교통 혼잡도 AI 추론 API
    - 3개 ONNX 머신러닝 모델(지하철, 버스, 따릉이)을 배치 추론하여 거점별 실시간 혼잡도 반환
    - 기상청 실시간 관측치 또는 요청 파라미터 기반 기상 연동
    - 30초 인메모리 캐싱 지원 (<1ms 응답)
    """
    if not registry.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 추론 세션이 준비되지 않았습니다."
        )

    t_start = time.perf_counter()
    now = datetime.now()
    cur_hour = hour if hour is not None else now.hour
    cur_temp = temp if temp is not None else 19.4
    cur_rain = max(0.0, rain if rain is not None else 0.0)

    cache_key = (round(cur_rain, 1), round(cur_temp, 1), cur_hour, include_all)
    now_ts = time.time()
    if cache_key in LIVE_DISTRICT_CACHE:
        cached_time, cached_resp = LIVE_DISTRICT_CACHE[cache_key]
        if now_ts - cached_time < 30.0:
            return cached_resp

    def _infer_single_district(name: str, district_raw: str) -> DistrictLiveCongestionItem:
        norm_d = normalize_district_name(district_raw)
        w_in = WeatherInput(temp=cur_temp, rain=cur_rain, humidity=65.0, wind=2.5)
        f_vec = build_feature_vector(norm_d, cur_hour, w_in)

        sub_t = prepare_session_input(f_vec, registry.subway_session)
        bus_t = prepare_session_input(f_vec, registry.bus_session)
        bike_t = prepare_session_input(f_vec, registry.bike_session)

        s_v = max(0.0, float(registry.subway_session.run(None, {"float_input": sub_t})[0].flatten()[0]))
        bu_v = max(0.0, float(registry.bus_session.run(None, {"float_input": bus_t})[0].flatten()[0]))
        bi_v = max(0.0, float(registry.bike_session.run(None, {"float_input": bike_t})[0].flatten()[0]))

        s_c, _, _ = evaluate_subway(s_v, cur_rain, norm_d)
        bu_c, _, _ = evaluate_bus(bu_v, cur_rain, norm_d)
        bi_c, _, _ = evaluate_bike(bi_v, cur_rain, norm_d)

        # 기상 아이콘 결정
        if cur_rain >= 5.0:
            weather_icon = "🌧"
            cond = "Heavy Rain"
        elif cur_rain > 0.0:
            weather_icon = "🌦"
            cond = "Rainy"
        elif cur_temp >= 28.0:
            weather_icon = "☀️"
            cond = "Clear"
        elif cur_temp <= 0.0:
            weather_icon = "❄️"
            cond = "Snow/Cold"
        else:
            weather_icon = "☀️" if (6 <= cur_hour < 19) else "🌙"
            cond = "Clear"

        return DistrictLiveCongestionItem(
            name=name,
            district=norm_d,
            bus=bu_c,
            subway=s_c,
            bike=bi_c,
            weather=weather_icon,
            temp=round(cur_temp, 1),
            rain=round(cur_rain, 1),
            condition=cond,
        )

    hotspots = [_infer_single_district(h["name"], h["district"]) for h in HOTSPOT_DEFINITIONS]

    all_districts = None
    if include_all:
        all_districts = [_infer_single_district(d, d) for d in DISTRICT_CODE_MAP.keys()]

    latency_ms = (time.perf_counter() - t_start) * 1000.0

    resp = LiveDistrictCongestionResponse(
        status="success",
        timestamp=datetime.now().astimezone().isoformat(),
        hour=cur_hour,
        latency_ms=round(latency_ms, 2),
        hotspots=hotspots,
        all_districts=all_districts,
    )
    LIVE_DISTRICT_CACHE[cache_key] = (now_ts, resp)
    return resp

HOURLY_FORECAST_CACHE: dict[tuple, tuple[float, HourlyForecastResponse]] = {}

@app.get("/api/v1/transit/hourly-forecast", response_model=HourlyForecastResponse, tags=["Inference"])
async def get_hourly_transit_forecast(
    district: str = "강남구",
    rain: Optional[float] = None,
    temp: Optional[float] = None,
):
    """
    24시간(00시~23시) 시계열 기상 및 3대 대중교통(지하철, 버스, 따릉이) 수요/혼잡도 AI 추론 API
    - 자치구별 일교차 곡선 및 출퇴근 피크(08~09시, 17~18시) 동적 모델 추론
    - 60초 인메모리 캐싱 지원 (<2ms 초저지연)
    """
    if not registry.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 추론 세션이 준비되지 않았습니다."
        )

    t_start = time.perf_counter()
    norm_d = normalize_district_name(district)
    now = datetime.now()
    cur_hour = now.hour
    base_temp = temp if temp is not None else 19.4
    base_rain = max(0.0, rain if rain is not None else 0.0)

    # 사용자가 명시적으로 temp/rain을 오버라이드하지 않은 경우, 기상청 단기예보 24시간 실시간 데이터 조회
    kma_fcst_data = None
    if rain is None and temp is None:
        try:
            kma_fcst_data = await kma_forecast_manager.get_district_forecast(norm_d, auth_key=KMA_AUTH_KEY)
        except Exception as e:
            logger.warning(f"단기예보 시계열 조회 폴백: {e}")

    cache_key = (norm_d, round(base_rain, 1), round(base_temp, 1), cur_hour, kma_fcst_data is not None)
    now_ts = time.time()
    if cache_key in HOURLY_FORECAST_CACHE:
        cached_time, cached_resp = HOURLY_FORECAST_CACHE[cache_key]
        if now_ts - cached_time < 60.0:
            return cached_resp

    items = []
    for h in range(24):
        if kma_fcst_data and h < len(kma_fcst_data.hours):
            h_fcst = kma_fcst_data.hours[h]
            temp_h = h_fcst.temp
            rain_h = h_fcst.rain
            humid_h = 75.0 if rain_h > 0 else 50.0
            wind_h = 2.0
        else:
            # 1. 일교차 및 시간대별 기상 추정 곡선 (최저 05시, 최고 14시)
            temp_h = round(base_temp + 3.2 * math.sin((h - 8) * math.pi / 12), 1)
            rain_h = base_rain
            if base_rain > 0.0:
                rain_factor = 1.0 + 0.3 * math.sin((h - 6) * math.pi / 6)
                rain_h = round(max(0.0, base_rain * rain_factor), 1)
            
            humid_h = min(95.0, max(40.0, 65.0 - (temp_h - base_temp) * 2.0 + (15.0 if rain_h > 0 else 0.0)))
            wind_h = round(max(0.5, 2.0 + 0.8 * math.cos((h - 14) * math.pi / 12)), 1)

        w_in = WeatherInput(temp=temp_h, rain=rain_h, humidity=round(humid_h, 1), wind=wind_h)
        f_vec = build_feature_vector(norm_d, h, w_in)

        sub_t = prepare_session_input(f_vec, registry.subway_session)
        bus_t = prepare_session_input(f_vec, registry.bus_session)
        bike_t = prepare_session_input(f_vec, registry.bike_session)

        s_v = max(0.0, float(registry.subway_session.run(None, {"float_input": sub_t})[0].flatten()[0]))
        bu_v = max(0.0, float(registry.bus_session.run(None, {"float_input": bus_t})[0].flatten()[0]))
        bi_v = max(0.0, float(registry.bike_session.run(None, {"float_input": bike_t})[0].flatten()[0]))

        s_c, _, _ = evaluate_subway(s_v, rain_h, norm_d)
        bu_c, _, _ = evaluate_bus(bu_v, rain_h, norm_d)
        bi_c, _, _ = evaluate_bike(bi_v, rain_h, norm_d)

        is_peak = (8 <= h <= 9) or (17 <= h <= 18)

        items.append(HourlyForecastItem(
            hour=f"{h:02d}시",
            hour_num=h,
            temp=temp_h,
            rain=rain_h,
            humidity=round(humid_h, 1),
            wind=wind_h,
            subway=int(round(s_v)),
            bus=int(round(bu_v)),
            bike=int(round(bi_v)),
            subway_crowd=s_c,
            bus_crowd=bu_c,
            bike_crowd=bi_c,
            is_peak=is_peak,
        ))

    latency_ms = (time.perf_counter() - t_start) * 1000.0

    resp = HourlyForecastResponse(
        status="success",
        district=norm_d,
        timestamp=now.astimezone().isoformat(),
        current_hour=cur_hour,
        latency_ms=round(latency_ms, 2),
        hourly=items,
        forecast=items,
    )
    HOURLY_FORECAST_CACHE[cache_key] = (now_ts, resp)
    return resp

# ==============================================================================
# 지능형 동적 Fallback 생성기 (계절/시간대 및 정류소 문맥 인식)
# ==============================================================================
def generate_intelligent_weather_fallback(
    target_name: str,
    station: Optional[str],
    nx: int,
    ny: int,
    base_date: str,
    base_time: str,
    source: str = "KMA_FALLBACK"
) -> dict:
    """시간대 및 월(계절) 기반 자연스러운 디폴트 기상 생성"""
    now = datetime.now()
    month = now.month
    hour = now.hour

    if 3 <= month <= 5:    # 봄
        base_t = 15.0
    elif 6 <= month <= 8:  # 여름
        base_t = 26.0
    elif 9 <= month <= 11: # 가을
        base_t = 17.5
    else:                  # 겨울
        base_t = 1.0

    hour_t = round(base_t + 4.0 * math.sin((hour - 8) * math.pi / 12), 1)

    return {
        "status": "success",
        "district": target_name,
        "station": station,
        "nx": nx,
        "ny": ny,
        "base_date": base_date,
        "base_time": base_time,
        "temp": hour_t,
        "rain": 0.0,
        "pty": "0",
        "pty_desc": "없음(맑음/흐림)",
        "humidity": 52.0,
        "wind": 1.8,
        "source": source
    }

def generate_intelligent_subway_fallback(raw_st: str, clean_st: str, source: str = "SEOUL_SUBWAY_FALLBACK") -> dict:
    """역명에 기반한 지능형 정상 운행 도착 정보 생성"""
    return {
        "status": "success",
        "station": raw_st,
        "clean_station": clean_st,
        "arrivals": [
            SubwayArrivalItem(
                line="수도권 전철",
                destination=f"{clean_st} 방면 운행",
                message="배차 간격 2~5분 정상 운행중",
                remaining_seconds=180,
                remaining_minutes=3,
                train_status="일반",
                updn_line="상행/내선"
            ),
            SubwayArrivalItem(
                line="수도권 전철",
                destination=f"{clean_st} 방면 운행",
                message="배차 간격 2~5분 정상 운행중",
                remaining_seconds=360,
                remaining_minutes=6,
                train_status="일반",
                updn_line="하행/외선"
            )
        ],
        "source": source
    }

def generate_intelligent_bus_fallback(stId: str, busRouteId: Optional[str] = None, source: str = "SEOUL_BUS_FALLBACK") -> dict:
    """정류소 ID에 기반한 지능형 버스 도착 정보 생성"""
    return {
        "status": "success",
        "st_id": stId,
        "arrivals": [
            BusArrivalItem(
                route_name="간선/지선",
                station_name=f"환승정류소({stId})",
                arrival_msg1="배차간격 유지 운행중",
                arrival_msg2="출발대기",
                station_order="1",
                bus_route_id=busRouteId
            )
        ],
        "source": source
    }

# ==============================================================================
# 8. 실시간 공공 API 연동 엔드포인트 (기상청 실황, 지하철 도착, 버스 도착)
# ==============================================================================

@app.get("/api/v1/weather/current", response_model=RealtimeWeatherResponse, tags=["Live Public APIs"])
async def get_current_weather(
    district: str = "강남구",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    station: Optional[str] = None
):
    """
    기상청 API허브 초단기실황(getUltraSrtNcst) 연동 실시간 기상 관측 API
    - 서킷 브레이커(Circuit Breaker) 및 직전 정상 스냅샷(Last Known Good) 캐시 적용
    """
    target_name, nx, ny = resolve_weather_target(district, lat=lat, lng=lng, station=station)

    now = datetime.now()
    if now.minute < 10:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now

    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")
    cache_key = f"{nx}_{ny}_{base_date}_{base_time}"
    nx_ny_key = f"{nx}_{ny}"

    curr_time = time.time()
    # 1. 1차 인메모리 유효 캐시 확인 (10분)
    if cache_key in _weather_cache:
        cached_ts, cached_data = _weather_cache[cache_key]
        if curr_time - cached_ts < 600:
            res = dict(cached_data)
            res["district"] = target_name
            res["station"] = station
            return RealtimeWeatherResponse(**res)

    # 2. 서킷 브레이커 차단(OPEN) 여부 확인
    if not kma_circuit_breaker.can_execute():
        # 서킷 OPEN 상태: 외부 호출 없이 즉시 스냅샷 또는 지능형 폴백 반환 (0ms)
        if nx_ny_key in _weather_last_good:
            stale_data = dict(_weather_last_good[nx_ny_key])
            stale_data["district"] = target_name
            stale_data["station"] = station
            stale_data["source"] = "KMA_CIRCUIT_OPEN_STALE"
            return RealtimeWeatherResponse(**stale_data)
        fallback_data = generate_intelligent_weather_fallback(
            target_name, station, nx, ny, base_date, base_time, source="KMA_CIRCUIT_OPEN_FALLBACK"
        )
        return RealtimeWeatherResponse(**fallback_data)

    if not KMA_AUTH_KEY:
        fallback_data = generate_intelligent_weather_fallback(
            target_name, station, nx, ny, base_date, base_time, source="KMA_NO_KEY_FALLBACK"
        )
        return RealtimeWeatherResponse(**fallback_data)

    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    params = {
        "authKey": KMA_AUTH_KEY,
        "pageNo": "1",
        "numOfRows": "10",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if items:
                    result = {item["category"]: item["obsrValue"] for item in items if "category" in item}
                    pty_desc_map = {
                        "0": "없음(맑음/흐림)", "1": "비", "2": "비/눈",
                        "3": "눈", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"
                    }
                    pty_val = str(result.get("PTY", "0"))
                    rain_val = float(result.get("RN1", 0.0) or 0.0)
                    temp_val = float(result.get("T1H", 15.0) or 15.0)
                    reh_val = float(result.get("REH", 50.0) or 50.0)
                    wsd_val = float(result.get("WSD", 2.0) or 2.0)

                    resp_data = {
                        "status": "success",
                        "district": target_name,
                        "station": station,
                        "nx": nx,
                        "ny": ny,
                        "base_date": base_date,
                        "base_time": base_time,
                        "temp": round(temp_val, 1),
                        "rain": round(rain_val, 1),
                        "pty": pty_val,
                        "pty_desc": pty_desc_map.get(pty_val, "맑음"),
                        "humidity": round(reh_val, 1),
                        "wind": round(wsd_val, 1),
                        "source": "KMA_APIHUB_LIVE"
                    }
                    kma_circuit_breaker.record_success()
                    _weather_cache[cache_key] = (curr_time, resp_data)
                    _weather_last_good[nx_ny_key] = resp_data
                    timeseries_cache.record_weather(
                        target_name,
                        temp=resp_data["temp"],
                        rain=resp_data["rain"],
                        humidity=resp_data["humidity"],
                        wind=resp_data["wind"]
                    )
                    return RealtimeWeatherResponse(**resp_data)
                else:
                    kma_circuit_breaker.record_failure("Empty items in KMA response")
            else:
                kma_circuit_breaker.record_failure(f"HTTP {res.status_code}")
    except Exception as e:
        logger.warning(f"KMA API call failed: {e}, activating circuit breaker & fallback.")
        kma_circuit_breaker.record_failure(str(e))

    # 실패 시: 1순위 직전 정상 스냅샷 반환, 2순위 지능형 폴백
    if nx_ny_key in _weather_last_good:
        stale_data = dict(_weather_last_good[nx_ny_key])
        stale_data["district"] = target_name
        stale_data["station"] = station
        stale_data["source"] = "KMA_CACHED_STALE"
        return RealtimeWeatherResponse(**stale_data)

    fallback_data = generate_intelligent_weather_fallback(
        target_name, station, nx, ny, base_date, base_time, source="KMA_APIHUB_FALLBACK"
    )
    timeseries_cache.record_weather(
        target_name,
        temp=fallback_data["temp"],
        rain=fallback_data["rain"],
        humidity=fallback_data["humidity"],
        wind=fallback_data["wind"]
    )
    return RealtimeWeatherResponse(**fallback_data)


@app.get("/api/v1/weather/forecast/hourly", response_model=District24hForecast, tags=["Live Public APIs"])
async def get_hourly_weather_forecast(district: str = "강남구"):
    """
    기상청 단기예보(nph-dfs_shrt_grd) 연동 24시간 시간대별 기상(기온, 강수량, 하늘상태, 아이콘) 조회 API
    - 한반도 149x253 격자 기반 서울 25개 자치구 초저지연(<1ms) 인메모리 캐시 제공
    """
    return await kma_forecast_manager.get_district_forecast(district, auth_key=KMA_AUTH_KEY)


@app.get("/api/v1/transit/subway/arrival", response_model=SubwayArrivalResponse, tags=["Live Public APIs"])
async def get_subway_arrival(station: str = "강남"):
    """
    서울 열린데이터광장(realtimeStationArrival) 연동 실시간 지하철 도착 정보 API (15초 캐싱)
    - 서킷 브레이커(Circuit Breaker) 및 직전 정상 스냅샷(Last Known Good) 캐시 적용
    """
    raw_st = station.strip()
    clean_st = re.sub(r"역$", "", raw_st)
    if not clean_st:
        clean_st = raw_st

    curr_time = time.time()
    # 1. 1차 인메모리 유효 캐시 확인 (15초)
    if clean_st in _subway_cache:
        cached_ts, cached_data = _subway_cache[clean_st]
        if curr_time - cached_ts < 15:
            return SubwayArrivalResponse(**cached_data)

    # 2. 서킷 브레이커 차단(OPEN) 여부 확인
    if not subway_circuit_breaker.can_execute():
        if clean_st in _subway_last_good:
            stale_data = dict(_subway_last_good[clean_st])
            stale_data["station"] = raw_st
            stale_data["clean_station"] = clean_st
            stale_data["source"] = "SEOUL_SUBWAY_CIRCUIT_OPEN_STALE"
            return SubwayArrivalResponse(**stale_data)
        fallback_data = generate_intelligent_subway_fallback(raw_st, clean_st, source="SEOUL_SUBWAY_CIRCUIT_OPEN_FALLBACK")
        return SubwayArrivalResponse(**fallback_data)

    key = SEOUL_SUBWAY_KEY or "sample"
    # 서울역은 서울시 공공데이터에 일반 노선(1·4·경의중앙·공항)은 '서울', GTX-A는 '서울역'으로 분리 등록되어 있어 둘 다 병렬 조회
    query_stations = ["서울", "서울역"] if clean_st == "서울" else [clean_st]

    subway_line_map = {
        "1001": "1호선", "1002": "2호선", "1003": "3호선", "1004": "4호선",
        "1005": "5호선", "1006": "6호선", "1007": "7호선", "1008": "8호선",
        "1009": "9호선", "1063": "경의중앙선", "1065": "공항철도", "1067": "경춘선",
        "1071": "수인분당선", "1075": "수인분당선", "1077": "신분당선", "1092": "우이신설선",
        "1093": "서해선", "1081": "경강선", "1032": "GTX-A"
    }

    arrivals: list[SubwayArrivalItem] = []
    call_success = False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            tasks = [
                client.get(f"http://swopenAPI.seoul.go.kr/api/subway/{key}/json/realtimeStationArrival/0/16/{urllib.parse.quote(q)}")
                for q in query_stations
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            seen_trains = set()
            for res in responses:
                if isinstance(res, httpx.Response) and res.status_code == 200:
                    data = res.json()
                    raw_list = data.get("realtimeArrivalList", [])
                    if raw_list:
                        call_success = True
                    for item in raw_list:
                        train_key = (
                            item.get("subwayId"),
                            item.get("btrainNo"),
                            item.get("trainLineNm"),
                            item.get("arvlMsg2")
                        )
                        if train_key in seen_trains:
                            continue
                        seen_trains.add(train_key)

                        subway_id = str(item.get("subwayId", ""))
                        line_name = subway_line_map.get(subway_id, f"{subway_id}호선")
                        barvl_dt = int(item.get("barvlDt", 0) or 0)
                        rem_min = max(1, round(barvl_dt / 60)) if barvl_dt > 0 else 1
                        arrivals.append(
                            SubwayArrivalItem(
                                line=line_name,
                                destination=item.get("trainLineNm", "열차 운행중"),
                                message=item.get("arvlMsg2", "도착 정보 준비중"),
                                remaining_seconds=barvl_dt,
                                remaining_minutes=rem_min,
                                train_status=item.get("btrainSttus", "일반"),
                                updn_line=item.get("updnLine", "상/하행")
                            )
                        )
            if call_success:
                subway_circuit_breaker.record_success()
    except Exception as e:
        logger.warning(f"Seoul Subway API error: {e}")
        subway_circuit_breaker.record_failure(str(e))

    if arrivals:
        resp_data = {
            "status": "success",
            "station": raw_st,
            "clean_station": clean_st,
            "arrivals": arrivals,
            "source": "SEOUL_SUBWAY_LIVE"
        }
        _subway_cache[clean_st] = (curr_time, resp_data)
        _subway_last_good[clean_st] = resp_data
        return SubwayArrivalResponse(**resp_data)

    # API 장애 또는 도착 정보 부재 시: 스냅샷 캐시 우선, 그 후 지능형 Fallback
    if clean_st in _subway_last_good:
        stale_data = dict(_subway_last_good[clean_st])
        stale_data["station"] = raw_st
        stale_data["clean_station"] = clean_st
        stale_data["source"] = "SEOUL_SUBWAY_CACHED_STALE"
        return SubwayArrivalResponse(**stale_data)

    fallback_data = generate_intelligent_subway_fallback(
        raw_st, clean_st, source="SEOUL_SUBWAY_LIVE" if call_success else "SEOUL_SUBWAY_FALLBACK"
    )
    return SubwayArrivalResponse(**fallback_data)


@app.get("/api/v1/transit/bus/arrival", response_model=BusArrivalResponse, tags=["Live Public APIs"])
async def get_bus_arrival(stId: str = "111000299", busRouteId: Optional[str] = None):
    """
    공공데이터포털(서울특별시_버스도착정보조회) 연동 실시간 버스 도착 정보 API (15초 캐싱)
    - 서킷 브레이커(Circuit Breaker) 및 직전 정상 스냅샷(Last Known Good) 캐시 적용
    """
    cache_key = f"{stId}_{busRouteId or 'all'}"
    curr_time = time.time()
    # 1. 1차 인메모리 유효 캐시 확인 (15초)
    if cache_key in _bus_cache:
        cached_ts, cached_data = _bus_cache[cache_key]
        if curr_time - cached_ts < 15:
            return BusArrivalResponse(**cached_data)

    # 2. 서킷 브레이커 차단(OPEN) 여부 확인
    if not bus_circuit_breaker.can_execute():
        if cache_key in _bus_last_good:
            stale_data = dict(_bus_last_good[cache_key])
            stale_data["st_id"] = stId
            stale_data["source"] = "SEOUL_BUS_CIRCUIT_OPEN_STALE"
            return BusArrivalResponse(**stale_data)
        fallback_data = generate_intelligent_bus_fallback(stId, busRouteId, source="SEOUL_BUS_CIRCUIT_OPEN_FALLBACK")
        return BusArrivalResponse(**fallback_data)

    arrivals: list[BusArrivalItem] = []
    call_success = False

    if DATA_GO_KR_BUS_KEY:
        try:
            decoded_key = urllib.parse.unquote(DATA_GO_KR_BUS_KEY)
            endpoint = "getArrInfoByRouteAll" if busRouteId else "getLowArrInfoByStId"
            url = f"http://ws.bus.go.kr/api/rest/arrive/{endpoint}"
            params = {"serviceKey": decoded_key, "resultType": "json"}
            if busRouteId:
                params["busRouteId"] = busRouteId
            else:
                params["stId"] = stId

            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    msg_body = data.get("msgBody") or {}
                    items = msg_body.get("itemList", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items[:10]:
                        arrivals.append(
                            BusArrivalItem(
                                route_name=item.get("rtNm", "간선/지선"),
                                station_name=item.get("stNm", "정류소"),
                                arrival_msg1=item.get("arrmsg1", "도착 정보 없음"),
                                arrival_msg2=item.get("arrmsg2", "정보 없음"),
                                station_order=item.get("staOrd"),
                                bus_route_id=item.get("busRouteId")
                            )
                        )
                    if arrivals:
                        call_success = True
                        bus_circuit_breaker.record_success()
                    else:
                        bus_circuit_breaker.record_success()
                else:
                    bus_circuit_breaker.record_failure(f"HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Seoul Bus API error: {e}")
            bus_circuit_breaker.record_failure(str(e))
    else:
        fallback_data = generate_intelligent_bus_fallback(stId, busRouteId, source="SEOUL_BUS_NO_KEY_FALLBACK")
        return BusArrivalResponse(**fallback_data)

    if arrivals:
        resp_data = {
            "status": "success",
            "st_id": stId,
            "arrivals": arrivals,
            "source": "SEOUL_BUS_LIVE"
        }
        _bus_cache[cache_key] = (curr_time, resp_data)
        _bus_last_good[cache_key] = resp_data
        return BusArrivalResponse(**resp_data)

    # API 장애 또는 도착 정보 부재 시: 스냅샷 캐시 우선, 그 후 지능형 Fallback
    if cache_key in _bus_last_good:
        stale_data = dict(_bus_last_good[cache_key])
        stale_data["st_id"] = stId
        stale_data["source"] = "SEOUL_BUS_CACHED_STALE"
        return BusArrivalResponse(**stale_data)

    fallback_data = generate_intelligent_bus_fallback(
        stId, busRouteId, source="SEOUL_BUS_LIVE" if call_success else "SEOUL_BUS_FALLBACK"
    )
    return BusArrivalResponse(**fallback_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ─────────────────────────────────────────────
# 서울시 버스정류장 이름 검색 API
# ─────────────────────────────────────────────

@app.get("/api/v1/transit/bus/stations/search", tags=["Live Public APIs"])
async def search_bus_stations(q: str):
    from fastapi import HTTPException

    keyword = q.strip()

    if not keyword:
        raise HTTPException(
            status_code=400,
            detail="검색어를 입력해 주세요."
        )

    if not DATA_GO_KR_BUS_KEY:
        raise HTTPException(
            status_code=503,
            detail="버스 API 인증키가 설정되지 않았습니다."
        )

    url = (
        "http://ws.bus.go.kr/api/rest/"
        "stationinfo/getStationByName"
    )

    params = {
        "serviceKey": urllib.parse.unquote(DATA_GO_KR_BUS_KEY),
        "stSrch": keyword,
        "resultType": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        header = data.get("msgHeader") or {}

        if str(header.get("headerCd")) != "0":
            raise HTTPException(
                status_code=502,
                detail=f"서울시 API 오류: {header.get('headerMsg')}"
            )

        body = data.get("msgBody") or {}
        items = body.get("itemList") or []

        if isinstance(items, dict):
            items = [items]

        stations = []

        for item in items:
            if str(item.get("arsId", "")) == "0":
                continue

            try:
                longitude = float(item["tmX"])
                latitude = float(item["tmY"])
            except (KeyError, TypeError, ValueError):
                continue

            if not (126 <= longitude <= 128 and 37 <= latitude <= 38):
                continue

            stations.append({
                "id": str(item.get("stId", "")),
                "name": item.get("stNm", ""),
                "arsId": str(item.get("arsId", "")),
                "coords": [longitude, latitude]
            })

        return {
            "status": "success",
            "query": keyword,
            "count": len(stations),
            "stations": stations,
            "source": "SEOUL_BUS_LIVE"
        }

    except httpx.HTTPError as exc:
        logger.warning("Bus station search error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="서울시 버스정류장 API 연결 실패"
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="서울시 API 응답 형식 오류"
        )


# ─────────────────────────────────────────────
# 서울시 지도 주변 버스정류장 조회 API
# ─────────────────────────────────────────────

@app.get("/api/v1/transit/bus/stations/nearby", tags=["Live Public APIs"])
async def get_nearby_bus_stations(
    lat: float,
    lng: float,
    radius: int = 500
):
    from fastapi import HTTPException

    if not (37.0 <= lat <= 38.0 and 126.0 <= lng <= 128.0):
        raise HTTPException(
            status_code=400,
            detail="좌표 범위를 확인해 주세요."
        )

    if not (1 <= radius <= 1500):
        raise HTTPException(
            status_code=400,
            detail="검색 반경은 1~1500m여야 합니다."
        )

    if not DATA_GO_KR_BUS_KEY:
        raise HTTPException(
            status_code=503,
            detail="버스 API 인증키가 설정되지 않았습니다."
        )

    url = (
        "http://ws.bus.go.kr/api/rest/"
        "stationinfo/getStationByPos"
    )

    params = {
        "serviceKey": urllib.parse.unquote(DATA_GO_KR_BUS_KEY),
        "tmX": lng,
        "tmY": lat,
        "radius": radius,
        "resultType": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        header = data.get("msgHeader") or {}

        if str(header.get("headerCd")) != "0":
            raise HTTPException(
                status_code=502,
                detail=f"서울시 API 오류: {header.get('headerMsg')}"
            )

        body = data.get("msgBody") or {}
        items = body.get("itemList") or []

        if isinstance(items, dict):
            items = [items]

        stations = []
        seen_ids = set()

        for item in items:
            station_id = str(
                item.get("stationId") or item.get("stId") or ""
            )
            ars_id = str(item.get("arsId") or "")

            if not station_id or station_id in seen_ids:
                continue

            if ars_id == "0":
                continue

            try:
                longitude = float(
                    item.get("gpsX") or item.get("tmX")
                )
                latitude = float(
                    item.get("gpsY") or item.get("tmY")
                )
            except (TypeError, ValueError):
                continue

            if not (126 <= longitude <= 128 and 37 <= latitude <= 38):
                continue

            seen_ids.add(station_id)

            stations.append({
                "id": station_id,
                "name": item.get("stationNm") or item.get("stNm") or "",
                "stId": station_id,
                "arsId": ars_id,
                "coords": [longitude, latitude],
                "distance": item.get("dist")
            })

        return {
            "status": "success",
            "count": len(stations),
            "center": [lng, lat],
            "radius": radius,
            "stations": stations,
            "source": "SEOUL_BUS_LIVE"
        }

    except httpx.HTTPError as exc:
        logger.warning("Nearby bus station API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="서울시 주변 정류장 API 연결 실패"
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="서울시 API 응답 형식 오류"
        )


# ─────────────────────────────────────────────
# 서울시 버스 노선별 경유 정류장 조회 API
# ─────────────────────────────────────────────

@app.get("/api/v1/transit/bus/routes/{bus_route_id}/stations", tags=["Live Public APIs"])
async def get_bus_route_stations(bus_route_id: str):
    """서울시 버스 노선 ID로 경유 정류장 순서 및 WGS84 좌표 조회."""
    route_id = bus_route_id.strip()

    if not route_id.isdigit() or len(route_id) > 12:
        raise HTTPException(
            status_code=400,
            detail="올바른 버스 노선 ID를 입력해 주세요."
        )

    if not DATA_GO_KR_BUS_KEY:
        raise HTTPException(
            status_code=503,
            detail="버스 API 인증키가 설정되지 않았습니다."
        )

    url = (
        "http://ws.bus.go.kr/api/rest/"
        "busRouteInfo/getStaionByRoute"
    )
    params = {
        "serviceKey": urllib.parse.unquote(DATA_GO_KR_BUS_KEY),
        "busRouteId": route_id,
        "resultType": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        header = data.get("msgHeader") or {}

        if str(header.get("headerCd")) != "0":
            raise HTTPException(
                status_code=502,
                detail=f"서울시 버스 노선 API 오류: {header.get('headerMsg', '알 수 없는 오류')}"
            )

        body = data.get("msgBody") or {}
        items = body.get("itemList") or []
        if isinstance(items, dict):
            items = [items]

        stations = []
        for item in items:
            try:
                longitude = float(item["gpsX"])
                latitude = float(item["gpsY"])
            except (KeyError, TypeError, ValueError):
                continue

            if not (126.0 <= longitude <= 128.0 and 37.0 <= latitude <= 38.0):
                continue

            try:
                sequence = int(item.get("seq"))
            except (TypeError, ValueError):
                continue

            station_id = str(item.get("station") or item.get("stId") or "")
            stations.append({
                "sequence": sequence,
                "name": item.get("stationNm") or "",
                "stId": station_id,
                "arsId": str(item.get("arsId") or ""),
                "coords": [longitude, latitude]
            })

        stations.sort(key=lambda station: station["sequence"])

        return {
            "status": "success",
            "bus_route_id": route_id,
            "count": len(stations),
            "stations": stations,
            "source": "SEOUL_BUS_LIVE"
        }

    except httpx.HTTPError as exc:
        logger.warning("Bus route stations API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="서울시 버스 노선 API 연결 실패"
        )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="서울시 버스 노선 API 응답 형식 오류"
        )

# ─────────────────────────────────────────────
# 서울시 버스 노선별 실시간 차량 위치 조회 API
# ─────────────────────────────────────────────

@app.get("/api/v1/transit/bus/routes/{bus_route_id}/positions", tags=["Live Public APIs"])
async def get_bus_route_positions(bus_route_id: str):
    """서울시 노선 ID에 속한 운행 차량의 실시간 GPS 위치 조회."""
    route_id = bus_route_id.strip()

    if not route_id.isdigit() or len(route_id) > 12:
        raise HTTPException(
            status_code=400,
            detail="올바른 버스 노선 ID를 입력해 주세요."
        )

    if not DATA_GO_KR_BUS_KEY:
        raise HTTPException(
            status_code=503,
            detail="버스 API 인증키가 설정되지 않았습니다."
        )

    url = (
        "http://ws.bus.go.kr/api/rest/"
        "buspos/getBusPosByRtid"
    )
    params = {
        "serviceKey": urllib.parse.unquote(DATA_GO_KR_BUS_KEY),
        "busRouteId": route_id,
        "resultType": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        header = data.get("msgHeader") or {}

        if str(header.get("headerCd")) != "0":
            raise HTTPException(
                status_code=502,
                detail=f"서울시 버스 위치 API 오류: {header.get('headerMsg', '알 수 없는 오류')}"
            )

        body = data.get("msgBody") or {}
        items = body.get("itemList") or []
        if isinstance(items, dict):
            items = [items]

        vehicles = []
        seen_ids = set()

        for item in items:
            vehicle_id = str(item.get("vehId") or "")
            if not vehicle_id or vehicle_id in seen_ids:
                continue

            # posX/posY는 투영좌표일 수 있으므로 GPS 또는 tmX/tmY만 사용
            try:
                longitude = float(item.get("gpsX") or item.get("tmX"))
                latitude = float(item.get("gpsY") or item.get("tmY"))
            except (TypeError, ValueError):
                continue

            if not (126.0 <= longitude <= 128.0 and 37.0 <= latitude <= 38.0):
                continue

            seen_ids.add(vehicle_id)
            vehicles.append({
                "vehicle_id": vehicle_id,
                "plate_no": str(item.get("plainNo") or ""),
                "coords": [longitude, latitude],
                "section_order": item.get("sectOrd"),
                "last_station_id": str(item.get("lastStnId") or ""),
                "at_stop": str(item.get("stopFlag")) == "1",
                "bus_type": item.get("busType"),
                "congestion": item.get("congetion"),
                "data_time": item.get("dataTm")
            })

        return {
            "status": "success",
            "bus_route_id": route_id,
            "count": len(vehicles),
            "vehicles": vehicles,
            "source": "SEOUL_BUS_LIVE"
        }

    except httpx.HTTPError as exc:
        logger.warning("Bus route positions API error: %s", exc)
        raise HTTPException(status_code=502, detail="서울시 버스 위치 API 연결 실패")
    except (ValueError, TypeError) as exc:
        logger.warning("Bus route positions response error: %s", exc)
        raise HTTPException(status_code=502, detail="서울시 버스 위치 API 응답 형식 오류")

# ─────────────────────────────────────────────
# 선택한 정류장에 가장 먼저 도착할 버스 2대의 실시간 위치
# - 서울시 도착정보 vehId1/vehId2 와 위치정보 vehId 매칭
# - 외부 API는 노선 단위로 응답하므로 백엔드에서 2대만 걸러 프론트에 전송
# ─────────────────────────────────────────────
_bus_approaching_cache: dict[str, tuple[float, dict]] = {}

@app.get("/api/v1/transit/bus/routes/{bus_route_id}/approaching", tags=["Live Public APIs"])
async def get_approaching_bus_positions(bus_route_id: str, stId: str):
    route_id = bus_route_id.strip()
    station_id = stId.strip()
    if not route_id.isdigit() or not (1 <= len(route_id) <= 12):
        raise HTTPException(status_code=400, detail="올바른 버스 노선 ID가 필요합니다.")
    if not station_id.isdigit() or not (1 <= len(station_id) <= 12):
        raise HTTPException(status_code=400, detail="올바른 정류장 ID가 필요합니다.")
    if not DATA_GO_KR_BUS_KEY:
        raise HTTPException(status_code=503, detail="버스 API 인증키가 설정되지 않았습니다.")

    cache_key = f"{station_id}:{route_id}"
    now = time.monotonic()
    cached = _bus_approaching_cache.get(cache_key)
    if cached and now - cached[0] < 20:
        return cached[1]

    # 도착정보에는 정류장을 향해 오는 첫 번째/두 번째 차량의 고유 ID가 제공됨.
    # 기존 /arrival 와 같은 공공데이터 조회 API를 사용하되, vehId1/vehId2를 활용한다.
    params = {
        "serviceKey": urllib.parse.unquote(DATA_GO_KR_BUS_KEY),
        "stId": station_id,
        "resultType": "json"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                "http://ws.bus.go.kr/api/rest/arrive/getLowArrInfoByStId",
                params=params
            )
            res.raise_for_status()
        arrival_data = res.json()
        header = arrival_data.get("msgHeader") or {}
        if str(header.get("headerCd")) != "0":
            raise HTTPException(
                status_code=502,
                detail=f"서울시 버스 도착 API 오류: {header.get('headerMsg', '알 수 없는 오류')}"
            )
        arrival_items = (arrival_data.get("msgBody") or {}).get("itemList") or []
        if isinstance(arrival_items, dict):
            arrival_items = [arrival_items]
    except httpx.HTTPError as exc:
        logger.warning("Approaching bus arrival API error: %s", exc)
        raise HTTPException(status_code=502, detail="서울시 버스 도착 API 연결 실패")
    except (ValueError, TypeError, AttributeError) as exc:
        logger.warning("Approaching bus arrival response error: %s", exc)
        raise HTTPException(status_code=502, detail="서울시 버스 도착 API 응답 형식 오류")

    matched_route = next(
        (item for item in arrival_items if str(item.get("busRouteId") or "") == route_id),
        None
    )
    requested_vehicles = []
    if matched_route:
        for order in (1, 2):
            vehicle_id = str(matched_route.get(f"vehId{order}") or "").strip()
            if vehicle_id and vehicle_id != "0" and all(
                entry["vehicle_id"] != vehicle_id for entry in requested_vehicles
            ):
                requested_vehicles.append({
                    "vehicle_id": vehicle_id,
                    "arrival_order": order,
                    "arrival_message": str(matched_route.get(f"arrmsg{order}") or "")
                })

    # 도착 예정 차량의 ID가 없는 경우에는 추정으로 다른 버스를 표시하지 않는다.
    if not requested_vehicles:
        payload = {
            "status": "success", "bus_route_id": route_id, "station_id": station_id,
            "count": 0, "vehicles": [],
            "message": "현재 확인 가능한 첫차·다음 차 차량 ID가 없습니다.",
            "source": "SEOUL_BUS_LIVE"
        }
        _bus_approaching_cache[cache_key] = (time.monotonic(), payload)
        return payload

    # 기존 실시간 위치 API의 검증/좌표 가공 코드를 재사용한다.
    position_data = await get_bus_route_positions(route_id)
    position_by_id = {
        str(vehicle.get("vehicle_id")): vehicle
        for vehicle in position_data.get("vehicles", [])
    }
    vehicles = []
    for requested in requested_vehicles:
        position = position_by_id.get(requested["vehicle_id"])
        if position is None:
            continue
        vehicles.append({
            **position,
            "arrival_order": requested["arrival_order"],
            "arrival_message": requested["arrival_message"]
        })

    payload = {
        "status": "success", "bus_route_id": route_id, "station_id": station_id,
        "count": len(vehicles), "vehicles": vehicles,
        "message": "" if len(vehicles) == len(requested_vehicles) else "일부 차량의 GPS 위치가 아직 제공되지 않습니다.",
        "source": "SEOUL_BUS_LIVE"
    }
    _bus_approaching_cache[cache_key] = (time.monotonic(), payload)
    # 반복 조회 중 키가 무제한 늘지 않도록 오래된 캐시만 정리
    if len(_bus_approaching_cache) > 200:
        expiry = time.monotonic() - 60
        for key, (saved_at, _) in list(_bus_approaching_cache.items()):
            if saved_at < expiry:
                _bus_approaching_cache.pop(key, None)
    return payload

# ─────────────────────────────────────────────
# 서울시 따릉이(공공자전거) 실시간 대여소 API
# ─────────────────────────────────────────────

BIKE_SNAPSHOT_TTL_SEC = 60
BIKE_PAGE_SIZE = 1000
BIKE_MAX_PAGES = 5


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_bike_row(row: dict) -> Optional[dict]:
    try:
        lat = float(row.get("stationLatitude"))
        lng = float(row.get("stationLongitude"))
        rack_total = int(float(row.get("rackTotCnt") or 0))
        bikes = int(float(row.get("parkingBikeTotCnt") or 0))
    except (TypeError, ValueError):
        return None
    if not (37.0 <= lat <= 38.0 and 126.0 <= lng <= 128.0):
        return None
    station_id = str(row.get("stationId") or "")
    if not station_id:
        return None
    return {
        "id": station_id,
        "name": str(row.get("stationName") or "").strip(),
        "coords": [lng, lat],
        "rackTotal": rack_total,
        "availableBikes": bikes,
        "shared": int(float(row.get("shared") or 0)),
    }


async def _fetch_bike_snapshot() -> tuple[list[dict], str]:
    """전체 대여소 스냅샷을 반환한다. (stations, source)
    1) 60초 인메모리 캐시 → 2) 서킷 OPEN 시 last_good → 3) 라이브 호출 → 4) 실패 시 last_good
    모두 불가하면 HTTPException(503)을 발생시켜 프론트가 정적 데이터로 fallback 하도록 한다.
    """
    global _bike_snapshot_cache, _bike_snapshot_last_good
    now = time.time()

    if _bike_snapshot_cache and now - _bike_snapshot_cache[0] < BIKE_SNAPSHOT_TTL_SEC:
        return _bike_snapshot_cache[1], "SEOUL_BIKE_LIVE"

    if not SEOUL_BIKE_KEY:
        raise HTTPException(status_code=503, detail="따릉이 API 인증키가 설정되지 않았습니다.")

    if not bike_circuit_breaker.can_execute():
        if _bike_snapshot_last_good:
            return _bike_snapshot_last_good, "SEOUL_BIKE_CIRCUIT_OPEN_STALE"
        raise HTTPException(status_code=503, detail="따릉이 API 일시 차단(서킷 OPEN)")

    stations: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            for page in range(BIKE_MAX_PAGES):
                start = page * BIKE_PAGE_SIZE + 1
                end = start + BIKE_PAGE_SIZE - 1
                url = f"http://openapi.seoul.go.kr:8088/{SEOUL_BIKE_KEY}/json/bikeList/{start}/{end}/"
                res = await client.get(url)
                res.raise_for_status()
                body = res.json().get("rentBikeStatus")
                if not body:
                    raise ValueError("bikeList 응답 형식 오류")
                code = (body.get("RESULT") or {}).get("CODE")
                if code == "INFO-200":  # 해당 범위 데이터 없음 → 종료
                    break
                if code != "INFO-000":
                    raise ValueError(f"bikeList 오류 코드: {code}")
                rows = body.get("row") or []
                for row in rows:
                    parsed = _parse_bike_row(row)
                    if parsed:
                        stations[parsed["id"]] = parsed
                if len(rows) < BIKE_PAGE_SIZE:
                    break
        if not stations:
            raise ValueError("대여소 데이터가 비어 있습니다.")
    except Exception as exc:
        logger.warning("Seoul bike API error: %s", exc)
        bike_circuit_breaker.record_failure(str(exc))
        if _bike_snapshot_last_good:
            return _bike_snapshot_last_good, "SEOUL_BIKE_CACHED_STALE"
        raise HTTPException(status_code=503, detail="서울시 따릉이 API 연결 실패")

    result = list(stations.values())
    bike_circuit_breaker.record_success()
    _bike_snapshot_cache = (now, result)
    _bike_snapshot_last_good = result
    return result, "SEOUL_BIKE_LIVE"


@app.get("/api/v1/transit/bike/stations/nearby", tags=["Live Public APIs"])
async def get_nearby_bike_stations(lat: float, lng: float, radius: int = 500, limit: int = 100):
    if not (37.0 <= lat <= 38.0 and 126.0 <= lng <= 128.0):
        raise HTTPException(status_code=400, detail="좌표 범위를 확인해 주세요.")
    if not (1 <= radius <= 3000):
        raise HTTPException(status_code=400, detail="검색 반경은 1~3000m여야 합니다.")
    limit = max(1, min(limit, 300))

    stations, source = await _fetch_bike_snapshot()
    nearby = []
    for s in stations:
        dist = _haversine_m(lat, lng, s["coords"][1], s["coords"][0])
        if dist <= radius:
            nearby.append({**s, "distance": round(dist)})
    nearby.sort(key=lambda s: s["distance"])
    nearby = nearby[:limit]
    return {
        "status": "success",
        "count": len(nearby),
        "center": [lng, lat],
        "radius": radius,
        "stations": nearby,
        "source": source,
    }


@app.get("/api/v1/transit/bike/stations/search", tags=["Live Public APIs"])
async def search_bike_stations(q: str, limit: int = 30):
    keyword = q.strip()
    if len(keyword) < 2:
        raise HTTPException(status_code=400, detail="검색어는 2자 이상 입력해 주세요.")
    limit = max(1, min(limit, 100))

    stations, source = await _fetch_bike_snapshot()
    matched = [s for s in stations if keyword in s["name"]][:limit]
    return {
        "status": "success",
        "count": len(matched),
        "stations": matched,
        "source": source,
    }


@app.get("/api/v1/transit/bike/stations/by-number/{station_no}", tags=["Live Public APIs"])
async def get_bike_station_by_number(station_no: str):
    """따릉이 대여소 번호(예: 2301)로 실시간 상태를 조회한다. 대여소명이 '2301. ...' 형식인 점을 이용."""
    prefix = f"{station_no.strip()}."
    stations, source = await _fetch_bike_snapshot()
    for s in stations:
        if s["name"].startswith(prefix):
            return {"status": "success", "station": s, "source": source}
    raise HTTPException(status_code=404, detail="해당 번호의 대여소를 찾을 수 없습니다.")

@app.get("/api/v1/transit/bike/stations/{station_id}", tags=["Live Public APIs"])
async def get_bike_station(station_id: str):
    stations, source = await _fetch_bike_snapshot()
    for s in stations:
        if s["id"] == station_id:
            return {"status": "success", "station": s, "source": source}
    raise HTTPException(status_code=404, detail="해당 대여소를 찾을 수 없습니다.")


# ==============================================================================
# 9. LangGraph × FactChat LLM 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 API (Issue #18)
# ==============================================================================

class MultimodalRouteRequest(BaseModel):
    from_station: str = Field("강남역", description="출발역 또는 출발 거점명")
    to_station: str = Field("서울역", description="도착역 또는 도착 거점명")
    district: str = Field("강남구", description="기준 자치구명")
    hour: Optional[int] = Field(None, ge=0, le=23, description="탐색 시간대 (0~23시)")
    weather: Optional[WeatherInput] = Field(None, description="기상 조건 오버라이드 (미지정 시 KMA 단기예보/실황 연동)")


async def _execute_multimodal_search(
    from_station: str,
    to_station: str,
    district: str = "강남구",
    hour: Optional[int] = None,
    weather_override: Optional[WeatherInput] = None,
) -> dict:
    norm_d = normalize_district_name(district)
    target_hour = hour if hour is not None else datetime.now().hour

    # 1. 기상 컨텍스트 결정 (명시적 오버라이드 우선 -> KMA 단기예보 시간대별 기상 연동)
    if weather_override is not None:
        w_in = weather_override
        w_ctx = {
            "temp": w_in.temp,
            "rain": w_in.rain,
            "humidity": w_in.humidity,
            "wind": w_in.wind,
            "pty_desc": "비" if w_in.rain > 0 else "맑음",
            "source": "USER_OVERRIDE",
        }
    else:
        try:
            h_fcst = await kma_forecast_manager.get_hour_weather(norm_d, target_hour, auth_key=KMA_AUTH_KEY)
            w_in = WeatherInput(
                temp=h_fcst.temp,
                rain=h_fcst.rain,
                humidity=75.0 if h_fcst.rain > 0 else 55.0,
                wind=2.2,
            )
            w_ctx = {
                "temp": h_fcst.temp,
                "rain": h_fcst.rain,
                "humidity": w_in.humidity,
                "wind": w_in.wind,
                "pty_desc": h_fcst.pty_desc,
                "sky_desc": h_fcst.sky_desc,
                "source": "KMA_SHORT_TERM_FORECAST",
            }
        except Exception:
            w_in = WeatherInput(temp=16.5, rain=0.0, humidity=55.0, wind=2.0)
            w_ctx = {
                "temp": 16.5,
                "rain": 0.0,
                "humidity": 55.0,
                "wind": 2.0,
                "pty_desc": "맑음",
                "source": "FALLBACK_WEATHER",
            }

    # 2. 32차원 ONNX 모델 추론으로 수단별 혼잡도 및 MCDA 점수 산출
    ai_cong = {
        "subway_crowd": 52,
        "bus_crowd": 58,
        "bike_crowd": 22,
        "subway_score": 88,
        "bus_score": 79,
        "bike_score": 82,
        "subway_volume": 28500,
        "bus_volume": 19200,
        "bike_volume": 340,
    }
    if registry.is_loaded:
        try:
            f_vec = build_feature_vector(norm_d, target_hour, w_in)
            sub_t = prepare_session_input(f_vec, registry.subway_session)
            bus_t = prepare_session_input(f_vec, registry.bus_session)
            bike_t = prepare_session_input(f_vec, registry.bike_session)

            s_v = max(0.0, float(registry.subway_session.run(None, {"float_input": sub_t})[0].flatten()[0]))
            bu_v = max(0.0, float(registry.bus_session.run(None, {"float_input": bus_t})[0].flatten()[0]))
            bi_v = max(0.0, float(registry.bike_session.run(None, {"float_input": bike_t})[0].flatten()[0]))

            s_c, s_sc, _ = evaluate_subway(s_v, w_in.rain, norm_d)
            bu_c, bu_sc, _ = evaluate_bus(bu_v, w_in.rain, norm_d)
            bi_c, bi_sc, _ = evaluate_bike(bi_v, w_in.rain, norm_d)

            ai_cong = {
                "subway_crowd": int(s_c),
                "bus_crowd": int(bu_c),
                "bike_crowd": int(bi_c),
                "subway_score": int(s_sc),
                "bus_score": int(bu_sc),
                "bike_score": int(bi_sc),
                "subway_volume": int(round(s_v)),
                "bus_volume": int(round(bu_v)),
                "bike_volume": int(round(bi_v)),
            }
        except Exception as exc:
            logger.warning(f"멀티모달 ONNX 추론 폴백: {exc}")

    # 3. 인메모리 캐시된 실시간 따릉이 스냅샷 및 실시간 지하철 도착 정보 연동
    live_bikes = _bike_snapshot_cache[1] if _bike_snapshot_cache else (_bike_snapshot_last_good or [])
    live_subway_arrs: list[dict] = []
    if SEOUL_SUBWAY_KEY:
        try:
            sub_resp = await get_subway_arrival(from_station)
            if sub_resp and sub_resp.source == 'SEOUL_SUBWAY_LIVE' and sub_resp.arrivals:
                live_subway_arrs = [
                    a.model_dump() if hasattr(a, 'model_dump') else (a.dict() if hasattr(a, 'dict') else dict(a))
                    for a in sub_resp.arrivals
                ]
        except Exception as exc:
            logger.debug('멀티모달 실시간 지하철 도착 연동 스킵: %s', exc)

    # 4. LangGraph StateGraph 파이프라인 실행
    result = multimodal_routing_engine.run_multimodal_search(
        from_query=from_station,
        to_query=to_station,
        district=norm_d,
        hour=target_hour,
        weather_context=w_ctx,
        ai_congestion=ai_cong,
        live_bike_snapshot=live_bikes,
        live_subway_arrivals=live_subway_arrs,
    )
    result["district"] = norm_d
    result["hour"] = target_hour
    return result


@app.post("/api/v1/routes/multimodal-search", tags=["Multimodal Routing"])
async def post_multimodal_route_search(req: MultimodalRouteRequest):
    """
    LangGraph StateGraph 및 FactChat LLM 기반 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 API
    - 강수/강풍 시 Weather Gate가 자동으로 따릉이(PM) First/Last-Mile 구간을 배제하고 안전 실내 환승 경로로 우회
    - 32차원 ONNX 실시간 혼잡도 예측 및 FactChat LLM (또는 XAI 엔진) 자연어 브리핑 제공
    """
    return await _execute_multimodal_search(
        from_station=req.from_station,
        to_station=req.to_station,
        district=req.district,
        hour=req.hour,
        weather_override=req.weather,
    )


@app.get("/api/v1/routes/multimodal-search", tags=["Multimodal Routing"])
async def get_multimodal_route_search(
    from_station: str = "강남역",
    to_station: str = "서울역",
    district: str = "강남구",
    hour: Optional[int] = None,
    rain: Optional[float] = None,
    temp: Optional[float] = None,
):
    """GET 방식 멀티모달 통합 경로 탐색 API (쿼리 파라미터 기반)"""
    w_override = None
    if rain is not None or temp is not None:
        w_override = WeatherInput(
            temp=temp if temp is not None else 16.5,
            rain=max(0.0, rain if rain is not None else 0.0),
            humidity=75.0 if (rain or 0.0) > 0 else 55.0,
            wind=2.2,
        )
    return await _execute_multimodal_search(
        from_station=from_station,
        to_station=to_station,
        district=district,
        hour=hour,
        weather_override=w_override,
    )

