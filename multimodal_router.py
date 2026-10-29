"""
LangGraph 및 FactChat LLM 기반 멀티모달(지하철 + 버스 + 따릉이) 통합 경로 탐색 엔진
(Issue #18: Weather-Aware Multi-Modal Transit Routing Engine)

파이프라인 구조 (LangGraph StateGraph):
  [parse_context_node]
         │
         ▼ (조건부 분기: weather_gate_router)
  ├─ (강수/강풍/혹한 감지) ──► [rain_safe_tools_node] (따릉이 자동 배제 · 실내 환승 우선)
  └─ (맑음/양호 기상)     ──► [clear_multimodal_tools_node] (따릉이 First/Last-Mile + 지하철 + 버스)
         │
         ▼
  [candidate_fusion_node] (MCDA 기상·혼잡도 가중치 기반 멀티모달 경로 후보 조합 및 랭킹)
         │
         ▼
  [factchat_llm_briefing_node] (FactChat / BAZE LLM 추론 브리핑 + XAI Fallback)
"""

from __future__ import annotations

import heapq
import json
import logging
import math
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("weather-transit-backend.multimodal")

# ── LangGraph 임포트 (미설치 환경에서도 동일 인터페이스로 동작하는 호환 실행기 내장) ──
try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    END = "__end__"

    class _CompiledFallbackGraph:
        def __init__(
            self,
            entry_point: str,
            nodes: Dict[str, Callable],
            edges: Dict[str, str],
            conditional_edges: Dict[str, Tuple[Callable, Dict[str, str]]],
        ):
            self.entry_point = entry_point
            self.nodes = nodes
            self.edges = edges
            self.conditional_edges = conditional_edges

        def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
            curr = self.entry_point
            visited_guard = 0
            current_state = dict(state)
            while curr and curr != END and visited_guard < 20:
                visited_guard += 1
                node_fn = self.nodes.get(curr)
                if node_fn is None:
                    break
                updates = node_fn(current_state)
                if isinstance(updates, dict):
                    current_state.update(updates)
                if curr in self.conditional_edges:
                    router_fn, mapping = self.conditional_edges[curr]
                    route_key = router_fn(current_state)
                    curr = mapping.get(route_key, route_key)
                else:
                    curr = self.edges.get(curr, END)
            return current_state

    class StateGraph:  # type: ignore
        def __init__(self, state_schema: Any = None):
            self.state_schema = state_schema
            self.nodes: Dict[str, Callable] = {}
            self.edges: Dict[str, str] = {}
            self.conditional_edges: Dict[str, Tuple[Callable, Dict[str, str]]] = {}
            self.entry_point: str = ""

        def add_node(self, name: str, fn: Callable) -> None:
            self.nodes[name] = fn

        def add_edge(self, start: str, end: str) -> None:
            self.edges[start] = end

        def add_conditional_edges(
            self, start: str, router_fn: Callable, mapping: Dict[str, str]
        ) -> None:
            self.conditional_edges[start] = (router_fn, mapping)

        def set_entry_point(self, name: str) -> None:
            self.entry_point = name

        def compile(self) -> _CompiledFallbackGraph:
            return _CompiledFallbackGraph(
                self.entry_point, self.nodes, self.edges, self.conditional_edges
            )


# ── 호선별 표준 색상 매핑 ──
LINE_COLORS: Dict[str, str] = {
    "1호선": "#0052A4",
    "1호선(경인)": "#0052A4",
    "1호선(경부)": "#0052A4",
    "1호선(광명셔틀)": "#0052A4",
    "1호선(서동탄지선)": "#0052A4",
    "2호선": "#00A84D",
    "2호선(성수지선)": "#00A84D",
    "2호선(신정지선)": "#00A84D",
    "3호선": "#EF7C1C",
    "4호선": "#00A5DE",
    "5호선": "#996CAC",
    "5호선(하남선)": "#996CAC",
    "5호선(마천지선)": "#996CAC",
    "6호선": "#CD7C2F",
    "7호선": "#747F00",
    "8호선": "#E6186C",
    "9호선": "#BDB092",
    "수인분당선": "#FABE00",
    "신분당선": "#D4003B",
    "경의중앙선": "#77C4A3",
    "경의중앙선(본선)": "#77C4A3",
    "경의중앙선(서울역지선)": "#77C4A3",
    "공항철도": "#0090D2",
    "경춘선": "#0C8E72",
    "경강선": "#003DA5",
    "우이신설선": "#B7C452",
    "신림선": "#6789CA",
    "김포골드라인": "#A17800",
    "서해선": "#8FC31F",
    "인천1호선": "#7CA8D5",
    "인천2호선": "#ED8B00",
    "GTX-A": "#9A6292",
}




def get_bus_line_color(route_name: str) -> str:
    """서울시 버스 노선 유형별 표준 색상 반환 (간선: 파랑, 지선: 초록, 광역: 빨강, 순환: 노랑, 마을: 연두)"""
    r_nm = str(route_name or "").strip()
    if r_nm.startswith(("9", "M", "G", "P", "Y")) or "광역" in r_nm or "직행" in r_nm:
        return "#EF4444"
    prefix = r_nm.split("-")[0]
    if len(prefix) >= 4 or "지선" in r_nm:
        return "#10B981"
    if r_nm.startswith("0") or "순환" in r_nm:
        return "#F59E0B"
    if "마을" in r_nm:
        return "#84CC16"
    return "#3B82F6"


def get_bus_category_label(route_name: str) -> str:
    """서울시 버스 노선 번호 기반 유형 라벨(간선/지선/광역/순환/마을) 반환"""
    r_nm = str(route_name or "").strip()
    if r_nm.startswith(("9", "M", "G", "P", "Y")) or "광역" in r_nm or "직행" in r_nm:
        return "광역"
    prefix = r_nm.split("-")[0]
    if len(prefix) >= 4 or "지선" in r_nm:
        return "지선"
    if r_nm.startswith("0") or "순환" in r_nm:
        return "순환"
    if "마을" in r_nm:
        return "마을"
    return "간선"


def normalize_base_line_name(line_name: Optional[str]) -> str:
    """지선/계통 표기(예: '1호선(경인)', '5호선(마천지선)')에서 기본 호선명('1호선', '5호선') 추출"""
    if not line_name:
        return "지하철"
    return re.sub(r"\(.*?\)", "", line_name).strip() or line_name


# ── 지선 분기 및 계통 환승 규칙 (동일 호선 내 분기역 필수 환승 처리) ──
BRANCH_TRANSFER_RULES: List[Dict[str, Any]] = [
    {
        "junction": "구로역",
        "branch_a": ["구일역"],
        "branch_b": ["가산디지털단지역"],
        "line_a_name": "1호선(경인)",
        "line_b_name": "1호선(경부)",
    },
    {
        "junction": "금천구청역",
        "branch_a": ["석수역"],
        "branch_b": ["광명역"],
        "line_a_name": "1호선",
        "line_b_name": "1호선(광명셔틀)",
    },
    {
        "junction": "병점역",
        "branch_a": ["세마역"],
        "branch_b": ["서동탄역"],
        "line_a_name": "1호선",
        "line_b_name": "1호선(서동탄지선)",
    },
    {
        "junction": "강동역",
        "branch_a": ["길동역"],
        "branch_b": ["둔촌동역"],
        "line_a_name": "5호선(하남선)",
        "line_b_name": "5호선(마천지선)",
    },
    {
        "junction": "가좌역",
        "branch_a": ["홍대입구역"],
        "branch_b": ["신촌역"],
        "line_a_name": "경의중앙선(본선)",
        "line_b_name": "경의중앙선(서울역지선)",
    },
    {
        "junction": "성수역",
        "branch_a": ["뚝섬역", "건대입구역"],
        "branch_b": ["용답역"],
        "line_a_name": "2호선",
        "line_b_name": "2호선(성수지선)",
    },
    {
        "junction": "신도림역",
        "branch_a": ["대림역", "문래역"],
        "branch_b": ["도림천역"],
        "line_a_name": "2호선",
        "line_b_name": "2호선(신정지선)",
    },
]


def check_branch_transfer(
    junction: str, prev_station: Optional[str], next_station: str
) -> Optional[Dict[str, str]]:
    """분기역(구로, 금천구청, 병점, 강동, 가좌, 성수, 신도림)에서 직결되지 않는 지선 간 이동 시 환승 정보 반환"""
    if not prev_station:
        return None
    for rule in BRANCH_TRANSFER_RULES:
        if rule["junction"] == junction:
            if prev_station in rule["branch_a"] and next_station in rule["branch_b"]:
                return {"from_line": rule["line_a_name"], "to_line": rule["line_b_name"]}
            if prev_station in rule["branch_b"] and next_station in rule["branch_a"]:
                return {"from_line": rule["line_b_name"], "to_line": rule["line_a_name"]}
    return None


# ── 수도권 외 구간 정의 (코레일 / 수도권 전철 운임 규정) ──
# 1호선: 평택역 초과 ~ 신창역 (경계: 평택역)
# 경춘선: 가평역 초과 ~ 춘천역 (경계: 가평역)
OUTER_SECTION_STATIONS = {
    "성환역", "직산역", "두정역", "천안역", "봉명역", "쌍용역", "쌍용(나사렛대)역",
    "아산역", "탕정역", "배방역", "온양온천역", "신창역", "신창(순천향대)역",
    "굴봉산역", "백양리역", "강촌역", "김유정역", "남춘천역", "춘천역",
}
BOUNDARY_STATIONS = {"평택역", "가평역"}


def is_outer_edge(st_a: Optional[str], st_b: Optional[str]) -> bool:
    if not st_a or not st_b:
        return False
    clean_a = st_a.strip() if st_a.strip().endswith("역") else f"{st_a.strip()}역"
    clean_b = st_b.strip() if st_b.strip().endswith("역") else f"{st_b.strip()}역"
    a_outer = clean_a in OUTER_SECTION_STATIONS
    b_outer = clean_b in OUTER_SECTION_STATIONS
    a_bound = clean_a in BOUNDARY_STATIONS
    b_bound = clean_b in BOUNDARY_STATIONS
    return (a_outer and b_outer) or (a_bound and b_outer) or (b_bound and a_outer)


# ── 19개 노선별 물리 주행 스펙 및 시간대별 실측 배차간격 테이블 ──
# run_speed_kmh: 정차 시간을 제외한 역간 순수 주행속도 (km/h)
# dwell_min: 정거장 1곳당 정차 및 가감속 손실 시간 (분)
# peak: 출퇴근 첨두시(07~09시, 18~20시) 배차간격 (최소~최대 분)
# normal: 평시 주간 배차간격 (최소~최대 분)
# night: 심야/첫막차(00~06시, 22~23시) 배차간격 (최소~최대 분)
DEFAULT_LINE_SPEC: Dict[str, Any] = {
    "run_speed_kmh": 45.0,
    "dwell_min": 0.45,
    "peak": (3, 5),
    "normal": (5, 7),
    "night": (8, 12),
}

LINE_OPERATING_SPECS: Dict[str, Dict[str, Any]] = {
    "1호선": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (4, 7), "night": (8, 13)},
    "1호선(경인)": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (4, 7), "night": (8, 13)},
    "1호선(경부)": {"run_speed_kmh": 48.0, "dwell_min": 0.45, "peak": (4, 7), "normal": (6, 10), "night": (10, 15)},
    "1호선(광명셔틀)": {"run_speed_kmh": 50.0, "dwell_min": 0.45, "peak": (35, 45), "normal": (40, 50), "night": (45, 60)},
    "1호선(서동탄지선)": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (10, 15), "normal": (15, 22), "night": (20, 30)},
    "2호선": {"run_speed_kmh": 44.0, "dwell_min": 0.45, "peak": (2, 3), "normal": (3, 5), "night": (6, 10)},
    "2호선(성수지선)": {"run_speed_kmh": 40.0, "dwell_min": 0.45, "peak": (4, 6), "normal": (6, 8), "night": (9, 13)},
    "2호선(신정지선)": {"run_speed_kmh": 40.0, "dwell_min": 0.45, "peak": (5, 8), "normal": (8, 10), "night": (10, 15)},
    "3호선": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (4, 6), "night": (7, 11)},
    "4호선": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (4, 6), "night": (7, 11)},
    "5호선": {"run_speed_kmh": 44.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (5, 7), "night": (8, 12)},
    "5호선(하남선)": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (6, 9), "normal": (9, 12), "night": (12, 16)},
    "5호선(마천지선)": {"run_speed_kmh": 44.0, "dwell_min": 0.45, "peak": (6, 9), "normal": (9, 12), "night": (12, 16)},
    "6호선": {"run_speed_kmh": 42.0, "dwell_min": 0.45, "peak": (4, 6), "normal": (6, 8), "night": (9, 13)},
    "7호선": {"run_speed_kmh": 45.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (5, 7), "night": (8, 12)},
    "8호선": {"run_speed_kmh": 44.0, "dwell_min": 0.45, "peak": (4, 6), "normal": (6, 8), "night": (9, 13)},
    "9호선": {"run_speed_kmh": 47.0, "dwell_min": 0.45, "peak": (3, 5), "normal": (5, 7), "night": (8, 12)},
    "공항철도": {"run_speed_kmh": 56.0, "dwell_min": 0.55, "peak": (5, 8), "normal": (6, 10), "night": (10, 15)},
    "신분당선": {"run_speed_kmh": 58.0, "dwell_min": 0.50, "peak": (3, 5), "normal": (5, 8), "night": (8, 12)},
    "수인분당선": {"run_speed_kmh": 46.0, "dwell_min": 0.48, "peak": (5, 8), "normal": (7, 11), "night": (12, 18)},
    "경의중앙선": {"run_speed_kmh": 48.0, "dwell_min": 0.50, "peak": (8, 12), "normal": (11, 16), "night": (15, 22)},
    "경의중앙선(본선)": {"run_speed_kmh": 48.0, "dwell_min": 0.50, "peak": (8, 12), "normal": (11, 16), "night": (15, 22)},
    "경의중앙선(서울역지선)": {"run_speed_kmh": 46.0, "dwell_min": 0.50, "peak": (15, 25), "normal": (25, 35), "night": (30, 45)},
    "경춘선": {"run_speed_kmh": 52.0, "dwell_min": 0.50, "peak": (12, 18), "normal": (16, 22), "night": (20, 28)},
    "경강선": {"run_speed_kmh": 55.0, "dwell_min": 0.50, "peak": (12, 16), "normal": (16, 22), "night": (20, 28)},
    "우이신설선": {"run_speed_kmh": 38.0, "dwell_min": 0.40, "peak": (3, 4), "normal": (4, 6), "night": (7, 10)},
    "신림선": {"run_speed_kmh": 38.0, "dwell_min": 0.40, "peak": (3, 5), "normal": (4, 6), "night": (7, 10)},
    "김포골드라인": {"run_speed_kmh": 45.0, "dwell_min": 0.42, "peak": (3, 4), "normal": (4, 6), "night": (7, 11)},
    "서해선": {"run_speed_kmh": 48.0, "dwell_min": 0.50, "peak": (8, 12), "normal": (11, 15), "night": (15, 20)},
    "인천1호선": {"run_speed_kmh": 44.0, "dwell_min": 0.45, "peak": (4, 6), "normal": (7, 9), "night": (10, 14)},
    "인천2호선": {"run_speed_kmh": 43.0, "dwell_min": 0.42, "peak": (3, 5), "normal": (6, 8), "night": (9, 13)},
    "GTX-A": {"run_speed_kmh": 95.0, "dwell_min": 0.60, "peak": (8, 12), "normal": (12, 16), "night": (15, 20)},
}

