import os
import sys
import re
import math
import time
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

# 공공 API 인메모리 캐시 (과도한 외부 호출 방지 및 SLA 10ms 보장)
_weather_cache: dict[str, tuple[float, dict]] = {}
_subway_cache: dict[str, tuple[float, dict]] = {}
_bus_cache: dict[str, tuple[float, dict]] = {}

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

# 25개 자치구별 대중교통 인프라 가중치 (지하철 역사수, 버스 정류소수, 따릉이 거치대수, 상업지구 밀도)
DISTRICT_INFRA: dict[str, dict[str, float]] = {
    "강남구": {"subway_stations": 34.0, "bus_stops": 540.0, "bike_racks": 165.0, "commercial_density": 1.45},
    "강동구": {"subway_stations": 16.0, "bus_stops": 390.0, "bike_racks": 110.0, "commercial_density": 0.85},
    "강북구": {"subway_stations": 13.0, "bus_stops": 420.0, "bike_racks": 85.0,  "commercial_density": 0.70},
    "강서구": {"subway_stations": 23.0, "bus_stops": 610.0, "bike_racks": 195.0, "commercial_density": 0.90},
    "관악구": {"subway_stations": 9.0,  "bus_stops": 480.0, "bike_racks": 125.0, "commercial_density": 0.85},
    "광진구": {"subway_stations": 11.0, "bus_stops": 290.0, "bike_racks": 115.0, "commercial_density": 0.95},
    "구로구": {"subway_stations": 15.0, "bus_stops": 510.0, "bike_racks": 130.0, "commercial_density": 1.05},
    "금천구": {"subway_stations": 5.0,  "bus_stops": 360.0, "bike_racks": 90.0,  "commercial_density": 1.00},
    "노원구": {"subway_stations": 18.0, "bus_stops": 540.0, "bike_racks": 150.0, "commercial_density": 0.80},
    "도봉구": {"subway_stations": 8.0,  "bus_stops": 390.0, "bike_racks": 95.0,  "commercial_density": 0.70},
    "동대문구": {"subway_stations": 16.0, "bus_stops": 490.0, "bike_racks": 125.0, "commercial_density": 1.05},
    "동작구": {"subway_stations": 17.0, "bus_stops": 440.0, "bike_racks": 110.0, "commercial_density": 0.90},
    "마포구": {"subway_stations": 18.0, "bus_stops": 560.0, "bike_racks": 160.0, "commercial_density": 1.25},
    "서대문구": {"subway_stations": 10.0, "bus_stops": 450.0, "bike_racks": 105.0, "commercial_density": 0.95},
    "서초구": {"subway_stations": 27.0, "bus_stops": 600.0, "bike_racks": 150.0, "commercial_density": 1.35},
    "성동구": {"subway_stations": 17.0, "bus_stops": 435.0, "bike_racks": 120.0, "commercial_density": 1.10},
    "성북구": {"subway_stations": 14.0, "bus_stops": 590.0, "bike_racks": 120.0, "commercial_density": 0.85},
    "송파구": {"subway_stations": 30.0, "bus_stops": 620.0, "bike_racks": 210.0, "commercial_density": 1.20},
    "양천구": {"subway_stations": 10.0, "bus_stops": 380.0, "bike_racks": 130.0, "commercial_density": 0.85},
    "영등포구": {"subway_stations": 21.0, "bus_stops": 510.0, "bike_racks": 175.0, "commercial_density": 1.40},
    "용산구": {"subway_stations": 15.0, "bus_stops": 350.0, "bike_racks": 100.0, "commercial_density": 1.15},
    "은평구": {"subway_stations": 16.0, "bus_stops": 510.0, "bike_racks": 135.0, "commercial_density": 0.75},
    "종로구": {"subway_stations": 19.0, "bus_stops": 380.0, "bike_racks": 120.0, "commercial_density": 1.35},
    "중구":   {"subway_stations": 26.0, "bus_stops": 240.0, "bike_racks": 110.0, "commercial_density": 1.45},
    "중랑구": {"subway_stations": 12.0, "bus_stops": 370.0, "bike_racks": 115.0, "commercial_density": 0.75},
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

def resolve_weather_target(district_str: str) -> tuple[str, int, int]:
    """
    기상청 관측소 격자 좌표(nx, ny) 및 표출 지역명 판별
    - 서울시 25개 자치구
    - 수도권 주요 인접 도시 (성남시, 광명시, 부천시, 고양시, 하남시, 수원시, 안양시, 남양주시 등)
    """
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
        if key in d_clean:
            return city_name, nx, ny

    # 서울 25개 자치구 정규화
    norm_d = normalize_district_name(d_clean)
    grid = DISTRICT_KMA_GRID.get(norm_d, {"nx": 61, "ny": 126})
    return norm_d, grid["nx"], grid["ny"]

# ==============================================================================
# 2. ONNX 세션 관리 및 Cold Start 방지 인메모리 로더
# ==============================================================================
class ModelRegistry:
    def __init__(self):
        self.bike_session: Optional[ort.InferenceSession] = None
        self.bus_session: Optional[ort.InferenceSession] = None
        self.subway_session: Optional[ort.InferenceSession] = None
        self.is_loaded: bool = False

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

# ── 실시간 공공 API 응답 스키마 ──
class RealtimeWeatherResponse(BaseModel):
    status: str = "success"
    district: str
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

# ==============================================================================
# 5. 사양서 규격의 32차원 Feature Vector 조립 함수 (build_feature_vector)
# ==============================================================================
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
    is_holiday = 1 if is_weekend else 0
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

    # 4. 시계열 래그 및 이동통계 피처 (11)
    stats = DISTRICT_STATS.get(norm_district, DISTRICT_STATS["강남구"])
    bike_base = float(stats["bike_mean"])
    bus_base = float(stats["bus_mean"])
    subway_base = float(stats["subway_mean"])

    bike_lag_1h = bike_base
    bus_lag_1h = bus_base
    subway_lag_1h = subway_base
    bike_roll_mean_3h = bike_base
    bus_roll_mean_3h = bus_base
    subway_roll_mean_3h = subway_base
    same_day_last_week_bike = bike_base
    same_day_last_week_bus = bus_base
    same_day_last_week_sub = subway_base
    temp_diff_1h = 0.0
    rain_diff_1h = 0.0

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
    return vector_32

def prepare_session_input(vector_32: list[float], session: ort.InferenceSession) -> np.ndarray:
    """
    32차원 피처 벡터를 로드된 ONNX 모델의 입력 텐서 차원에 맞게 정렬하여 반환합니다.
    - 학습 모델 세션이 25차원을 기대하는 경우:
      [0..15](시간+날씨), [16](구코드), [21..26](1h/3h 래그 6개), [30..31](기온/강수 변화량 2개) = 25차원
    - 32차원을 직접 지원하는 경우: 전체 32차원 전달
    """
    expected_dim = session.get_inputs()[0].shape[1]
    if expected_dim == 25:
        indices = list(range(17)) + [21, 22, 23, 24, 25, 26, 30, 31]
        vec = [vector_32[i] for i in indices]
        return np.array([vec], dtype=np.float32)
    elif expected_dim == 32:
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

def get_crowd_color(val: int) -> str:
    if val < 45:
        return "#10B981"  # Emerald
    elif val <= 75:
        return "#38BDF8"  # Sky
    return "#F43F5E"      # Rose

def evaluate_subway(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """지하철 혼잡도(0~100%), MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["subway_p95"]
    v_min = stats["subway_min"]

    # 1) 혼잡도 계산: C_m = min(100, max(5, ((V - min) / (p95 - min)) * 100))
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) MCDA 추천 스코어:
    # 지하철은 우천 영향 0, 정시성 페널티 2점, 혼잡도 페널티 0.40 * crowd
    weather_penalty = 0.0
    delay_risk = 2.0
    crowd_penalty = 0.40 * crowd
    score = int(round(max(25.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유 (Explainability)
    reasons = []
    if rain > 0:
        reasons.append("강수로 인한 도로 혼잡 회피 (정시성 99.2%)")
        reasons.append("지하 역사 이동으로 강수 노출 최소화")
        if crowd > 75:
            reasons.append(f"우천 집중으로 차내 혼잡도({crowd}%) 높음, 안전 유의")
        else:
            reasons.append("출퇴근 배차 간격 2.5~3분 유지로 신속한 이동")
    else:
        reasons.append("정시성 99.2% 유지로 가장 신뢰도 높은 이동 수단")
        reasons.append(f"현재 자치구 역사 혼잡도 {crowd}% 수준")
        reasons.append("중장거리 이동 시 최적 소요 시간 보장")

    return crowd, score, reasons

def evaluate_bus(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """버스 혼잡도(0~100%), MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["bus_p95"]
    v_min = stats["bus_min"]

    # 1) 혼잡도 계산
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) MCDA 추천 스코어:
    # 버스는 노면 감속 페널티 min(30, 3.5*rain + 5), 도로 지연 페널티 15 + 2.5*rain, 혼잡도 페널티 0.35 * crowd
    weather_penalty = min(30.0, 3.5 * rain + (5.0 if rain > 0 else 0.0))
    delay_risk = 15.0 + 2.5 * rain
    crowd_penalty = 0.35 * crowd
    score = int(round(max(10.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유
    reasons = []
    if rain > 0:
        delay_est = round(4.0 + 1.5 * rain, 1)
        reasons.append(f"우천 노면 감속으로 평균 {delay_est}분 지연 예상")
        reasons.append("간선/지선 교차로 및 주요 대로 병목 구간 통과")
        reasons.append("승하차 시 우산 이용 불편 및 차내 혼잡 가중")
    else:
        reasons.append("정상 도로 소통으로 목적지 인접 하차 편리")
        reasons.append(f"현재 노선 차내 혼잡도 {crowd}% 수준 운행 중")
        reasons.append("환승 할인 및 단거리 이동 접근성 우수")

    return crowd, score, reasons

def evaluate_bike(volume: float, rain: float, district: str) -> tuple[int, int, list[str]]:
    """따릉이 혼잡도(0~100%), MCDA 추천 스코어(0~100), 추천 사유 도출"""
    norm_d = normalize_district_name(district)
    stats = DISTRICT_STATS.get(norm_d, DISTRICT_STATS["강남구"])
    p95 = stats["bike_p95"]
    v_min = stats["bike_min"]

    # 1) 혼잡도 계산 (대여율)
    denom = max(1.0, p95 - v_min)
    crowd = int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))

    # 2) MCDA 추천 스코어:
    # 따릉이는 우천 시 치명적 감점 min(80, 25*rain + 15), 지연/신호 10점, 거치대 혼잡 페널티 0.15 * crowd
    weather_penalty = min(80.0, 25.0 * rain + (15.0 if rain > 0 else 0.0))
    delay_risk = 10.0
    crowd_penalty = 0.15 * crowd
    score = int(round(max(5.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

    # 3) 추천 사유
    reasons = []
    if rain > 0:
        reasons.append(f"강수량 {rain:.1f}mm로 노면 수막현상 및 미끄러짐 위험 극심")
        reasons.append("우천 시 자전거 이용객 급감(-80% 이상) 패턴 관측")
        reasons.append("우천 안전사고 예방을 위해 지하철/버스 이용 권고")
    else:
        reasons.append("쾌적한 날씨로 단거리 친환경 이동에 적합")
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

# ==============================================================================
# 7. 엔드포인트 구현
# ==============================================================================
@app.get("/health", tags=["System"])
async def health_check():
    """서버 헬스체크 및 모델 로딩 상태 확인"""
    return {
        "status": "ok",
        "models_loaded": registry.is_loaded,
        "available_districts": list(DISTRICT_CODE_MAP.keys()),
        "timestamp": datetime.now().astimezone().isoformat()
    }

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

    # 기상 입력 검증 및 디폴트 보정
    weather = req.weather or WeatherInput()
    norm_district = normalize_district_name(req.district)

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

    # 추천 점수 내림차순 정렬
    recommendations.sort(key=lambda x: x.score, reverse=True)

    latency_ms = (time.perf_counter() - t_start) * 1000.0

    return PredictionResponse(
        status="success",
        timestamp=datetime.now().astimezone().isoformat(),
        district=norm_district,
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

# ==============================================================================
# 8. 실시간 공공 API 연동 엔드포인트 (기상청 실황, 지하철 도착, 버스 도착)
# ==============================================================================

@app.get("/api/v1/weather/current", response_model=RealtimeWeatherResponse, tags=["Live Public APIs"])
async def get_current_weather(district: str = "강남구"):
    """
    기상청 API허브 초단기실황(getUltraSrtNcst) 연동 실시간 기상 관측 API
    - 서울시 25개 자치구 및 수도권 주요 8대 광역 거점 격자(nx, ny) 자동 매핑 및 10분 캐싱 지원
    """
    target_name, nx, ny = resolve_weather_target(district)

    now = datetime.now()
    if now.minute < 10:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now

    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")
    cache_key = f"{nx}_{ny}_{base_date}_{base_time}"

    curr_time = time.time()
    if cache_key in _weather_cache:
        cached_ts, cached_data = _weather_cache[cache_key]
        if curr_time - cached_ts < 600:
            res = dict(cached_data)
            res["district"] = target_name
            return RealtimeWeatherResponse(**res)

    if not KMA_AUTH_KEY:
        return RealtimeWeatherResponse(
            status="success",
            district=target_name,
            nx=nx,
            ny=ny,
            base_date=base_date,
            base_time=base_time,
            temp=16.0,
            rain=0.0,
            pty="0",
            pty_desc="없음(맑음/흐림)",
            humidity=50.0,
            wind=2.0,
            source="FALLBACK"
        )

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
        async with httpx.AsyncClient(timeout=5.0) as client:
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
                    _weather_cache[cache_key] = (curr_time, resp_data)
                    return RealtimeWeatherResponse(**resp_data)
    except Exception as e:
        logger.warning(f"KMA API call failed: {e}, using fallback.")

    fallback_data = {
        "status": "success",
        "district": target_name,
        "nx": nx,
        "ny": ny,
        "base_date": base_date,
        "base_time": base_time,
        "temp": 15.8,
        "rain": 0.0,
        "pty": "0",
        "pty_desc": "없음(맑음/흐림)",
        "humidity": 46.0,
        "wind": 2.4,
        "source": "KMA_APIHUB_FALLBACK"
    }
    return RealtimeWeatherResponse(**fallback_data)


@app.get("/api/v1/transit/subway/arrival", response_model=SubwayArrivalResponse, tags=["Live Public APIs"])
async def get_subway_arrival(station: str = "강남"):
    """
    서울 열린데이터광장(realtimeStationArrival) 연동 실시간 지하철 도착 정보 API (15초 캐싱)
    """
    raw_st = station.strip()
    clean_st = re.sub(r"역$", "", raw_st)
    if clean_st == "서울" or raw_st == "서울역":
        clean_st = "서울역"
    elif not clean_st:
        clean_st = raw_st

    curr_time = time.time()
    if clean_st in _subway_cache:
        cached_ts, cached_data = _subway_cache[clean_st]
        if curr_time - cached_ts < 15:
            return SubwayArrivalResponse(**cached_data)

    key = SEOUL_SUBWAY_KEY or "sample"
    encoded_station = urllib.parse.quote(clean_st)
    url = f"http://swopenAPI.seoul.go.kr/api/subway/{key}/json/realtimeStationArrival/0/8/{encoded_station}"

    subway_line_map = {
        "1001": "1호선", "1002": "2호선", "1003": "3호선", "1004": "4호선",
        "1005": "5호선", "1006": "6호선", "1007": "7호선", "1008": "8호선",
        "1009": "9호선", "1063": "경의중앙선", "1065": "공항철도", "1067": "경춘선",
        "1071": "수인분당선", "1075": "수인분당선", "1077": "신분당선", "1092": "우이신설선",
        "1093": "서해선", "1081": "경강선", "1032": "GTX-A"
    }

    arrivals: list[SubwayArrivalItem] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                raw_list = data.get("realtimeArrivalList", [])
                for item in raw_list:
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
    except Exception as e:
        logger.warning(f"Seoul Subway API error: {e}")

    if not arrivals:
        arrivals.append(
            SubwayArrivalItem(
                line="수도권 전철",
                destination=f"{clean_st} 방면 운행",
                message="배차 간격 2~5분 정상 운행중",
                remaining_seconds=180,
                remaining_minutes=3,
                train_status="일반",
                updn_line="내선/상행"
            )
        )

    resp_data = {
        "status": "success",
        "station": raw_st,
        "clean_station": clean_st,
        "arrivals": arrivals,
        "source": "SEOUL_SUBWAY_LIVE" if len(arrivals) > 1 or arrivals[0].remaining_seconds != 180 else "SEOUL_SUBWAY_FALLBACK"
    }
    _subway_cache[clean_st] = (curr_time, resp_data)
    return SubwayArrivalResponse(**resp_data)


@app.get("/api/v1/transit/bus/arrival", response_model=BusArrivalResponse, tags=["Live Public APIs"])
async def get_bus_arrival(stId: str = "111000299", busRouteId: Optional[str] = None):
    """
    공공데이터포털(서울특별시_버스도착정보조회) 연동 실시간 버스 도착 정보 API (15초 캐싱)
    """
    cache_key = f"{stId}_{busRouteId or 'all'}"
    curr_time = time.time()
    if cache_key in _bus_cache:
        cached_ts, cached_data = _bus_cache[cache_key]
        if curr_time - cached_ts < 15:
            return BusArrivalResponse(**cached_data)

    arrivals: list[BusArrivalItem] = []
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

            async with httpx.AsyncClient(timeout=5.0) as client:
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
        except Exception as e:
            logger.warning(f"Seoul Bus API error: {e}")

    if not arrivals:
        arrivals.append(
            BusArrivalItem(
                route_name="472",
                station_name="구산동사거리",
                arrival_msg1="출발대기",
                arrival_msg2="출발대기"
            )
        )

    resp_data = {
        "status": "success",
        "st_id": stId,
        "arrivals": arrivals,
        "source": "SEOUL_BUS_LIVE" if len(arrivals) > 1 or arrivals[0].arrival_msg1 != "출발대기" else "SEOUL_BUS_FALLBACK"
    }
    _bus_cache[cache_key] = (curr_time, resp_data)
    return BusArrivalResponse(**resp_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