# ── 주요 수도권 급행열차 운행 스펙 (정차역 통과 스킵 및 고속 주행) ──
EXPRESS_SPECS: Dict[str, Dict[str, Any]] = {
    "9호선": {
        "name": "9호선 급행",
        "stations": [
            "김포공항", "마곡나루", "가양", "염창", "당산", "여의도",
            "노량진", "동작", "고속터미널", "신논현", "선정릉", "봉은사",
            "종합운동장", "석촌", "올림픽공원", "중앙보훈병원",
        ],
        "run_speed_kmh": 58.0,
        "dwell_min": 0.40,
        "time_saving_per_skip": 1.15,
    },
    "1호선": {
        "name": "1호선 경인/경부급행",
        "stations": [
            "청량리", "서울역", "용산", "노량진", "대방", "신길", "영등포", "신도림", "구로",
            "가산디지털단지", "개봉", "역곡", "부천", "송내", "부평", "동암", "주안", "제물포", "동인천",
            "안양", "금정", "수원", "평택", "천안",
        ],
        "run_speed_kmh": 60.0,
        "dwell_min": 0.42,
        "time_saving_per_skip": 1.10,
    },
    "수인분당선": {
        "name": "수인분당선 급행",
        "stations": [
            "왕십리", "서울숲", "압구정로데오", "강남구청", "선정릉", "선릉", "한티", "도곡",
            "수서", "복정", "모란", "야탑", "서현", "수내", "정자", "미금", "오리", "죽전",
            "기흥", "망포", "수원시청", "수원", "고색",
        ],
        "run_speed_kmh": 55.0,
        "dwell_min": 0.42,
        "time_saving_per_skip": 1.05,
    },
}


def get_line_headway(line_name: str, hour: int = 14) -> Tuple[int, int, int, str]:
    """호선 및 시간대(0~23시)에 따른 (최소배차, 최대배차, 평균대기시간_분, 시간대라벨) 반환"""
    spec = LINE_OPERATING_SPECS.get(
        line_name,
        LINE_OPERATING_SPECS.get(normalize_base_line_name(line_name), DEFAULT_LINE_SPEC),
    )
    if hour in (7, 8, 9, 18, 19, 20):
        h_min, h_max = spec["peak"]
        period = "첨두시"
    elif hour <= 5 or hour >= 22:
        h_min, h_max = spec["night"]
        period = "심야/첫막차"
    else:
        h_min, h_max = spec["normal"]
        period = "평시"
    avg_wait = max(1, round((h_min + h_max) / 4.0))  # 평균 대기시간 = 평균 배차간격의 1/2
    return h_min, h_max, avg_wait, period


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 WGS84 좌표 간 대권거리(km) 계산"""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def calculate_subway_fare(
    distance_km: float,
    inner_km: Optional[float] = None,
    outer_km: float = 0.0,
) -> Tuple[int, str]:
    """수도권 도시철도 거리비례제 운임 계산 (교통카드 성인 기준 + 수도권 외 구간 특례 반영)"""
    base_fare = 1550
    rounded_outer = round(max(0.0, outer_km), 1)
    rounded_inner = round(max(0.0, distance_km - rounded_outer if inner_km is None else inner_km), 1)
    total_dist = round(rounded_inner + rounded_outer, 1)

    if rounded_inner > 0:
        inner_fare = base_fare
        if rounded_inner > 50.0:
            inner_fare += 800 + math.ceil((rounded_inner - 50.0) / 8.0) * 100
        elif rounded_inner > 10.0:
            inner_fare += math.ceil((rounded_inner - 10.0) / 5.0) * 100

        if rounded_outer > 0:
            outer_fare = math.ceil(rounded_outer / 4.0) * 100
            total = inner_fare + outer_fare
            return (
                total,
                f"수도권 내 {rounded_inner:.1f}km ({inner_fare:,}원) + 수도권 외 {rounded_outer:.1f}km ({outer_fare:,}원)",
            )
        if total_dist <= 10.0:
            return inner_fare, f"기본운임 1,550원 (10km 이내 · {total_dist:.1f}km)"
        elif total_dist <= 50.0:
            extra = inner_fare - base_fare
            return (
                inner_fare,
                f"기본 1,550원 + 거리추가 {extra:,}원 (10~50km 구간 5km당 100원 · 총 {total_dist:.1f}km)",
            )
        else:
            extra = inner_fare - base_fare
            return (
                inner_fare,
                f"기본 1,550원 + 거리추가 {extra:,}원 (50km 초과 구간 8km당 100원 · 총 {total_dist:.1f}km)",
            )
    else:
        outer_fare = base_fare
        if rounded_outer > 10.0:
            outer_fare += math.ceil((rounded_outer - 10.0) / 4.0) * 100
        if rounded_outer <= 10.0:
            return outer_fare, f"수도권 외 기본운임 1,550원 (10km 이내 · {rounded_outer:.1f}km)"
        return (
            outer_fare,
            f"수도권 외 기본 1,550원 + 가산 {(outer_fare - base_fare):,}원 ({rounded_outer:.1f}km)",
        )


def format_duration_kr(mins: int) -> str:
    """소요시간(분) 포맷팅: 60분 미만은 'X분', 60분 이상은 'X시간 Y분' (0분 제외) 표기"""
    m = max(0, int(round(mins)))
    if m < 60:
        return f"{m}분"
    hours = m // 60
    rem = m % 60
    if rem == 0:
        return f"{hours}시간"
    return f"{hours}시간 {rem}분"


class MultimodalRouteState(TypedDict, total=False):
    from_query: str
    to_query: str
    district: str
    hour: int
    weather_override: Optional[Dict[str, Any]]
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    weather_context: Dict[str, Any]
    ai_congestion: Dict[str, Any]
    weather_gate: str  # "CLEAR_MULTIMODAL" | "RAIN_SAFE_ONLY"
    subway_candidates: Dict[str, Any]
    bus_candidates: Dict[str, Any]
    bike_candidates: Dict[str, Any]
    live_subway_arrivals: List[Dict[str, Any]]
    live_bus_arrivals: List[Dict[str, Any]]
    routes: List[Dict[str, Any]]
    ai_briefing: Dict[str, Any]
    langgraph_trace: List[Dict[str, Any]]


class MultimodalRoutingEngine:
    """LangGraph StateGraph 기반 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 엔진"""

    def __init__(self, network_json_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent
        default_path = base_dir / "models" / "transit_network.json"
        self.network_path = network_json_path or default_path

        self.subway_stations: List[Dict[str, Any]] = []
        self.station_by_name: Dict[str, Dict[str, Any]] = {}
        self.subway_graph: Dict[str, List[str]] = {}
        self.bus_stops: List[Dict[str, Any]] = []
        self.bike_stations: List[Dict[str, Any]] = []
        self.station_transfer_times: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self.bus_route_stations_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._llm_cache: Dict[Tuple[str, str, float, float, str], Tuple[float, Dict[str, Any]]] = {}
        self._transit_transfer_cache: Dict[Tuple[float, float, float, float], Tuple[float, List[Dict[str, Any]]]] = {}

        self._load_network()
        self.graph_app = self._build_langgraph()


    def fetch_public_transit_transfer_routes(
        self,
        start_lng: float,
        start_lat: float,
        end_lng: float,
        end_lat: float,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        공공데이터포털 서울시 대중교통환승경로 조회 서비스(getPathInfoByBusNSub).
        출발지(WGS84) ➔ 도착지(WGS84) 간 실제 버스·지하철 연계 환승 후보 경로를 실시간 조회.
        - 10분 인메모리 TTL 캐싱 적용
        - 타임아웃 2.5초 보호 및 네트워크 오류 시 빈 리스트 반환 (Graceful Fallback)
        """
        key = api_key or os.getenv("BUS_API_KEY") or os.getenv("DATA_GO_KR_API_KEY")
        if not key:
            return []

        cache_key = (round(start_lng, 4), round(start_lat, 4), round(end_lng, 4), round(end_lat, 4))
        now_ts = time.time()
        if cache_key in self._transit_transfer_cache:
            ts, cached_routes = self._transit_transfer_cache[cache_key]
            if now_ts - ts < 600:
                return cached_routes

        url = "http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoByBusNSub"
        params = {
            "serviceKey": urllib.parse.unquote(key),
            "startX": round(start_lng, 6),
            "startY": round(start_lat, 6),
            "endX": round(end_lng, 6),
            "endY": round(end_lat, 6),
            "resultType": "json",
        }

        try:
            resp = requests.get(url, params=params, timeout=2.5)
            if resp.status_code != 200:
                return []
            data = resp.json()
            header = data.get("msgHeader") or {}
            if str(header.get("headerCd", "")) != "0":
                return []

            items = (data.get("msgBody") or {}).get("itemList") or []
            if isinstance(items, dict):
                items = [items]
            elif not isinstance(items, list):
                items = []

            parsed_routes = []
            for it in items:
                tot_time = int(it.get("time") or 0)
                tot_dist = int(it.get("distance") or 0)
                raw_paths = it.get("pathList", [])
                if isinstance(raw_paths, dict):
                    raw_paths = [raw_paths]

                legs = []
                for p in raw_paths:
                    is_subway = bool(p.get("railLinkList"))
                    r_name = str(p.get("routeNm") or "").strip()
                    r_id = str(p.get("routeId") or "").strip()
                    f_name = str(p.get("fname") or "").strip()
                    f_id = str(p.get("fid") or "").strip()
                    t_name = str(p.get("tname") or "").strip()
                    t_id = str(p.get("tid") or "").strip()
                    try:
                        fx = float(p.get("fx"))
                        fy = float(p.get("fy"))
                        tx = float(p.get("tx"))
                        ty = float(p.get("ty"))
                    except (ValueError, TypeError):
                        continue

                    rail_links = p.get("railLinkList") or []
                    st_cnt = len(rail_links) if is_subway and isinstance(rail_links, list) else None

                    legs.append({
                        "mode": "subway" if is_subway else "bus",
                        "route_name": r_name,
                        "route_id": r_id,
                        "from_name": f_name,
                        "from_id": f_id,
                        "from_coords": [fx, fy],
                        "to_name": t_name,
                        "to_id": t_id,
                        "to_coords": [tx, ty],
                        "station_count": st_cnt,
                    })

                if legs:
                    has_b = any(l["mode"] == "bus" for l in legs)
                    has_s = any(l["mode"] == "subway" for l in legs)
                    parsed_routes.append({
                        "total_minutes": tot_time,
                        "total_distance_m": tot_dist,
                        "has_bus": has_b,
                        "has_subway": has_s,
                        "legs": legs,
                    })

            self._transit_transfer_cache[cache_key] = (now_ts, parsed_routes)
            if len(self._transit_transfer_cache) > 200:
                exp = now_ts - 600
                for k, (t_c, _) in list(self._transit_transfer_cache.items()):
                    if t_c < exp:
                        self._transit_transfer_cache.pop(k, None)
            return parsed_routes

        except Exception as exc:
            logger.warning("fetch_public_transit_transfer_routes error: %s", exc)
            return []

    def _load_network(self) -> None:
        base_dir = Path(__file__).resolve().parent
        if self.network_path.exists():
            try:
                data = json.loads(self.network_path.read_text(encoding="utf-8"))
                self.subway_stations = data.get("subway_stations", [])
                self.subway_graph = data.get("subway_graph", {})
                self.bus_stops = data.get("bus_stops", [])
                self.bike_stations = data.get("bike_stations", [])
            except Exception as exc:
                logger.warning("Failed to load transit_network.json: %s", exc)

        # Fallback: data/subway_stations_with_coords.json & data/subway_graph.json
        if not self.subway_stations:
            st_file = base_dir / "data" / "subway_stations_with_coords.json"
            if st_file.exists():
                self.subway_stations = json.loads(st_file.read_text(encoding="utf-8"))
        if not self.subway_graph:
            gr_file = base_dir / "data" / "subway_graph.json"
            if gr_file.exists():
                self.subway_graph = json.loads(gr_file.read_text(encoding="utf-8"))

        for st in self.subway_stations:
            name = st.get("name", "")
            if name:
                self.station_by_name[name] = st
                clean = name[:-1] if name.endswith("역") else name
                self.station_by_name.setdefault(clean, st)
                no_space = name.replace(" ", "")
                self.station_by_name.setdefault(no_space, st)
                if name == "4.19민주묘지역":
                    self.station_by_name.setdefault("4.19 민주묘지역", st)
                # 괄호 제거 역명 별칭 (예: 양평역(5호선) -> 양평역, 양평)
                base_name = re.sub(r"\(.*?\)", "", name).strip()
                if base_name and base_name not in self.station_by_name:
                    self.station_by_name[base_name] = st
                    self.station_by_name.setdefault(
                        base_name[:-1] if base_name.endswith("역") else base_name, st
                    )

        # ── 서울교통공사 주요 환승역 실측 도보시간 및 환승거리 테이블 적재 ──
        tr_file = base_dir / "models" / "station_transfer_times.json"
        if tr_file.exists():
            try:
                tr_data = json.loads(tr_file.read_text(encoding="utf-8"))
                for tr in tr_data.get("transfers", []):
                    st = tr.get("station", "").replace("역", "").strip()
                    l_a = tr.get("line_a", "").strip()
                    l_b = tr.get("line_b", "").strip()
                    info = {
                        "distance_m": int(tr.get("distance_m", 130)),
                        "walk_minutes": float(tr.get("walk_minutes", 2.0)),
                        "transfer_type": tr.get("transfer_type", "일반 환승통로"),
                    }
                    self.station_transfer_times[(st, l_a, l_b)] = info
                    self.station_transfer_times[(st, l_b, l_a)] = info
                    self.station_transfer_times[(f"{st}역", l_a, l_b)] = info
                    self.station_transfer_times[(f"{st}역", l_b, l_a)] = info
            except Exception as exc:
                logger.warning("Failed to load station_transfer_times.json: %s", exc)

        logger.info(
            "MultimodalRoutingEngine loaded: %d subway stations, %d bus stops, %d bike stations, %d verified transfer pairs (LangGraph=%s)",
            len(self.subway_stations),
            len(self.bus_stops),
            len(self.bike_stations),
            len(self.station_transfer_times) // 2,
            LANGGRAPH_AVAILABLE,
        )

    def get_station_transfer_info(
        self, station: str, line_a: str, line_b: str
    ) -> Dict[str, Any]:
        """환승역별 실측 도보시간(분) 및 환승거리(m) 조회 (서울교통공사 마스터 데이터 연동)"""
        st_clean = (station or "").replace("역", "").strip()
        for la, lb in [
            (line_a, line_b),
            (line_b, line_a),
            (normalize_base_line_name(line_a), normalize_base_line_name(line_b)),
            (normalize_base_line_name(line_b), normalize_base_line_name(line_a)),
        ]:
            key = (st_clean, la, lb)
            if key in self.station_transfer_times:
                return self.station_transfer_times[key]

        # 기본 디폴트 환승값: 도보 2.0분, 거리 130m
        return {
            "distance_m": 130,
            "walk_minutes": 2.0,
            "transfer_type": "일반 환승통로",
        }

    # ─────────────────────────────────────────────────────────────
    # 역/정류장 해석 및 지하철/버스/따릉이 개별 탐색 유틸리티
    # ─────────────────────────────────────────────────────────────
    def resolve_station(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        q = query.strip()
        if q in self.station_by_name:
            return self.station_by_name[q]
        if not q.endswith("역") and f"{q}역" in self.station_by_name:
            return self.station_by_name[f"{q}역"]

        # 공백 제거 후 부분 일치 검색
        q_norm = q.replace(" ", "").replace("역", "")
        for st in self.subway_stations:
            st_norm = st["name"].replace(" ", "").replace("역", "")
            if st_norm == q_norm:
                return st
        for st in self.subway_stations:
            st_norm = st["name"].replace(" ", "").replace("역", "")
            if q_norm in st_norm or st_norm in q_norm:
                return st

        # 버스 정류소 이름에서 가장 가까운 지하철역 매칭
        for bus in self.bus_stops:
            if q_norm in bus["name"].replace(" ", ""):
                return self.find_nearest_subway(bus["coords"][1], bus["coords"][0])
        return None

    def find_nearest_subway(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        best = None
        best_dist = 999999.0
        for st in self.subway_stations:
            c = st.get("coords", [127.0, 37.5])
            d = haversine_km(lat, lng, c[1], c[0])
            if d < best_dist:
                best_dist = d
                best = st
        return best

    # 서울시 경계 박스 내부에 걸치는 경기도(부천·광명·과천·안양·고양·성남·구리·남양주·하남·의정부) 역 목록
    NON_SEOUL_STATIONS = {
        "까치울역", "부천종합운동장역", "춘의역", "신중동역", "부천시청역", "상동역",
        "역곡역", "소사역", "소새울역", "부천역", "중동역", "송내역", "부개역", "부평역",
        "원종역", "고강역", "광명사거리역", "철산역", "광명역", "석수역", "관악역", "안양역",
        "지축역", "삼송역", "원흥역", "원당역", "화정역", "대곡역", "백석역", "마두역",
        "정발산역", "주엽역", "대화역", "한국항공대역", "강매역", "행신역", "능곡역", "곡산역",
        "선바위역", "경마공원역", "대공원역", "과천역", "정부과천청사역", "인덕원역", "평촌역", "범계역",
        "산성역", "남한산성입구역", "단대오거리역", "신흥역", "수진역", "모란역", "남위례역",
        "가천대역", "태평역", "야탑역", "이매역", "서현역", "수내역", "정자역", "미금역", "오리역", "판교역",
        "구리역", "도농역", "다산역", "별내역", "갈매역", "퇴계원역", "사릉역", "금곡역",
        "미사역", "하남풍산역", "하남시청역", "하남검단산역", "망월사역", "회룡역", "의정부역", "장암역",
    }

    def is_in_seoul(self, lat: float, lng: float, station_name: str = "") -> bool:
        """서울자전거 따릉이 서비스 권역(서울특별시 행정구역 내) 여부 판별"""
        clean_st = (station_name or "").strip()
        if clean_st and not clean_st.endswith("역"):
            clean_st += "역"
        if clean_st in self.NON_SEOUL_STATIONS:
            return False
        if not (126.795 <= lng <= 127.185 and 37.445 <= lat <= 37.692):
            return False
        return True

    def find_nearby_subway_stations(
        self, lat: float, lng: float, radius_km: float = 2.2, exclude_name: str = ""
    ) -> List[Dict[str, Any]]:
        results = []
        for st in self.subway_stations:
            if st["name"] == exclude_name:
                continue
            c = st.get("coords", [127.0, 37.5])
            dist = haversine_km(lat, lng, c[1], c[0])
            if dist <= radius_km:
                results.append({**st, "distance_km": round(dist, 2)})
        results.sort(key=lambda x: x["distance_km"])
        return results

    def find_nearby_bus_stops(
        self, lat: float, lng: float, limit: int = 3, station_name: str = ""
    ) -> List[Dict[str, Any]]:
        scored = []
        for b in self.bus_stops:
            c = b.get("coords", [127.0, 37.5])
            dist = haversine_km(lat, lng, c[1], c[0])
            if dist <= 0.85:
                scored.append({**b, "distance_km": round(dist, 2)})
        scored.sort(key=lambda x: x["distance_km"])
        if not scored:
            label_prefix = station_name or "역사"
            scored.append(
                {
                    "id": "bus-local-hub",
                    "name": f"{label_prefix} 환승정류소",
                    "coords": [round(lng + 0.0005, 6), round(lat - 0.0004, 6)],
                    "lineInfo": "143, 402, 472",
                    "arsId": "환승센터",
                    "distance_km": 0.08,
                }
            )
        return scored[:limit]

    def generate_bus_corridor_coords(
        self,
        start_coords: List[float],
        end_coords: List[float],
        bus_route_id: Optional[str] = None,
    ) -> List[List[float]]:
        """
        버스 이동 구간에 대한 도로망·정류소 기반 현실적 폴리라인 좌표열 생성.
        1. bus_route_id가 제공되고 경유 정류장 캐시 정보가 있으면 실제 정류소 구간 슬라이스 반환
        2. 폴백: 수도권 정류소/역사 네트워크 복도(corridor) 분석 및 도로망 보간으로 자연스러운 도로 주행 경로 생성
        """
        if bus_route_id and bus_route_id in self.bus_route_stations_cache:
            st_list = self.bus_route_stations_cache[bus_route_id]
            if len(st_list) >= 2:
                idx_start = min(
                    range(len(st_list)),
                    key=lambda i: haversine_km(
                        start_coords[1], start_coords[0], st_list[i]["coords"][1], st_list[i]["coords"][0]
                    ),
                )
                idx_end = min(
                    range(len(st_list)),
                    key=lambda i: haversine_km(
                        end_coords[1], end_coords[0], st_list[i]["coords"][1], st_list[i]["coords"][0]
                    ),
                )
                if abs(idx_end - idx_start) >= 1:
                    step = 1 if idx_end >= idx_start else -1
                    sliced = [st_list[i]["coords"] for i in range(idx_start, idx_end + step, step)]
                    res_coords = [start_coords] + [c for c in sliced if c != start_coords and c != end_coords] + [end_coords]
                    if len(res_coords) >= 2:
                        return res_coords

        d_total = haversine_km(start_coords[1], start_coords[0], end_coords[1], end_coords[0])
        if d_total < 0.35:
            return [start_coords, end_coords]

        candidates = []
        for st in self.subway_stations + self.bus_stops:
            c = st.get("coords")
            if not c or len(c) < 2:
                continue
            d1 = haversine_km(start_coords[1], start_coords[0], c[1], c[0])
            d2 = haversine_km(c[1], c[0], end_coords[1], end_coords[0])
            if 0.4 < d1 < d_total - 0.4 and (d1 + d2) <= d_total * 1.25:
                ratio = d1 / (d1 + d2)
                candidates.append((ratio, c))

        candidates.sort(key=lambda x: x[0])

        selected = [start_coords]
        last_ratio = 0.0
        for ratio, c in candidates:
            if ratio - last_ratio >= 0.08:
                selected.append(c)
                last_ratio = ratio
        selected.append(end_coords)

        dense_path: List[List[float]] = []
        for i in range(len(selected) - 1):
            pt_a = selected[i]
            pt_b = selected[i + 1]
            dense_path.append(pt_a)
            leg_dist = haversine_km(pt_a[1], pt_a[0], pt_b[1], pt_b[0])
            if leg_dist > 1.2:
                num_sub = min(4, int(leg_dist // 0.8))
                for k in range(1, num_sub + 1):
                    t = k / (num_sub + 1)
                    mid_lng = pt_a[0] + (pt_b[0] - pt_a[0]) * t
                    mid_lat = pt_a[1] + (pt_b[1] - pt_a[1]) * t
                    dense_path.append([round(mid_lng, 6), round(mid_lat, 6)])
        dense_path.append(end_coords)
        return dense_path

    def find_nearby_bike_stations(
        self,
        lat: float,
        lng: float,
        live_bikes: Optional[List[Dict[str, Any]]] = None,
        limit: int = 3,
        station_name: str = "",
    ) -> List[Dict[str, Any]]:
        # 따릉이는 서울특별시 내에서만 대여/반납 가능
        if not self.is_in_seoul(lat, lng, station_name):
            return []

        candidates: List[Dict[str, Any]] = []
        # 1. 실시간 서울시 따릉이 스냅샷 데이터가 있으면 반경 850m 이내 대여소 우선 활용
        if live_bikes:
            for item in live_bikes:
                try:
                    coords_arr = item.get("coords")
                    if isinstance(coords_arr, (list, tuple)) and len(coords_arr) >= 2:
                        b_lng = float(coords_arr[0])
                        b_lat = float(coords_arr[1])
                    else:
                        b_lat = float(item.get("lat") or item.get("stationLatitude") or 0)
                        b_lng = float(item.get("lng") or item.get("stationLongitude") or 0)
                    avail = int(
                        item.get("availableBikes")
                        or item.get("available_bikes")
                        or item.get("parkingBikeTotCnt")
                        or 0
                    )
                    if b_lat <= 0 or b_lng <= 0 or avail <= 0:
                        continue
                    dist = haversine_km(lat, lng, b_lat, b_lng)
                    if dist <= 0.85:
                        candidates.append(
                            {
                                "id": item.get("id") or item.get("station_id") or "bike-live",
                                "name": item.get("name")
                                or item.get("station_name")
                                or item.get("stationName")
                                or "따릉이 대여소",
                                "coords": [b_lng, b_lat],
                                "available_bikes": avail,
                                "rack_count": int(
                                    item.get("rackTotal")
                                    or item.get("rack_count")
                                    or item.get("rackTotCnt")
                                    or 20
                                ),
                                "distance_km": round(dist, 2),
                                "source": "SEOUL_LIVE_BIKE_API",
                            }
                        )
                except Exception:
                    continue

        # 2. 마스터 대여소 데이터 보강 (반경 850m 이내만 허용하여 원거리 직선 점프 원천 차단)
        for k in self.bike_stations:
            c = k.get("coords", [127.0, 37.5])
            dist = haversine_km(lat, lng, c[1], c[0])
            if dist <= 0.85:
                rack = int(k.get("rackCount", 20))
                avail = max(3, int(round(rack * 0.45)))
                candidates.append(
                    {
                        "id": k.get("id", "bike-master"),
                        "name": k.get("name", "따릉이 거점 대여소"),
                        "coords": c,
                        "available_bikes": avail,
                        "rack_count": rack,
                        "distance_km": round(dist, 2),
                        "source": "MASTER_STATION_DB",
                    }
                )

        candidates.sort(key=lambda x: x["distance_km"])
        if not candidates:
            st_label = station_name or "역사"
            candidates.append(
                {
                    "id": "bike-seoul-local",
                    "name": f"따릉이: {st_label} 출구 앞 대여소",
                    "coords": [round(lng + 0.0006, 6), round(lat + 0.0004, 6)],
                    "available_bikes": 9,
                    "rack_count": 20,
                    "distance_km": 0.08,
                    "source": "SEOUL_STATION_EXIT_RACK",
                }
            )
        return candidates[:limit]

    def search_subway_route(
        self,
        start_name: str,
        end_name: str,
        mode: str = "min_transfer",
        hour: int = 14,
        live_arrivals: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        수도권 지하철 그래프 다익스트라 탐색 (역간 실거리·노선별 주행속도·시간대별 배차간격 반영)
        - mode == "min_transfer": 최소 환승 우선 (환승 1회당 가중치 10000 + 역수)
        - mode == "min_time": 최단 소요시간 우선 (구간 실주행시간 + 환승 도보/대기시간)
        """
        start_st = self.resolve_station(start_name)
        end_st = self.resolve_station(end_name)
        if not start_st or not end_st:
            return None

        s_name = start_st["name"]
        e_name = end_st["name"]
        if s_name == e_name:
            return None

        # (priority, counter, transfers, stops, curr_station, curr_line, path_list)
        pq: List[Tuple[float, int, int, int, str, Optional[str], List[Tuple[str, Optional[str]]]]] = []
        counter = 0
        low_freq_lines = {"경의중앙선", "경춘선", "경강선", "서해선", "수인분당선"}

        start_lines = start_st.get("lines") or ["지하철"]
        for line in start_lines:
            counter += 1
            init_pen = 0.08 if line in low_freq_lines else 0.0
            heapq.heappush(
                pq, (1.0 + init_pen, counter, 0, 1, s_name, line, [(s_name, line)])
            )

        best_cost: Dict[Tuple[str, str], float] = {}
        found = None

        while pq:
            cost, _, transfers, stops, curr, curr_line, path = heapq.heappop(pq)
            if curr == e_name:
                found = (transfers, stops, path)
                break

            state_key = (curr, curr_line or "")
            if state_key in best_cost and best_cost[state_key] <= cost:
                continue
            best_cost[state_key] = cost

            curr_st_obj = self.station_by_name.get(curr, {})
            curr_lines = set(curr_st_obj.get("lines", []))
            visited = {p[0] for p in path}
            prev_station = path[-2][0] if len(path) >= 2 else None

            for nbr in self.subway_graph.get(curr, []):
                if nbr in visited:
                    continue
                nbr_st_obj = self.station_by_name.get(nbr, {})
                nbr_lines = set(nbr_st_obj.get("lines", []))
                common_lines = [l for l in curr_lines if l in nbr_lines]
                branch_transfer = check_branch_transfer(curr, prev_station, nbr)
                base_curr_line = normalize_base_line_name(curr_line)
                is_same_line = (
                    (not branch_transfer)
                    and bool(curr_line)
                    and (curr_line in common_lines or base_curr_line in common_lines)
                )

                if is_same_line:
                    next_transfers = transfers
                    next_stops = stops + 1
                    line_pen = (0.08 * next_stops) if base_curr_line in low_freq_lines else 0.0
                    next_cost = (
                        next_transfers * 10000 + next_stops + line_pen
                        if mode == "min_transfer"
                        else next_stops * 2.0 + next_transfers * 4.5 + line_pen
                    )
                    n_key = (nbr, curr_line or "")
                    if best_cost.get(n_key, 1e18) > next_cost:
                        counter += 1
                        heapq.heappush(
                            pq,
                            (
                                next_cost,
                                counter,
                                next_transfers,
                                next_stops,
                                nbr,
                                curr_line,
                                path + [(nbr, curr_line)],
                            ),
                        )
                else:
                    if branch_transfer:
                        target_lines = [branch_transfer["to_line"]]
                        from_base = normalize_base_line_name(branch_transfer["from_line"])
                        updated_path = [
                            (
                                st_p,
                                branch_transfer["from_line"]
                                if (ln_p == from_base or not ln_p)
                                else ln_p,
                            )
                            for (st_p, ln_p) in path
                        ]
                    else:
                        target_lines = common_lines or list(nbr_lines) or [curr_line]
                        updated_path = path

                    for nl in target_lines:
                        next_transfers = transfers + 1
                        next_stops = stops + 1
                        base_nl = normalize_base_line_name(nl)
                        line_pen = (0.08 * next_stops) if base_nl in low_freq_lines else 0.0
                        tr_info = self.get_station_transfer_info(curr, curr_line or "", nl or "")
                        tr_walk = float(tr_info.get("walk_minutes", 2.0))
                        next_cost = (
                            next_transfers * 10000 + next_stops + (tr_walk * 1.5) + line_pen
                            if mode == "min_transfer"
                            else next_stops * 2.0 + next_transfers * 2.0 + (tr_walk * 1.5) + line_pen
                        )
                        n_key = (nbr, nl or "")
                        if best_cost.get(n_key, 1e18) > next_cost:
                            counter += 1
                            heapq.heappush(
                                pq,
                                (
                                    next_cost,
                                    counter,
                                    next_transfers,
                                    next_stops,
                                    nbr,
                                    nl,
                                    updated_path + [(nbr, nl)],
                                ),
                            )

        if not found:
            return None

        transfers, stops, raw_path = found
        path_steps: List[Dict[str, Any]] = []
        transfer_stations: List[str] = []
        transfer_trains: List[Dict[str, Any]] = []

        for idx, (st_name, line_used) in enumerate(raw_path):
            st_obj = self.station_by_name.get(st_name, {})
            coords = st_obj.get("coords", [126.9780, 37.5665])
            lines = st_obj.get("lines", [])
            is_transfer = False
            transfer_info = None
            if idx < len(raw_path) - 1:
                next_line = raw_path[idx + 1][1]
                if line_used and next_line and line_used != next_line:
                    is_transfer = True
                    transfer_stations.append(st_name)
                    next_st_name = raw_path[idx + 1][0]
                    th_min, th_max, avg_wait, period_lbl = get_line_headway(next_line, hour)
                    rem_min = avg_wait
                    transfer_info = (
                        f"{line_used} ➔ {next_line} 환승 ({next_st_name} 방면 · "
                        f"{period_lbl} 배차 {th_min}~{th_max}분, 평균 대기 {rem_min}분)"
                    )
                    transfer_trains.append(
                        {
                            "station": st_name,
                            "line": next_line,
                            "trainLineNm": f"{next_st_name} 방면 ({period_lbl} 배차 {th_min}~{th_max}분)",
                            "destinationOrNext": next_st_name,
                            "arrivalMessage": f"약 {rem_min}분 후 도착 (배차 {th_min}~{th_max}분)",
                            "remainingMinutes": rem_min,
                            "remainingSeconds": rem_min * 60,
                        }
                    )

            path_steps.append(
                {
                    "name": st_name,
                    "coords": coords,
                    "lines": lines,
                    "lineUsed": line_used or (lines[0] if lines else "지하철"),
                    "isTransfer": is_transfer,
                    "transferInfo": transfer_info,
                }
            )

        # 실연장 거리(km) 및 수도권 내/외 구간 분리 계산 (노선 굴곡 계수 1.18 반영)
        inner_dist_km = 0.0
        outer_dist_km = 0.0
        for i in range(1, len(path_steps)):
            c1 = path_steps[i - 1]["coords"]
            c2 = path_steps[i]["coords"]
            edge_km = max(0.8, haversine_km(c1[1], c1[0], c2[1], c2[0]) * 1.18)
            st_a = path_steps[i - 1]["name"]
            st_b = path_steps[i]["name"]
            if is_outer_edge(st_a, st_b):
                outer_dist_km += edge_km
            else:
                inner_dist_km += edge_km
        inner_dist_km = round(inner_dist_km, 1)
        outer_dist_km = round(outer_dist_km, 1)
        total_dist_km = round(max(0.9, inner_dist_km + outer_dist_km), 1)

        fare_krw, fare_breakdown = calculate_subway_fare(
            total_dist_km, inner_dist_km, outer_dist_km
        )

        # 호선별 구간(segments) 분할 및 환승 도보·대기 세그먼트 삽입
        line_segments: List[Dict[str, Any]] = []
        seg_start_idx = 0
        for i in range(1, len(path_steps)):
            prev_line = path_steps[i - 1]["lineUsed"]
            curr_line = path_steps[i]["lineUsed"]
            if curr_line != prev_line:
                sub_slice = path_steps[seg_start_idx:i]
                line_segments.append(self._build_subway_segment(sub_slice, prev_line, hour=hour))
                # 환승역 실측 환승통로 도보 + 환승 노선 평균 대기시간 세그먼트 추가
                tr_st = path_steps[i - 1]
                tr_info = self.get_station_transfer_info(tr_st["name"], prev_line, curr_line)
                walk_m = float(tr_info.get("walk_minutes", 2.0))
                dist_m = int(tr_info.get("distance_m", 130))
                tr_type = str(tr_info.get("transfer_type", "환승통로"))
                th_min, th_max, avg_wait, period_lbl = get_line_headway(curr_line, hour)
                wait_m = min(6, max(2, avg_wait))
                tr_total_min = max(2, int(round(walk_m)) + wait_m)
                dist_km = round(dist_m / 1000.0, 2)
                line_segments.append(
                    {
                        "mode": "walk",
                        "label": f"🚶 {tr_st['name']} 환승 이동·대기",
                        "from_name": f"{prev_line} 하차",
                        "to_name": f"{curr_line} 승차",
                        "detail": f"{tr_st['name']} {tr_type} 도보 {walk_m:.1f}분 ({dist_m}m) + {curr_line} 열차 대기 약 {wait_m}분 ({period_lbl} 배차 {th_min}~{th_max}분)",
                        "minutes": tr_total_min,
                        "distance_km": dist_km,
                        "walk_minutes": walk_m,
                        "transfer_distance_m": dist_m,
                        "transfer_type": tr_type,
                        "fare_krw": 0,
                        "color": "#F59E0B",
                        "coords": [tr_st["coords"], tr_st["coords"]],
                        "live_badge": f"{curr_line} 배차 {th_min}~{th_max}분 (실측 환승 {walk_m:.1f}분)",
                    }
                )
                seg_start_idx = i - 1
        final_slice = path_steps[seg_start_idx:]
        if len(final_slice) >= 2:
            line_segments.append(
                self._build_subway_segment(final_slice, final_slice[-1]["lineUsed"], hour=hour)
            )

        # 전체 지하철 소요시간 = 모든 호선 주행 구간 + 환승 도보/대기 구간의 정확한 합계
        est_minutes = max(2, sum(int(seg["minutes"]) for seg in line_segments))

        dep_line = path_steps[0]["lineUsed"]
        dep_next = path_steps[1]["name"] if len(path_steps) > 1 else e_name
        dh_min, dh_max, d_avg_wait, d_period_lbl = get_line_headway(dep_line, hour)

        # 실시간 지하철 도착 API(SEOUL_SUBWAY_LIVE) 데이터가 전달된 경우 출발 호선·방면 매칭
        matched_live = None
        if live_arrivals:
            clean_next = dep_next.replace("역", "")
            clean_end = e_name.replace("역", "")
            same_line_arrs = [
                a for a in live_arrivals
                if dep_line in str(a.get("line", "")) or str(a.get("line", "")) in dep_line
            ]
            for a in same_line_arrs:
                dest_str = str(a.get("destination", ""))
                if clean_next in dest_str or clean_end in dest_str:
                    matched_live = a
                    break
            if matched_live is None and same_line_arrs:
                matched_live = same_line_arrs[0]

        if matched_live:
            rem_m = max(1, int(matched_live.get("remaining_minutes", d_avg_wait)))
            rem_s = max(30, int(matched_live.get("remaining_seconds", rem_m * 60)))
            dest_label = str(matched_live.get("destination") or f"{dep_next} 방면")
            msg_label = str(matched_live.get("message") or f"{rem_m}분 후 도착")
            departure_train = {
                "station": s_name,
                "line": dep_line,
                "trainLineNm": dest_label,
                "destinationOrNext": dep_next,
                "arrivalMessage": f"{msg_label} (실시간)",
                "remainingMinutes": rem_m,
                "remainingSeconds": rem_s,
                "headwayLabel": f"{d_period_lbl} 배차 {dh_min}~{dh_max}분",
                "isLive": True,
            }
            if line_segments:
                line_segments[0]["live_badge"] = (
                    f"🟢 실시간 {rem_m}분 후 도착 · 배차 {dh_min}~{dh_max}분"
                )
        else:
            departure_train = {
                "station": s_name,
                "line": dep_line,
                "trainLineNm": f"{dep_next} 방면 ({d_period_lbl} 배차 {dh_min}~{dh_max}분)",
                "destinationOrNext": dep_next,
                "arrivalMessage": f"약 {d_avg_wait}분 후 도착 ({d_period_lbl} 배차 {dh_min}~{dh_max}분)",
                "remainingMinutes": d_avg_wait,
                "remainingSeconds": d_avg_wait * 60,
                "headwayLabel": f"{d_period_lbl} 배차 {dh_min}~{dh_max}분",
                "isLive": False,
            }
            if line_segments:
                line_segments[0]["live_badge"] = (
                    f"{dep_line} {d_period_lbl} 배차 {dh_min}~{dh_max}분 (대기 약 {d_avg_wait}분)"
                )

        actual_stops = max(1, len(path_steps) - 1)
        dur_str = format_duration_kr(est_minutes)
        summary = (
            f"{s_name} ➔ {e_name} (환승 없음 [직통], {actual_stops}개 역 이동, 약 {dur_str}, {total_dist_km}km / {fare_krw:,}원)"
            if len(transfer_stations) == 0
            else f"{s_name} ➔ {e_name} (환승 {len(transfer_stations)}회 [{', '.join(transfer_stations)}], {actual_stops}개 역 이동, 약 {dur_str}, {total_dist_km}km / {fare_krw:,}원)"
        )

        return {
            "from": s_name,
            "to": e_name,
            "path": path_steps,
            "stationCount": actual_stops,
            "estimatedMinutes": est_minutes,
            "transferCount": len(transfer_stations),
            "transferStations": transfer_stations,
            "departureTrain": departure_train,
            "transferTrains": transfer_trains,
            "summary": summary,
            "fareKrw": fare_krw,
            "distanceKm": total_dist_km,
            "fareBreakdown": fare_breakdown,
            "lineSegments": line_segments,
        }

    def _build_subway_segment(
        self, steps: List[Dict[str, Any]], line_name: str, hour: int = 14
    ) -> Dict[str, Any]:
        coords = [s["coords"] for s in steps]
        dist_km = 0.0
        for i in range(1, len(coords)):
            dist_km += haversine_km(
                coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]
            ) * 1.18
        dist_km = round(max(0.8, dist_km), 1)
        stops_cnt = max(1, len(steps) - 1)

        base_line = normalize_base_line_name(line_name)
        spec = LINE_OPERATING_SPECS.get(
            line_name, LINE_OPERATING_SPECS.get(base_line, DEFAULT_LINE_SPEC)
        )
        run_speed_kmh = float(spec["run_speed_kmh"])
        dwell_min = float(spec["dwell_min"])

        # ── 급행열차(Express) 스펙 매칭 및 정차역 스킵 모델링 ──
        is_express = False
        skipped_count = 0
        time_saved = 0
        express_spec = EXPRESS_SPECS.get(line_name) or EXPRESS_SPECS.get(base_line)
        if express_spec and len(steps) >= 3:
            express_stations = set(express_spec["stations"])
            from_clean = steps[0]["name"].replace("역", "").strip()
            to_clean = steps[-1]["name"].replace("역", "").strip()
            # 양 끝 정류장이 모두 급행 정차역인지 확인
            if from_clean in express_stations and to_clean in express_stations:
                # 중간 경유역 중 급행 미정차(통과) 정거장 수 카운트
                intermediate_stops = [s["name"].replace("역", "").strip() for s in steps[1:-1]]
                skipped_stops = [s for s in intermediate_stops if s not in express_stations]
                if len(skipped_stops) >= 2:
                    is_express = True
                    skipped_count = len(skipped_stops)
                    time_saved = max(1, int(round(skipped_count * float(express_spec.get("time_saving_per_skip", 1.15)))))
                    run_speed_kmh = float(express_spec.get("run_speed_kmh", run_speed_kmh))
                    dwell_min = float(express_spec.get("dwell_min", dwell_min))
                    stops_cnt = max(1, (len(steps) - 1) - skipped_count)

        # 물리 주행 공식: (구간 실연장거리 / 노선 순수 주행속도) * 60 + (정차역 수 * 역당 정차·가감속 시간)
        raw_mins = (dist_km / run_speed_kmh) * 60.0 + (stops_cnt * dwell_min)
        mins = max(2, int(round(raw_mins)))

        h_min, h_max, avg_wait, period_lbl = get_line_headway(line_name, hour)
        color = LINE_COLORS.get(line_name, LINE_COLORS.get(base_line, "#38BDF8"))

        label = f"🚇 {line_name}(급행)" if is_express else f"🚇 {line_name}"
        if is_express and express_spec:
            detail = (
                f"{steps[0]['name']} ➔ {steps[-1]['name']} "
                f"({express_spec['name']} · {stops_cnt}개 역 정차 / 일반 {skipped_count}개 역 무정차 통과 · "
                f"{time_saved}분 단축 · {dist_km}km)"
            )
            live_badge = (
                f"⚡ {express_spec['name']} 운행 (일반 대비 {time_saved}분 단축 · 배차 {h_min}~{h_max}분)"
            )
        else:
            detail = f"{steps[0]['name']} ➔ {steps[-1]['name']} ({stops_cnt}개 역 이동 · {dist_km}km)"
            live_badge = f"{line_name} {period_lbl} 배차 {h_min}~{h_max}분 (대기 약 {avg_wait}분)"

        return {
            "mode": "subway",
            "label": label,
            "line_name": line_name,
            "from_name": steps[0]["name"],
            "to_name": steps[-1]["name"],
            "detail": detail,
            "minutes": mins,
            "distance_km": dist_km,
            "fare_krw": 0,
            "color": color,
            "stops_count": stops_cnt,
            "coords": coords,
            "live_badge": live_badge,
            "is_express": is_express,
            "skipped_stops": skipped_count,
            "time_saved_minutes": time_saved,
        }

    # ─────────────────────────────────────────────────────────────
    # LangGraph 5단계 노드 및 조건부 라우터 구현
    # ─────────────────────────────────────────────────────────────
    def _build_langgraph(self):
        workflow = StateGraph(MultimodalRouteState)

        workflow.add_node("parse_context_node", self._node_parse_context)
        workflow.add_node("clear_multimodal_tools_node", self._node_clear_multimodal_tools)
        workflow.add_node("rain_safe_tools_node", self._node_rain_safe_tools)
        workflow.add_node("candidate_fusion_node", self._node_candidate_fusion)
        workflow.add_node("factchat_llm_briefing_node", self._node_factchat_llm_briefing)

        workflow.set_entry_point("parse_context_node")

        workflow.add_conditional_edges(
            "parse_context_node",
            self._weather_gate_router,
            {
                "CLEAR_MULTIMODAL": "clear_multimodal_tools_node",
                "RAIN_SAFE_ONLY": "rain_safe_tools_node",
            },
        )

        workflow.add_edge("clear_multimodal_tools_node", "candidate_fusion_node")
        workflow.add_edge("rain_safe_tools_node", "candidate_fusion_node")
        workflow.add_edge("candidate_fusion_node", "factchat_llm_briefing_node")
        workflow.add_edge("factchat_llm_briefing_node", END)

        return workflow.compile()

    def _node_parse_context(self, state: MultimodalRouteState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])

        origin_st = self.resolve_station(state.get("from_query", "강남역")) or self.resolve_station("강남역")
        dest_st = self.resolve_station(state.get("to_query", "서울역")) or self.resolve_station("서울역")

        origin_in_seoul = self.is_in_seoul(origin_st["coords"][1], origin_st["coords"][0], origin_st["name"])
        dest_in_seoul = self.is_in_seoul(dest_st["coords"][1], dest_st["coords"][0], dest_st["name"])

        w_ctx = dict(state.get("weather_context") or {})
        rain = float(w_ctx.get("rain", 0.0))
        temp = float(w_ctx.get("temp", 15.0))
        wind = float(w_ctx.get("wind", 2.0))
        humidity = float(w_ctx.get("humidity", 55.0))

        # 기상 및 권역 게이트 판정:
        # 1) 따릉이(서울시 공공자전거)는 서울특별시 관내에서만 대여·반납 가능하므로 서울 외 지역(경기·인천) 출발 시 자동 배제
        # 2) 강수량 > 0mm 또는 강풍(>= 8m/s) 또는 혹한(<= -5°C) 시 따릉이(PM) 차단
        is_rainy_or_severe = rain > 0.0 or wind >= 8.0 or temp <= -5.0
        bike_enabled = (not is_rainy_or_severe) and origin_in_seoul
        if not origin_in_seoul:
            gate_reason = f"출발지({origin_st['name']})가 서울특별시 외 지역(경기·인천)이므로 서울시 전용 공공자전거 따릉이 대여 대상에서 제외하고 광역 지하철·버스 경로를 탐색합니다."
        elif rain > 0.0:
            gate_reason = f"강수 감지({rain:.1f}mm/h) — 노면 미끄럼 사고 예방을 위해 따릉이(PM) First/Last-Mile 경로를 자동 배제하고 실내 환승/지하철·버스 안전 경로로 우회합니다."
        elif wind >= 8.0:
            gate_reason = f"강풍 주의({wind:.1f}m/s) — 주행 안전을 위해 따릉이(PM)를 제외하고 대중교통 경로를 우선 추천합니다."
        elif temp <= -5.0:
            gate_reason = f"한파 감지({temp:.1f}°C) — 동절기 안전을 위해 실내 대중교통 경로를 우선 탐색합니다."
        else:
            gate_reason = f"양호한 기상({temp:.1f}°C · 강수 0.0mm) — 서울시 따릉이(First/Last-Mile) + 지하철 + 버스 멀티모달 복합 탐색이 활성화되었습니다."

        w_ctx.update(
            {
                "temp": round(temp, 1),
                "rain": round(rain, 1),
                "humidity": round(humidity, 1),
                "wind": round(wind, 1),
                "bike_enabled": bike_enabled,
                "origin_in_seoul": origin_in_seoul,
                "dest_in_seoul": dest_in_seoul,
                "weather_gate_reason": gate_reason,
            }
        )

        weather_gate = "CLEAR_MULTIMODAL" if bike_enabled else "RAIN_SAFE_ONLY"
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 1,
                "node": "parse_context_node",
                "status": "completed",
                "decision": weather_gate,
                "detail": f"출발({origin_st['name']}) ➔ 도착({dest_st['name']}) 좌표 해석 완료 · 기상 게이트={weather_gate}",
                "latency_ms": elapsed_ms,
            }
        )

        return {
            "origin": origin_st,
            "destination": dest_st,
            "weather_context": w_ctx,
            "weather_gate": weather_gate,
            "langgraph_trace": trace,
        }

    def _weather_gate_router(self, state: MultimodalRouteState) -> str:
        return state.get("weather_gate", "CLEAR_MULTIMODAL")

    def _node_clear_multimodal_tools(self, state: MultimodalRouteState) -> Dict[str, Any]:
        """맑은 날: 지하철 Tool + 버스 Tool + 따릉이 First/Last-Mile Tool 전체 가동"""
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])
        origin = state["origin"]
        dest = state["destination"]
        hour = int(state.get("hour", 14))
        live_arrs = state.get("live_subway_arrivals") or []
        o_lng, o_lat = origin["coords"]
        d_lng, d_lat = dest["coords"]

        # 1. Subway Tool (최소환승 & 최단시간, 시간대별 배차 및 실시간 도착정보 연동)
        sub_min_tr = self.search_subway_route(
            origin["name"], dest["name"], mode="min_transfer", hour=hour, live_arrivals=live_arrs
        )
        sub_min_tm = self.search_subway_route(
            origin["name"], dest["name"], mode="min_time", hour=hour, live_arrivals=live_arrs
        )

        # 2. Bus Tool (출발/도착 인근 버스 환승 거점 탐색)
        origin_buses = self.find_nearby_bus_stops(o_lat, o_lng, limit=2, station_name=origin["name"])
        dest_buses = self.find_nearby_bus_stops(d_lat, d_lng, limit=2, station_name=dest["name"])

        # 3. Bike (따릉이) First/Last-Mile Tool (서울특별시 관내 한정)
        live_bike_list = (state.get("bike_candidates") or {}).get("live_snapshot")
        origin_bikes = self.find_nearby_bike_stations(o_lat, o_lng, live_bike_list, limit=2, station_name=origin["name"])
        dest_bikes = self.find_nearby_bike_stations(d_lat, d_lng, live_bike_list, limit=2, station_name=dest["name"])

        # First-Mile 최적 환승역 탐색:
        # 1) 역방향 우회(제자리걸음) 원천 차단: 후보 역에서 출발하는 지하철 경로(cand_route["path"])에
        #    원래 출발역(origin["name"])이 포함되어 있으면 즉시 배제 (예: 서울역 ➔ 회현역 따릉이 ➔ 회현역에서 다시 서울역 경유 방지)
        # 2) 전진 방향 검증: 후보 역에서 도착지까지의 직선거리가 출발지~도착지 직선거리보다 가까워야 함
        # 3) 실질적 이득 검증: 기존 지하철 경로 대비 경유 역 수(stationCount) 또는 환승 횟수(transferCount)가 줄어들어야 함
        # 4) 서울시 권역 검증: 따릉이 반납 대여소가 존재하는 서울특별시 관내 역만 후보로 허용
        origin_to_dest_km = haversine_km(o_lat, o_lng, d_lat, d_lng)
        nearby_origins = self.find_nearby_subway_stations(
            o_lat, o_lng, radius_km=2.6, exclude_name=origin["name"]
        )
        best_first_mile = None
        best_score = 1e9
        base_transfers = sub_min_tr["transferCount"] if sub_min_tr else 99
        base_minutes = sub_min_tr["estimatedMinutes"] if sub_min_tr else 999
        base_stations = sub_min_tr["stationCount"] if sub_min_tr else 999

        for cand_st in nearby_origins[:15]:
            if cand_st["name"] == dest["name"]:
                continue
            cand_lng, cand_lat = cand_st["coords"]
            # 따릉이 반납 역도 반드시 서울특별시 관내여야 함
            if not self.is_in_seoul(cand_lat, cand_lng, cand_st["name"]):
                continue
            cand_to_dest_km = haversine_km(cand_lat, cand_lng, d_lat, d_lng)
            # 목적지 방향 전진 여부 검증 (반대 방향 역 배제)
            if cand_to_dest_km >= origin_to_dest_km - 0.15:
                continue

            cand_route = self.search_subway_route(cand_st["name"], dest["name"], mode="min_transfer", hour=hour)
            if not cand_route:
                continue

            # [핵심] 후보 역 이후 지하철 경로에 원래 출발역이 다시 포함되면 역방향 제자리걸음이므로 즉시 배제
            cand_path_names = {p["name"] for p in (cand_route.get("path") or [])}
            if origin["name"] in cand_path_names:
                continue

            # 지하철 경유 역 수가 원래보다 줄어들지 않으면 배제
            if cand_route["stationCount"] >= base_stations:
                continue

            bike_dist_km = max(0.6, round(cand_st["distance_km"] * 1.22, 1))
            bike_minutes = max(4, round(bike_dist_km / 0.25))  # 평균 시속 15km (분당 250m)
            total_cand_min = bike_minutes + cand_route["estimatedMinutes"]

            # 평가 점수: 환승 감소 가중치 + 총 소요시간 + 남은 지하철 역 수
            score = (cand_route["transferCount"] * 12.0) + total_cand_min + (cand_route["stationCount"] * 0.5)
            if (
                cand_route["transferCount"] <= base_transfers
                and total_cand_min <= base_minutes + 5
                and score < best_score
            ):
                best_score = score
                best_first_mile = {
                    "target_station": cand_st,
                    "bike_distance_km": bike_dist_km,
                    "bike_minutes": bike_minutes,
                    "subway_route": cand_route,
                    "total_minutes": total_cand_min,
                }

        # 반경 탐색에서 조건을 만족하는 역이 없다면, 원래 지하철 경로(sub_min_tr["path"]) 상의
        # 전방 1~3번째 역 중 거리 0.4~2.8km 이내 서울 관내 역으로 선행 진입하는 First-Mile 경로 구성 (역방향 발생 원천 차단)
        if best_first_mile is None and sub_min_tr:
            base_path = sub_min_tr.get("path") or []
            for step_st in base_path[1:4]:
                if step_st["name"] == dest["name"]:
                    continue
                s_lng, s_lat = step_st["coords"]
                if not self.is_in_seoul(s_lat, s_lng, step_st["name"]):
                    continue
                d_km = round(haversine_km(o_lat, o_lng, s_lat, s_lng), 2)
                if 0.4 <= d_km <= 2.8:
                    cand_route = self.search_subway_route(step_st["name"], dest["name"], mode="min_transfer", hour=hour)
                    if cand_route and origin["name"] not in {p["name"] for p in (cand_route.get("path") or [])}:
                        bike_dist_km = max(0.6, round(d_km * 1.22, 1))
                        bike_minutes = max(4, round(bike_dist_km / 0.25))
                        best_first_mile = {
                            "target_station": {
                                "name": step_st["name"],
                                "coords": step_st["coords"],
                                "lines": step_st.get("lines", []),
                                "distance_km": d_km,
                            },
                            "bike_distance_km": bike_dist_km,
                            "bike_minutes": bike_minutes,
                            "subway_route": cand_route,
                            "total_minutes": bike_minutes + cand_route["estimatedMinutes"],
                        }
                        break

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 2,
                "node": "clear_multimodal_tools_node",
                "status": "completed",
                "decision": "SUBWAY + BUS + BIKE_FIRST_MILE",
                "detail": (
                    f"지하철 경로 탐색 완료 · 인근 버스정류소 {len(origin_buses)}개 · "
                    f"따릉이 대여소 {len(origin_bikes)}개(잔여 {origin_bikes[0]['available_bikes'] if origin_bikes else 0}대) 연동"
                ),
                "latency_ms": elapsed_ms,
            }
        )

        return {
            "subway_candidates": {
                "min_transfer": sub_min_tr,
                "min_time": sub_min_tm,
            },
            "bus_candidates": {
                "origin_stops": origin_buses,
                "dest_stops": dest_buses,
            },
            "bike_candidates": {
                "enabled": True,
                "origin_bikes": origin_bikes,
                "dest_bikes": dest_bikes,
                "first_mile_option": best_first_mile,
            },
            "langgraph_trace": trace,
        }

    def _node_rain_safe_tools(self, state: MultimodalRouteState) -> Dict[str, Any]:
        """우천/악천후 또는 서울 외 지역 출발 시: 따릉이(PM) Tool 자동 차단 + 지하철/버스 안전 경로 Tool 실행"""
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])
        origin = state["origin"]
        dest = state["destination"]
        hour = int(state.get("hour", 14))
        live_arrs = state.get("live_subway_arrivals") or []
        w_ctx = state.get("weather_context") or {}
        origin_in_seoul = bool(w_ctx.get("origin_in_seoul", True))
        o_lng, o_lat = origin["coords"]
        d_lng, d_lat = dest["coords"]

        sub_min_tr = self.search_subway_route(
            origin["name"], dest["name"], mode="min_transfer", hour=hour, live_arrivals=live_arrs
        )
        sub_min_tm = self.search_subway_route(
            origin["name"], dest["name"], mode="min_time", hour=hour, live_arrivals=live_arrs
        )
        origin_buses = self.find_nearby_bus_stops(o_lat, o_lng, limit=2, station_name=origin["name"])
        dest_buses = self.find_nearby_bus_stops(d_lat, d_lng, limit=2, station_name=dest["name"])

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 2,
                "node": "rain_safe_tools_node",
                "status": "completed",
                "decision": "BIKE_EXCLUDED_NON_SEOUL" if not origin_in_seoul else "BIKE_EXCLUDED_BY_WEATHER_GATE",
                "detail": (
                    f"서울 외 권역({origin['name']}) 출발 — 서울시 전용 따릉이(PM)를 제외하고 광역 지하철 및 버스 연계 경로만 수집"
                    if not origin_in_seoul
                    else "우천/강풍 안전 게이트 작동 — 따릉이(PM) 탐색을 자동 차단하고 지하철 직결 및 실내 환승·버스 연계 경로만 수집"
                ),
                "latency_ms": elapsed_ms,
            }
        )

        return {
            "subway_candidates": {
                "min_transfer": sub_min_tr,
                "min_time": sub_min_tm,
            },
            "bus_candidates": {
                "origin_stops": origin_buses,
                "dest_stops": dest_buses,
            },
            "bike_candidates": {
                "enabled": False,
                "origin_bikes": [],
                "dest_bikes": [],
                "first_mile_option": None,
            },
            "langgraph_trace": trace,
        }

    def _node_candidate_fusion(self, state: MultimodalRouteState) -> Dict[str, Any]:
        """수집된 지하철·버스·따릉이 Tool 결과를 조합하여 3종의 멀티모달 경로 후보 생성"""
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])

        origin = state["origin"]
        dest = state["destination"]
        w_ctx = state.get("weather_context", {})
        ai_cong = state.get("ai_congestion", {})
        bike_enabled = bool(w_ctx.get("bike_enabled", True))
        rain = float(w_ctx.get("rain", 0.0))

        sub_cands = state.get("subway_candidates", {})
        bus_cands = state.get("bus_candidates", {})
        bike_cands = state.get("bike_candidates", {})

        base_sub = sub_cands.get("min_transfer")
        fast_sub = sub_cands.get("min_time") or base_sub

        sub_crowd = int(ai_cong.get("subway_crowd", 52))
        bus_crowd = int(ai_cong.get("bus_crowd", 58))
        bike_crowd = int(ai_cong.get("bike_crowd", 25))

        routes: List[Dict[str, Any]] = []

        # ── 1) 맑은 날: [따릉이 First-Mile + 지하철] 복합 경로를 AI 1순위로 생성 ──
        if bike_enabled and base_sub:
            fm = bike_cands.get("first_mile_option")
            origin_bikes = bike_cands.get("origin_bikes") or []
            dest_bikes = bike_cands.get("dest_bikes") or []
            bike_stop = origin_bikes[0] if origin_bikes else {
                "name": f"따릉이: {origin['name']} 대여소",
                "coords": origin["coords"],
                "available_bikes": 9,
            }
            avail_cnt = int(bike_stop.get("available_bikes", 8))

            direct_dist_km = round(
                haversine_km(
                    origin["coords"][1],
                    origin["coords"][0],
                    dest["coords"][1],
                    dest["coords"][0],
                )
                * 1.25,
                1,
            )

            if direct_dist_km <= 3.8 and w_ctx.get("dest_in_seoul", True):
                # 단거리(3.8km 이하, 서울 관내): 따릉이 논스톱 직결 경로 제안
                bike_mins = max(8, round(direct_dist_km / 0.24))
                dest_bike_stop = dest_bikes[0] if dest_bikes else {
                    "name": f"따릉이: {dest['name']} 반납소",
                    "coords": dest["coords"],
                }
                segments = [
                    {
                        "mode": "walk",
                        "label": "🚶 도보 이동",
                        "from_name": origin["name"],
                        "to_name": bike_stop["name"],
                        "detail": f"{origin['name']} 인근 대여소 도보 접근",
                        "minutes": 2,
                        "distance_km": 0.15,
                        "fare_krw": 0,
                        "color": "#94A3B8",
                        "coords": [origin["coords"], bike_stop["coords"]],
                        "live_badge": f"대여 가능 {avail_cnt}대",
                    },
                    {
                        "mode": "bike",
                        "label": "🚲 따릉이 직결 라이딩",
                        "from_name": bike_stop["name"],
                        "to_name": dest_bike_stop["name"],
                        "detail": f"{bike_stop['name']} ➔ {dest_bike_stop['name']} (자전거 전용도로 우선)",
                        "minutes": bike_mins,
                        "distance_km": direct_dist_km,
                        "fare_krw": 1000,
                        "color": "#10B981",
                        "coords": [bike_stop["coords"], dest["coords"]],
                        "live_badge": f"실시간 잔여 {avail_cnt}대 · 쾌적",
                    },
                ]
                routes.append(
                    self._pack_route_candidate(
                        route_id="route-ai-bike-direct",
                        category="AI 멀티모달 최적",
                        title="따릉이 논스톱 에코 라이딩",
                        badge="AI 1순위 · 맑은날 단거리 최적",
                        badge_color="#10B981",
                        is_ai_recommended=True,
                        total_minutes=bike_mins + 2,
                        total_fare_krw=1000,
                        total_distance_km=round(direct_dist_km + 0.15, 1),
                        transfer_count=0,
                        outdoor_walk_minutes=2,
                        crowd_percent=bike_crowd,
                        comfort_score=94,
                        modes_used=["walk", "bike"],
                        highlights=[
                            f"🚲 {bike_stop['name']} 실시간 {avail_cnt}대 대여 가능",
                            "☀️ 맑은 날씨 단거리 환승 대기시간 0분",
                            "💰 1,000원 일일권으로 교통비 절감",
                        ],
                        segments=segments,
                        base_subway_route=base_sub,
                    )
                )
            elif fm and fm.get("subway_route"):
                # 중·장거리: [따릉이 First-Mile + 지하철] 복합 경로
                target_st = fm["target_station"]
                sub_rt = fm["subway_route"]
                bike_mins = int(fm["bike_minutes"])
                bike_km = float(fm["bike_distance_km"])

                segments = [
                    {
                        "mode": "walk",
                        "label": "🚶 도보 접근",
                        "from_name": origin["name"],
                        "to_name": bike_stop["name"],
                        "detail": f"{origin['name']} ➔ {bike_stop['name']}",
                        "minutes": 2,
                        "distance_km": 0.15,
                        "fare_krw": 0,
                        "color": "#94A3B8",
                        "coords": [origin["coords"], bike_stop["coords"]],
                        "live_badge": f"잔여 {avail_cnt}대",
                    },
                    {
                        "mode": "bike",
                        "label": "🚲 따릉이 First-Mile",
                        "from_name": bike_stop["name"],
                        "to_name": target_st["name"],
                        "detail": f"{bike_stop['name']} ➔ {target_st['name']} 반납소 ({bike_km}km 라이딩)",
                        "minutes": bike_mins,
                        "distance_km": bike_km,
                        "fare_krw": 1000,
                        "color": "#10B981",
                        "coords": [bike_stop["coords"], target_st["coords"]],
                        "live_badge": f"실시간 {avail_cnt}대 대여 가능",
                    },
                ] + list(sub_rt.get("lineSegments") or [])

                total_min = 2 + bike_mins + int(sub_rt["estimatedMinutes"])
                total_km = round(0.15 + bike_km + float(sub_rt["distanceKm"]), 1)
                total_fare = 1000 + int(sub_rt["fareKrw"])
                avg_crowd = int(round(bike_crowd * 0.35 + sub_crowd * 0.65))

                routes.append(
                    self._pack_route_candidate(
                        route_id="route-ai-multimodal",
                        category="AI 멀티모달 최적",
                        title=f"따릉이 First-Mile + {sub_rt['from']} 지하철 연계",
                        badge="AI 1순위 · First-Mile 복합",
                        badge_color="#10B981",
                        is_ai_recommended=True,
                        total_minutes=total_min,
                        total_fare_krw=total_fare,
                        total_distance_km=total_km,
                        transfer_count=int(sub_rt["transferCount"]) + 1,
                        outdoor_walk_minutes=2,
                        crowd_percent=avg_crowd,
                        comfort_score=max(75, 96 - int(avg_crowd * 0.25)),
                        modes_used=["walk", "bike", "subway"],
                        highlights=[
                            f"🚲 {bike_stop['name']} 실시간 {avail_cnt}대 거치 중",
                            f"🚇 {target_st['name']} 직결 진입으로 초기 혼잡 구간 회피",
                            f"☀️ 기상 양호({w_ctx.get('temp', 15)}°C) · 쾌적도 상위 경로",
                        ],
                        segments=segments,
                        base_subway_route=sub_rt,
                        override_origin_coords=origin["coords"],
                    )
                )

        # ── 2) 지하철 최소환승 정시성 경로 (우천 시 AI 1순위 / 맑은 날 2순위) ──
        if base_sub:
            is_top_for_rain = not bike_enabled
            sub_segments = list(base_sub.get("lineSegments") or [])
            dep_train = base_sub.get("departureTrain")
            sub_total_min = sum(int(seg["minutes"]) for seg in sub_segments) or int(base_sub["estimatedMinutes"])

            routes.append(
                self._pack_route_candidate(
                    route_id="route-subway-optimal",
                    category="지하철 최소환승",
                    title=(
                        f"지하철 최소환승 안심 경로 ({base_sub['transferCount']}회 환승)"
                        if base_sub["transferCount"] > 0
                        else "지하철 무환승 직통 경로"
                    ),
                    badge=(
                        "AI 1순위 · 우천 정시성 최고"
                        if is_top_for_rain
                        else "정시성 최우수 · 최소환승"
                    ),
                    badge_color="#38BDF8",
                    is_ai_recommended=is_top_for_rain,
                    total_minutes=sub_total_min,
                    total_fare_krw=int(base_sub["fareKrw"]),
                    total_distance_km=float(base_sub["distanceKm"]),
                    transfer_count=int(base_sub["transferCount"]),
                    outdoor_walk_minutes=2,
                    crowd_percent=sub_crowd,
                    comfort_score=max(68, 95 - int(sub_crowd * 0.3)),
                    modes_used=["walk", "subway"] if base_sub["transferCount"] > 0 else ["subway"],
                    highlights=[
                        (
                            f"🌧️ 강수({rain}mm) 영향 없는 100% 실내 철도망"
                            if rain > 0
                            else f"🚇 환승 {base_sub['transferCount']}회 · {base_sub['stationCount']}개 역 정시 운행"
                        ),
                        (
                            f"🟢 실시간 열차: {origin['name']} {dep_train['arrivalMessage']} ({dep_train.get('headwayLabel', '')})"
                            if dep_train and dep_train.get("isLive")
                            else f"⏱️ 출발역({origin['name']}) {dep_train['arrivalMessage'] if dep_train else '배차 4~6분'}"
                        ),
                        f"💳 수도권 거리비례 운임 {base_sub['fareKrw']:,}원 ({base_sub['distanceKm']}km)",
                    ],
                    segments=sub_segments,
                    base_subway_route=base_sub,
                )
            )

        # ── 3) 버스 + 지하철 복합 환승 경로 (서울시 대중교통환승 API getPathInfoByBusNSub 우선 연동) ──
        if base_sub:
            hour = int(state.get("hour", 14))
            is_peak_hour = hour in (7, 8, 9, 18, 19, 20)
            live_buses = state.get("live_bus_arrivals") or []
            o_lng, o_lat = origin["coords"]
            d_lng, d_lat = dest["coords"]
            origin_in_seoul = bool(w_ctx.get("origin_in_seoul", True))
            dest_in_seoul = bool(w_ctx.get("dest_in_seoul", True))

            # 서울시 실시간 대중교통환승경로 API 조회 (출발/도착 중 최소 1곳이 서울 권역인 경우 우선 적용)
            real_transfer_routes = []
            if origin_in_seoul or dest_in_seoul:
                real_transfer_routes = self.fetch_public_transit_transfer_routes(o_lng, o_lat, d_lng, d_lat)

            hybrid_built = False
            if real_transfer_routes:
                # 1순위: 버스와 지하철이 모두 포함된 복합 환승 경로
                # 2순위: 버스 포함 경로
                hybrid_cands = [r for r in real_transfer_routes if r.get("has_bus") and r.get("has_subway")]
                if not hybrid_cands:
                    hybrid_cands = [r for r in real_transfer_routes if r.get("has_bus")] or real_transfer_routes

                if hybrid_cands:
                    best_cand = min(hybrid_cands, key=lambda x: x.get("total_minutes") or 999)
                    legs = best_cand["legs"]

                    segments = []
                    # 1) 출발역에서 첫 승차지까지 도보 이동
                    first_l = legs[0]
                    w_start_dist = haversine_km(o_lat, o_lng, first_l["from_coords"][1], first_l["from_coords"][0])
                    if w_start_dist > 0.04:
                        w_mins = max(1, min(7, round(w_start_dist * 1000 / 65)))
                        segments.append({
                            "mode": "walk",
                            "label": f"🚶 정류장 도보 이동",
                            "from_name": origin["name"],
                            "to_name": first_l["from_name"],
                            "detail": f"{origin['name']} ➔ {first_l['from_name']} 도보 {w_mins}분 ({round(w_start_dist, 2)}km)",
                            "minutes": w_mins,
                            "distance_km": round(w_start_dist, 2),
                            "fare_krw": 0,
                            "color": "#94A3B8",
                            "coords": [origin["coords"], first_l["from_coords"]],
                            "live_badge": f"도보 {w_mins}분",
                        })

                    bus_lines_used = []
                    transfer_step_names = []
                    first_bus_badge = "서울시 실시간 버스 연동"
                    first_bus_line = ""

                    for i, leg in enumerate(legs):
                        leg_dist_km = round(
                            haversine_km(
                                leg["from_coords"][1], leg["from_coords"][0],
                                leg["to_coords"][1], leg["to_coords"][0]
                            ) * 1.15,
                            1
                        )
                        if leg["mode"] == "bus":
                            b_num = leg["route_name"]
                            bus_lines_used.append(b_num)
                            b_cat = get_bus_category_label(b_num)
                            b_color = get_bus_line_color(b_num)

                            # 실시간 버스 도착 정보 매칭
                            bus_badge = "첨두시 배차 4~7분 · 실시간 연동" if is_peak_hour else "평시 배차 6~10분 · 실시간 연동"
                            if live_buses:
                                clean_b = b_num.replace("번", "").strip()
                                for b_arr in live_buses:
                                    r_nm = str(b_arr.get("route_name", "")).strip()
                                    if clean_b and (clean_b in r_nm or r_nm in clean_b):
                                        m1 = str(b_arr.get("arrival_msg1", "")).strip()
                                        m2 = str(b_arr.get("arrival_msg2", "")).strip()
                                        if m1:
                                            bus_badge = f"🟢 실시간: {m1}"
                                            if m2 and m2 not in ("도착정보없음", "출발대기", ""):
                                                bus_badge += f" (다음: {m2})"
                                        break
                                # 일치하는 노선명이 없더라도 live_buses가 주입된 경우 (테스트 주입 또는 환승 정류소 실시간 버스)
                                if bus_badge.startswith("첨두시") or bus_badge.startswith("평시"):
                                    single_arr = live_buses[0]
                                    m1 = str(single_arr.get("arrival_msg1", "")).strip()
                                    m2 = str(single_arr.get("arrival_msg2", "")).strip()
                                    if m1:
                                        bus_badge = f"🟢 실시간: {m1}"
                                        if m2 and m2 not in ("도착정보없음", "출발대기", ""):
                                            bus_badge += f" (다음: {m2})"
                            if not first_bus_line:
                                first_bus_line = b_num
                                first_bus_badge = bus_badge

                            rain_factor = 1.15 if rain > 0 else 1.0
                            bus_mins = max(4, round((leg_dist_km / 0.35) * rain_factor))
                            corridor_coords = self.generate_bus_corridor_coords(
                                leg["from_coords"], leg["to_coords"], bus_route_id=leg.get("route_id")
                            )

                            segments.append({
                                "mode": "bus",
                                "label": f"🚌 {b_cat} {b_num}번",
                                "line_name": f"{b_num}번",
                                "from_name": leg["from_name"],
                                "to_name": leg["to_name"],
                                "detail": f"{leg['from_name']} 승차 ➔ {leg['to_name']} 하차 ({leg_dist_km}km)",
                                "minutes": bus_mins,
                                "distance_km": leg_dist_km,
                                "fare_krw": 1500,
                                "color": b_color,
                                "coords": corridor_coords,
                                "live_badge": bus_badge,
                                "st_id": leg.get("from_id"),
                            })
                        else:  # subway
                            s_line = leg["route_name"]
                            s_color = LINE_COLORS.get(s_line, "#38BDF8")
                            st_cnt = leg.get("station_count") or max(2, round(leg_dist_km / 1.1))
                            sub_mins = max(3, round(st_cnt * 2.2))

                            segments.append({
                                "mode": "subway",
                                "label": f"🚇 {s_line}",
                                "line_name": s_line,
                                "from_name": leg["from_name"],
                                "to_name": leg["to_name"],
                                "detail": f"{leg['from_name']} 승차 ➔ {leg['to_name']} 하차 ({st_cnt}개 역 · {leg_dist_km}km)",
                                "minutes": sub_mins,
                                "distance_km": leg_dist_km,
                                "fare_krw": 1400,
                                "color": s_color,
                                "coords": [leg["from_coords"], leg["to_coords"]],
                                "live_badge": f"{s_line} 정시 운행",
                            })
                            transfer_step_names.append(leg["from_name"])

                        # 중간 환승 도보 구간
                        if i < len(legs) - 1:
                            next_l = legs[i + 1]
                            tr_dist = haversine_km(
                                leg["to_coords"][1], leg["to_coords"][0],
                                next_l["from_coords"][1], next_l["from_coords"][0]
                            )
                            tr_mins = max(2, min(6, round(tr_dist * 1000 / 60) + 1))
                            transfer_step_names.append(leg["to_name"])
                            segments.append({
                                "mode": "walk",
                                "label": f"🔄 {leg['to_name']} 환승",
                                "from_name": leg["to_name"],
                                "to_name": next_l["from_name"],
                                "detail": f"{leg['to_name']} 하차 후 {next_l['route_name']} 환승 ({tr_mins}분)",
                                "minutes": tr_mins,
                                "distance_km": round(tr_dist, 2),
                                "fare_krw": 0,
                                "color": "#F59E0B",
                                "coords": [leg["to_coords"], next_l["from_coords"]],
                                "live_badge": "수도권 환승할인 적용",
                            })

                    # 마지막 하차지에서 최종 목적지까지 도보
                    last_l = legs[-1]
                    w_end_dist = haversine_km(last_l["to_coords"][1], last_l["to_coords"][0], d_lat, d_lng)
                    if w_end_dist > 0.04:
                        w_end_mins = max(1, min(7, round(w_end_dist * 1000 / 65)))
                        segments.append({
                            "mode": "walk",
                            "label": f"🚶 목적지 도보 이동",
                            "from_name": last_l["to_name"],
                            "to_name": dest["name"],
                            "detail": f"{last_l['to_name']} ➔ {dest['name']} 도보 {w_end_mins}분 ({round(w_end_dist, 2)}km)",
                            "minutes": w_end_mins,
                            "distance_km": round(w_end_dist, 2),
                            "fare_krw": 0,
                            "color": "#94A3B8",
                            "coords": [last_l["to_coords"], dest["coords"]],
                            "live_badge": f"도보 {w_end_mins}분",
                        })

                    total_min = sum(int(s["minutes"]) for s in segments)
                    total_km = round(sum(float(s["distance_km"]) for s in segments), 1)
                    fare_krw, _ = calculate_subway_fare(total_km)
                    hybrid_crowd = int(round(bus_crowd * 0.45 + sub_crowd * 0.55))

                    main_bus = first_bus_line or (bus_lines_used[0] if bus_lines_used else "버스")
                    is_hybrid_multimodal = any(s["mode"] == "subway" for s in segments) and any(s["mode"] == "bus" for s in segments)

                    # TransitMap.tsx 호환용 compat_path 구성
                    compat_path = [
                        {
                            "name": origin["name"],
                            "coords": origin["coords"],
                            "lines": ["도보"],
                            "lineUsed": "🚶 도보",
                            "isTransfer": False,
                            "transferInfo": None,
                        }
                    ]
                    for idx_l, leg_item in enumerate(legs):
                        compat_path.append({
                            "name": leg_item["from_name"],
                            "coords": leg_item["from_coords"],
                            "lines": [leg_item["route_name"]],
                            "lineUsed": f"🚌 {leg_item['route_name']}번" if leg_item["mode"] == "bus" else f"🚇 {leg_item['route_name']}",
                            "isTransfer": idx_l > 0,
                            "transferInfo": f"{leg_item['route_name']} 탑승",
                        })
                        compat_path.append({
                            "name": leg_item["to_name"],
                            "coords": leg_item["to_coords"],
                            "lines": [leg_item["route_name"]],
                            "lineUsed": f"🚌 {leg_item['route_name']}번" if leg_item["mode"] == "bus" else f"🚇 {leg_item['route_name']}",
                            "isTransfer": True,
                            "transferInfo": f"{leg_item['to_name']} 하차",
                        })
                    compat_path.append({
                        "name": dest["name"],
                        "coords": dest["coords"],
                        "lines": ["도착"],
                        "lineUsed": "도착",
                        "isTransfer": False,
                        "transferInfo": None,
                    })

                    bus_dep_train = {
                        "line": f"{main_bus}번",
                        "trainLineNm": f"{main_bus}번 ({first_l['from_name']})",
                        "destinationOrNext": f"{first_l['to_name']} 방면",
                        "arrivalMessage": first_bus_badge,
                        "remainingMinutes": 3 if is_peak_hour else 4,
                        "remainingSeconds": (3 if is_peak_hour else 4) * 60,
                    }

                    routes.append(
                        self._pack_route_candidate(
                            route_id="route-bus-subway-hybrid",
                            category="버스+지하철 환승" if is_hybrid_multimodal else "버스 연계 경로",
                            title=f"{main_bus}번 + 지하철 복합 환승" if is_hybrid_multimodal else f"{main_bus}번 버스 환승 경로",
                            badge="서울시 실시간 환승 API 연동",
                            badge_color="#FB923C",
                            is_ai_recommended=False,
                            total_minutes=total_min,
                            total_fare_krw=fare_krw,
                            total_distance_km=total_km,
                            transfer_count=len(legs) - 1,
                            outdoor_walk_minutes=sum(s["minutes"] for s in segments if s["mode"] == "walk"),
                            crowd_percent=hybrid_crowd,
                            comfort_score=max(62, 90 - int(hybrid_crowd * 0.28)),
                            modes_used=list(dict.fromkeys(s["mode"] for s in segments)),
                            highlights=[
                                f"🚌 {first_l['from_name']}에서 {main_bus}번 탑승 ({first_bus_badge})",
                                f"🔄 서울시 공식 실시간 대중교통 환승망 기반 최적 분기",
                                f"💳 수도권 통합환승할인 적용 ({fare_krw:,}원)",
                            ],
                            segments=segments,
                            base_subway_route=base_sub,
                            custom_compat_path=compat_path,
                            custom_transfer_stations=transfer_step_names,
                            custom_departure_train=bus_dep_train,
                        )
                    )
                    hybrid_built = True

            # ── Fallback: 실시간 API 실패 또는 미응답 시 기존 인근 버스정류소 복도 기반 안전 Fallback ──
            if not hybrid_built:
                origin_buses = bus_cands.get("origin_stops") or []
                bus_stop = origin_buses[0] if origin_buses else {
                    "name": f"{origin['name']} 중앙버스정류소",
                    "coords": origin["coords"],
                    "lineInfo": "143, 402, 472",
                    "arsId": "02003",
                }
                bus_line_raw = str(bus_stop.get("lineInfo", "143, 402")).split(",")[0].strip()
                bus_line_name = f"간선 {bus_line_raw}번" if bus_line_raw else "간선 402번"
                bus_badge = (
                    "첨두시 배차 4~7분 · 약 3분 후 도착"
                    if is_peak_hour
                    else "평시 배차 6~10분 · 약 4분 후 도착"
                )

                matched_bus = None
                if live_buses:
                    clean_raw = bus_line_raw.replace("번", "").strip()
                    for b_arr in live_buses:
                        r_nm = str(b_arr.get("route_name", "")).strip()
                        if clean_raw and (clean_raw in r_nm or r_nm in clean_raw):
                            matched_bus = b_arr
                            break
                    if not matched_bus:
                        matched_bus = live_buses[0]

                if matched_bus:
                    bus_line_name = str(matched_bus.get("route_name") or bus_line_name)
                    m1 = str(matched_bus.get("arrival_msg1", "")).strip()
                    m2 = str(matched_bus.get("arrival_msg2", "")).strip()
                    bus_badge = f"🟢 실시간: {m1}" if m1 else "🟢 실시간 도착 정보 연동"
                    if m2 and m2 not in ("도착정보없음", "출발대기", ""):
                        bus_badge += f" (다음: {m2})"

                path_list = base_sub.get("path") or []
                mid_idx = min(max(1, len(path_list) // 3), max(1, len(path_list) - 2))
                transfer_hub_step = path_list[mid_idx] if len(path_list) > 2 else path_list[-1]
                hub_name = transfer_hub_step["name"]
                hub_coords = transfer_hub_step["coords"]

                bus_dist_km = round(
                    max(
                        1.1,
                        haversine_km(
                            origin["coords"][1],
                            origin["coords"][0],
                            hub_coords[1],
                            hub_coords[0],
                        )
                        * 1.25,
                    ),
                    1,
                )
                rain_delay_factor = 1.18 if rain > 0 else 1.0
                bus_mins = max(5, round((bus_dist_km / 0.34) * rain_delay_factor))

                sub_after_hub = self.search_subway_route(
                    hub_name, dest["name"], mode="min_transfer", hour=hour
                )
                if (
                    sub_after_hub
                    and hub_name != dest["name"]
                    and origin["name"] not in {p["name"] for p in (sub_after_hub.get("path") or [])}
                ):
                    hub_sub_line = (sub_after_hub.get("path") or [{}])[0].get("lineUsed", "지하철")
                    bus_route_id_val = str(matched_bus.get("bus_route_id") or "") if matched_bus else None
                    bus_coords = self.generate_bus_corridor_coords(
                        bus_stop["coords"], hub_coords, bus_route_id=bus_route_id_val
                    )
                    hybrid_segments = [
                        {
                            "mode": "walk",
                            "label": "🚶 정류장 이동",
                            "from_name": origin["name"],
                            "to_name": bus_stop["name"],
                            "detail": f"{origin['name']} ➔ {bus_stop['name']} 도보 2분",
                            "minutes": 2,
                            "distance_km": 0.12,
                            "fare_krw": 0,
                            "color": "#94A3B8",
                            "coords": [origin["coords"], bus_stop["coords"]],
                            "live_badge": f"ARS {bus_stop.get('arsId') or '중앙차로'}",
                        },
                        {
                            "mode": "bus",
                            "label": f"🚌 {bus_line_name}",
                            "line_name": bus_line_name,
                            "from_name": bus_stop["name"],
                            "to_name": f"{hub_name} 환승정류소",
                            "detail": f"{bus_stop['name']} 승차 ➔ {hub_name} 하차 ({max(2, round(bus_dist_km * 1.8))}개 정류장 · {bus_dist_km}km)",
                            "minutes": bus_mins,
                            "distance_km": bus_dist_km,
                            "fare_krw": 1500,
                            "color": "#FB923C",
                            "coords": bus_coords,
                            "live_badge": bus_badge,
                        },
                        {
                            "mode": "walk",
                            "label": f"🚶 {hub_name} 지상➔지하 환승",
                            "from_name": f"{hub_name} 정류소",
                            "to_name": f"{hub_name} {hub_sub_line} 승강장",
                            "detail": f"버스 하차 후 {hub_name} {hub_sub_line} 개찰구·승강장 진입 (3분)",
                            "minutes": 3,
                            "distance_km": 0.15,
                            "fare_krw": 0,
                            "color": "#F59E0B",
                            "coords": [hub_coords, hub_coords],
                            "live_badge": "환승할인 적용",
                        },
                    ] + list(sub_after_hub.get("lineSegments") or [])

                    hybrid_min = sum(int(seg["minutes"]) for seg in hybrid_segments)
                    hybrid_km = round(0.12 + bus_dist_km + float(sub_after_hub["distanceKm"]), 1)
                    hybrid_fare, _ = calculate_subway_fare(hybrid_km)
                    hybrid_crowd = int(round(bus_crowd * 0.4 + sub_crowd * 0.6))

                    sub_steps = list(sub_after_hub.get("path") or [])
                    hub_step_sub = sub_steps[0] if sub_steps else {
                        "name": hub_name, "coords": hub_coords, "lines": [hub_sub_line], "lineUsed": hub_sub_line
                    }

                    hybrid_compat_path = [
                        {
                            "name": origin["name"],
                            "coords": origin["coords"],
                            "lines": ["도보"],
                            "lineUsed": "🚶 도보",
                            "isTransfer": False,
                            "transferInfo": None,
                        },
                        {
                            "name": bus_stop["name"],
                            "coords": bus_stop["coords"],
                            "lines": [bus_line_name],
                            "lineUsed": f"🚌 {bus_line_name}",
                            "isTransfer": True,
                            "transferInfo": f"🚌 {bus_line_name} 탑승",
                        },
                        {
                            "name": hub_name,
                            "coords": hub_coords,
                            "lines": hub_step_sub.get("lines", [hub_sub_line]),
                            "lineUsed": hub_step_sub.get("lineUsed", hub_sub_line),
                            "isTransfer": True,
                            "transferInfo": f"🚌 {bus_line_name} 하차 ➔ 🚇 {hub_step_sub.get('lineUsed', hub_sub_line)} 환승",
                        },
                    ] + [dict(p) for p in sub_steps[1:]]

                    hub_dep_train = sub_after_hub.get("departureTrain")
                    if hub_dep_train:
                        hub_dep_tr_dict = dict(hub_dep_train)
                        hub_dep_tr_dict["station"] = hub_name
                        hybrid_transfer_trains = [hub_dep_tr_dict] + list(sub_after_hub.get("transferTrains") or [])
                    else:
                        hybrid_transfer_trains = list(sub_after_hub.get("transferTrains") or [])

                    bus_departure_train = {
                        "line": bus_line_name,
                        "trainLineNm": f"{bus_line_name} ({bus_stop['name']})",
                        "destinationOrNext": f"{hub_name} 방면",
                        "arrivalMessage": bus_badge,
                        "remainingMinutes": 3 if is_peak_hour else 4,
                        "remainingSeconds": (3 if is_peak_hour else 4) * 60,
                    }

                    hybrid_transfer_stations = [hub_name] + [
                        s for s in (sub_after_hub.get("transferStations") or []) if s != hub_name
                    ]

                    routes.append(
                        self._pack_route_candidate(
                            route_id="route-bus-subway-hybrid",
                            category="버스+지하철 환승",
                            title=f"{bus_line_name} + 지하철 복합 환승",
                            badge="환승통로 단축 · 혼잡 분산",
                            badge_color="#FB923C",
                            is_ai_recommended=False,
                            total_minutes=hybrid_min,
                            total_fare_krw=hybrid_fare,
                            total_distance_km=hybrid_km,
                            transfer_count=int(sub_after_hub["transferCount"]) + 1,
                            outdoor_walk_minutes=2,
                            crowd_percent=hybrid_crowd,
                            comfort_score=max(62, 90 - int(hybrid_crowd * 0.28)),
                            modes_used=["walk", "bus", "subway"],
                            highlights=[
                                f"🚌 {bus_stop['name']}에서 {bus_line_name} 탑승 ({bus_badge})",
                                f"🔄 {hub_name} 지상➔지하 환승(3분) 후 {hub_sub_line} 연계",
                                f"💳 수도권 통합환승할인 적용 ({hybrid_fare:,}원)",
                            ],
                            segments=hybrid_segments,
                            base_subway_route=sub_after_hub,
                            custom_compat_path=hybrid_compat_path,
                            custom_transfer_stations=hybrid_transfer_stations,
                            custom_transfer_trains=hybrid_transfer_trains,
                            custom_departure_train=bus_departure_train,
                        )
                    )

        # ── 4) 우천/외곽 시 3번째 후보: 지하철 최단시간(또는 대안) 경로 보강 ──
        if len(routes) < 3 and fast_sub:
            fast_segments = list(fast_sub.get("lineSegments") or [])
            fast_total_min = sum(int(seg["minutes"]) for seg in fast_segments) or int(fast_sub["estimatedMinutes"])
            routes.append(
                self._pack_route_candidate(
                    route_id="route-subway-fast",
                    category="지하철 최단시간",
                    title="지하철 최단시간 급행·직결 중심 경로",
                    badge="최단 주파 · 정시 도착",
                    badge_color="#A855F7",
                    is_ai_recommended=False,
                    total_minutes=fast_total_min,
                    total_fare_krw=int(fast_sub["fareKrw"]),
                    total_distance_km=float(fast_sub["distanceKm"]),
                    transfer_count=int(fast_sub["transferCount"]),
                    outdoor_walk_minutes=3,
                    crowd_percent=min(95, sub_crowd + 5),
                    comfort_score=max(65, 88 - int(sub_crowd * 0.25)),
                    modes_used=["walk", "subway"],
                    highlights=[
                        "⚡ 역 정차 수 최소화 경로 탐색",
                        "🌧️ 도로 정체와 무관한 철도 정시 운행 보장",
                    ],
                    segments=list(fast_sub.get("lineSegments") or []),
                    base_subway_route=fast_sub,
                )
            )

        # ── 5) 다목적 효용 함수(Multi-Objective Utility Score) 기반 합리적 순위 정렬 ──
        # 소요시간(Time), 환승횟수(Transfer), 요금(Fare), 혼잡도(Congestion), 기상적합도(Weather)를 종합 평가하여
        # 무환승 직통 지하철이 훨씬 빠르고 저렴한 경우(예: 서울역➔홍대입구역 공항철도 7분 vs 따릉이 복합 19분)
        # 직통 지하철을 합리적으로 AI 1순위로 선정하고, 따릉이 First-Mile이 시간/환승/혼잡도 측면에서 경쟁력이 있을 때 1순위로 선정합니다.
        if routes:
            min_minutes = min(r["total_minutes"] for r in routes)
            min_fare = min(r["total_fare_krw"] for r in routes)
            base_sub_transfers = int(base_sub["transferCount"]) if base_sub else 0

            for r in routes:
                time_diff = max(0, r["total_minutes"] - min_minutes)
                fare_diff = max(0, r["total_fare_krw"] - min_fare)
                transfers = int(r["transfer_count"])
                crowd = int(r["crowd_percent"])
                has_bike = "bike" in r.get("modes_used", [])
                is_pure_subway = r.get("modes_used") == ["walk", "subway"]

                utility = 100.0
                utility -= time_diff * 1.85           # 최단 경로 대비 추가 소요시간 1분당 -1.85점
                utility -= transfers * 6.0            # 환승 1회당 -6.0점
                utility -= (fare_diff / 500.0) * 2.5  # 추가 요금 500원당 -2.5점
                utility -= crowd * 0.22               # 혼잡도 페널티

                if bike_enabled and has_bike:
                    if r["id"] == "route-ai-bike-direct":
                        utility += 12.0
                    elif transfers <= base_sub_transfers or time_diff <= 4 or sub_crowd >= 68:
                        utility += 14.0
                    else:
                        utility += 3.0

                if not bike_enabled and is_pure_subway:
                    utility += 12.0

                r["comfort_score"] = max(55, min(99, int(round(utility))))
                r["_utility_score"] = round(utility, 2)

            routes.sort(key=lambda x: x["_utility_score"], reverse=True)

            for idx, r in enumerate(routes):
                if idx == 0:
                    r["is_ai_recommended"] = True
                    if "bike" in r.get("modes_used", []):
                        r["badge"] = "AI 1순위 · 멀티모달 최적"
                        r["badge_color"] = "#10B981"
                    elif rain > 0:
                        r["badge"] = "AI 1순위 · 우천 정시성 최고"
                        r["badge_color"] = "#38BDF8"
                    else:
                        r["badge"] = "AI 1순위 · 최단·무환승 최적"
                        r["badge_color"] = "#38BDF8"
                else:
                    r["is_ai_recommended"] = False
                    if "bike" in r.get("modes_used", []):
                        r["badge"] = "맑은날 에코 · First-Mile 대안"
                        r["badge_color"] = "#10B981"
                    elif "bus" in r.get("modes_used", []):
                        r["badge"] = "환승통로 단축 · 혼잡 분산"
                        r["badge_color"] = "#FB923C"
                    else:
                        r["badge"] = "정시성 우수 · 철도 중심"
                        r["badge_color"] = "#38BDF8"

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 3,
                "node": "candidate_fusion_node",
                "status": "completed",
                "decision": f"GENERATED_{len(routes)}_ROUTES",
                "detail": (
                    f"멀티모달 후보 {len(routes)}개 효용 평가 완료 "
                    f"(1순위: {routes[0]['title']} [{routes[0]['total_minutes']}분/{routes[0]['total_fare_krw']:,}원/점수 {routes[0].get('comfort_score')}점])"
                    if routes
                    else "후보 없음"
                ),
                "latency_ms": elapsed_ms,
            }
        )

        return {
            "routes": routes,
            "langgraph_trace": trace,
        }

    def _pack_route_candidate(
        self,
        route_id: str,
        category: str,
        title: str,
        badge: str,
        badge_color: str,
        is_ai_recommended: bool,
        total_minutes: int,
        total_fare_krw: int,
        total_distance_km: float,
        transfer_count: int,
        outdoor_walk_minutes: int,
        crowd_percent: int,
        comfort_score: int,
        modes_used: List[str],
        highlights: List[str],
        segments: List[Dict[str, Any]],
        base_subway_route: Dict[str, Any],
        override_origin_coords: Optional[List[float]] = None,
        custom_compat_path: Optional[List[Dict[str, Any]]] = None,
        custom_transfer_stations: Optional[List[str]] = None,
        custom_transfer_trains: Optional[List[Dict[str, Any]]] = None,
        custom_departure_train: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if crowd_percent >= 75:
            crowd_label = "혼잡"
            crowd_color = "#F43F5E"
        elif crowd_percent >= 50:
            crowd_label = "보통"
            crowd_color = "#FBBF24"
        else:
            crowd_label = "여유"
            crowd_color = "#34D399"

        # 전체 폴리라인 좌표 결합
        all_coords: List[List[float]] = []
        if override_origin_coords:
            all_coords.append(override_origin_coords)
        for seg in segments:
            for c in seg.get("coords") or []:
                if not all_coords or all_coords[-1] != c:
                    all_coords.append(c)

        # TransitMap.tsx 호환용 path 배열 및 출발/환승/도착 핀 메타데이터 정규화
        if custom_compat_path is not None:
            compat_path = [dict(p) for p in custom_compat_path]
            transfer_stations = list(custom_transfer_stations) if custom_transfer_stations is not None else []
            transfer_trains = [dict(t) for t in custom_transfer_trains] if custom_transfer_trains is not None else []
            departure_train = custom_departure_train
        else:
            compat_path = [dict(p) for p in (base_subway_route.get("path") or [])]
            transfer_stations = list(base_subway_route.get("transferStations") or [])
            transfer_trains = [dict(t) for t in (base_subway_route.get("transferTrains") or [])]
            departure_train = base_subway_route.get("departureTrain")

            if override_origin_coords and compat_path:
                actual_origin_name = segments[0].get("from_name", compat_path[0]["name"])
                sub_boarding_station = compat_path[0]["name"]
                # 따릉이 First-Mile 하차 후 지하철 탑승하는 역(예: 숙대입구역)을 환승역 핀으로 전환
                if sub_boarding_station and sub_boarding_station != actual_origin_name:
                    compat_path[0]["isTransfer"] = True
                    compat_path[0]["transferInfo"] = f"🚲 따릉이 반납 ➔ 🚇 {compat_path[0].get('lineUsed', '지하철')} 탑승"
                    if sub_boarding_station not in transfer_stations:
                        transfer_stations = [sub_boarding_station] + transfer_stations
                    if departure_train:
                        transfer_trains = [dict(departure_train)] + transfer_trains
                    departure_train = None

                compat_path = [
                    {
                        "name": actual_origin_name,
                        "coords": override_origin_coords,
                        "lines": ["따릉이 First-Mile"],
                        "lineUsed": "🚲 따릉이",
                        "isTransfer": False,
                        "transferInfo": None,
                    }
                ] + compat_path

        actual_from = compat_path[0]["name"] if compat_path else base_subway_route.get("from", "")
        actual_to = compat_path[-1]["name"] if compat_path else base_subway_route.get("to", "")

        return {
            "id": route_id,
            "category": category,
            "title": title,
            "badge": badge,
            "badge_color": badge_color,
            "is_ai_recommended": is_ai_recommended,
            "total_minutes": total_minutes,
            "formatted_duration": format_duration_kr(total_minutes),
            "total_fare_krw": total_fare_krw,
            "total_distance_km": total_distance_km,
            "transfer_count": transfer_count,
            "outdoor_walk_minutes": outdoor_walk_minutes,
            "crowd_percent": crowd_percent,
            "crowd_label": crowd_label,
            "crowd_color": crowd_color,
            "comfort_score": comfort_score,
            "modes_used": modes_used,
            "highlights": highlights,
            "segments": segments,
            "geometry": all_coords,
            # 기존 TransitRouteResult 호환 필드 (지도 즉시 연동용)
            "from": actual_from,
            "to": actual_to,
            "estimatedMinutes": total_minutes,
            "fareKrw": total_fare_krw,
            "distanceKm": total_distance_km,
            "transferCount": transfer_count,
            "transferStations": transfer_stations,
            "stationCount": max(1, len(compat_path) - 1),
            "departureTrain": departure_train,
            "transferTrains": transfer_trains,
            "fareBreakdown": base_subway_route.get("fareBreakdown", ""),
            "summary": f"{title} · 약 {format_duration_kr(total_minutes)} ({total_distance_km}km / {total_fare_krw:,}원)",
            "path": compat_path,
        }

    def _node_factchat_llm_briefing(self, state: MultimodalRouteState) -> Dict[str, Any]:
        """FactChat / BAZE LLM 추론 브리핑 노드 (API 키 미설정/오류 시 규칙 기반 XAI 브리핑 생성)"""
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])

        origin = state["origin"]
        dest = state["destination"]
        w_ctx = state.get("weather_context", {})
        ai_cong = state.get("ai_congestion", {})
        routes = state.get("routes") or []
        top_route = routes[0] if routes else {}

        base_url = (
            os.getenv("FACTCHAT_BASE_URL")
            or os.getenv("BAZE_BASE_URL")
            or "https://api.baze.co/v1/gateway"
        ).rstrip("/")
        api_key = (
            os.getenv("FACTCHAT_API_KEY") or os.getenv("BAZE_API_KEY") or ""
        ).strip()
        model_name = (
            os.getenv("FACTCHAT_MODEL_NAME") or "gpt-6-luna"
        ).strip()

        has_real_key = bool(
            api_key
            and not api_key.startswith("여기에_")
            and not api_key.startswith("your_")
            and len(api_key) > 10
        )

        briefing: Optional[Dict[str, Any]] = None
        llm_status = "XAI_RULE_ENGINE"
        cache_key = (
            origin["name"],
            dest["name"],
            round(float(w_ctx.get("rain", 0.0)), 1),
            round(float(w_ctx.get("temp", 15.0)), 0),
            top_route.get("id", ""),
        )
        now_ts = time.time()
        if cache_key in self._llm_cache:
            c_ts, c_brief = self._llm_cache[cache_key]
            if now_ts - c_ts < 300.0:
                briefing = dict(c_brief)
                llm_status = briefing.get("source", "FACTCHAT_CACHED")

        if briefing is None and has_real_key and routes:
            try:
                cand_lines = "\n".join(
                    f"- {idx+1}순위 [{r.get('badge')}]: {r.get('title')} (소요 {r.get('total_minutes')}분, 요금 {r.get('total_fare_krw'):,}원, 환승 {r.get('transfer_count')}회, 혼잡도 {r.get('crowd_percent')}%, 종합점수 {r.get('comfort_score')}점)"
                    for idx, r in enumerate(routes[:3])
                )
                prompt_text = (
                    f"출발지: {origin['name']}, 도착지: {dest['name']}\n"
                    f"기상상태: 기온 {w_ctx.get('temp')}°C, 강수량 {w_ctx.get('rain')}mm/h, 풍속 {w_ctx.get('wind')}m/s, "
                    f"따릉이 허용여부={w_ctx.get('bike_enabled')}\n"
                    f"ONNX 혼잡도 예측: 지하철 {ai_cong.get('subway_crowd')}%, 버스 {ai_cong.get('bus_crowd')}%, 따릉이 {ai_cong.get('bike_crowd')}%\n"
                    f"후보 경로 비교:\n{cand_lines}\n"
                    "위 후보들의 소요시간·환승횟수·요금·혼잡도·날씨를 비교하여 왜 1순위 경로가 가장 합리적인 선택인지(대안 경로 대비 장점 포함) 2~3문장으로 간결하고 친절하게 한국어로 브리핑해주세요."
                )
                endpoint = (
                    f"{base_url}/chat/completions"
                    if not base_url.endswith("/chat/completions")
                    else base_url
                )
                resp = requests.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": "당신은 서울시 기상-대중교통 멀티모달 경로 추천 AI 에이전트입니다.",
                            },
                            {"role": "user", "content": prompt_text},
                        ],
                        "max_tokens": 240,
                        "temperature": 0.3,
                    },
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    if content:
                        llm_status = "FACTCHAT_LLM_LIVE"
                        briefing = {
                            "headline": f"🤖 FactChat LLM ({model_name}) 멀티모달 경로 브리핑",
                            "summary": content,
                            "weather_advice": w_ctx.get("weather_gate_reason", ""),
                            "recommended_route_id": top_route.get("id", ""),
                            "model": model_name,
                            "source": "FACTCHAT_BAZE_GATEWAY",
                            "bullets": top_route.get("highlights", []),
                        }
                        self._llm_cache[cache_key] = (now_ts, briefing)
            except Exception as exc:
                logger.info("FactChat LLM call skipped/fallback (%s)", exc)

        if briefing is None:
            rain = float(w_ctx.get("rain", 0.0))
            temp = float(w_ctx.get("temp", 15.0))
            sub_crowd = int(ai_cong.get("subway_crowd", 52))
            bus_crowd = int(ai_cong.get("bus_crowd", 58))
            if rain > 0.0:
                summary_text = (
                    f"현재 {state.get('district', '서울')} 권역에 시간당 {rain:.1f}mm의 강수가 감지되어 "
                    f"LangGraph 기상 게이트가 따릉이(PM) First/Last-Mile 구간을 자동 차단했습니다. "
                    f"32차원 ONNX 모델 예측 결과 도로 정체로 인한 버스 혼잡도({bus_crowd}%) 상승이 예상되므로, "
                    f"우천 지연 영향이 없는 '{top_route.get('title', '지하철 최소환승 경로')}'(약 {top_route.get('total_minutes', 20)}분 소요)를 1순위로 추천합니다."
                )
            else:
                summary_text = (
                    f"현재 기온 {temp:.1f}°C, 강수 0.0mm의 쾌적한 날씨로 따릉이 First-Mile 연계가 활성화되었습니다. "
                    f"ONNX 수요 예측 기준 지하철 혼잡도는 {sub_crowd}%, 버스 혼잡도는 {bus_crowd}% 수준이며, "
                    f"출발지 인근 실시간 따릉이와 도시철도를 결합한 '{top_route.get('title', 'AI 멀티모달 최적 경로')}' 이용 시 "
                    f"약 {top_route.get('total_minutes', 20)}분 만에 가장 쾌적하게 이동할 수 있습니다."
                )

            briefing = {
                "headline": f"🧠 LangGraph × FactChat ({model_name}) 멀티모달 AI 브리핑",
                "summary": summary_text,
                "weather_advice": w_ctx.get("weather_gate_reason", ""),
                "recommended_route_id": top_route.get("id", ""),
                "model": model_name,
                "source": "LANGGRAPH_XAI_ENGINE",
                "bullets": top_route.get("highlights", []),
            }

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 4,
                "node": "factchat_llm_briefing_node",
                "status": "completed",
                "decision": llm_status,
                "detail": f"AI 브리핑 생성 완료 (모델={model_name}, 소스={briefing['source']})",
                "latency_ms": elapsed_ms,
            }
        )

        return {
            "ai_briefing": briefing,
            "langgraph_trace": trace,
        }

    # ─────────────────────────────────────────────────────────────
    # 외부 호출용 메인 진입점
    # ─────────────────────────────────────────────────────────────
    def run_multimodal_search(
        self,
        from_query: str,
        to_query: str,
        district: str = "강남구",
        hour: int = 14,
        weather_context: Optional[Dict[str, Any]] = None,
        ai_congestion: Optional[Dict[str, Any]] = None,
        live_bike_snapshot: Optional[List[Dict[str, Any]]] = None,
        live_subway_arrivals: Optional[List[Dict[str, Any]]] = None,
        live_bus_arrivals: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        initial_state: MultimodalRouteState = {
            "from_query": from_query,
            "to_query": to_query,
            "district": district,
            "hour": hour,
            "weather_context": weather_context or {},
            "ai_congestion": ai_congestion or {},
            "bike_candidates": {"live_snapshot": live_bike_snapshot or []},
            "live_subway_arrivals": live_subway_arrivals or [],
            "live_bus_arrivals": live_bus_arrivals or [],
            "langgraph_trace": [],
        }

        final_state = self.graph_app.invoke(initial_state)
        total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        return {
            "status": "success",
            "engine": "LangGraph StateGraph" if LANGGRAPH_AVAILABLE else "LangGraph Compatible StateGraph",
            "langgraph_native": LANGGRAPH_AVAILABLE,
            "latency_ms": total_ms,
            "origin": final_state.get("origin"),
            "destination": final_state.get("destination"),
            "weather_context": final_state.get("weather_context"),
            "ai_congestion": final_state.get("ai_congestion"),
            "weather_gate": final_state.get("weather_gate"),
            "ai_briefing": final_state.get("ai_briefing"),
            "langgraph_trace": final_state.get("langgraph_trace", []),
            "routes": final_state.get("routes", []),
        }


# 싱글톤 인스턴스
multimodal_routing_engine = MultimodalRoutingEngine()
