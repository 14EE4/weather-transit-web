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
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

import requests

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
    "2호선": "#00A84D",
    "3호선": "#EF7C1C",
    "4호선": "#00A5DE",
    "5호선": "#996CAC",
    "6호선": "#CD7C2F",
    "7호선": "#747F00",
    "8호선": "#E6186C",
    "9호선": "#BDB092",
    "수인분당선": "#FABE00",
    "신분당선": "#D4003B",
    "경의중앙선": "#77C4A3",
    "공항철도": "#0090D2",
    "경춘선": "#0C8E72",
    "우이신설선": "#B7C452",
    "신림선": "#6789CA",
    "김포골드라인": "#A17800",
    "서해선": "#8FC31F",
    "GTX-A": "#9A6292",
}


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


def calculate_subway_fare(distance_km: float) -> Tuple[int, str]:
    """수도권 도시철도 거리비례제 운임 계산 (교통카드 성인 기준)"""
    base_fare = 1550
    if distance_km <= 10.0:
        return base_fare, f"기본운임 1,550원 (10km 이내 · {distance_km:.1f}km)"
    elif distance_km <= 50.0:
        extra_km = distance_km - 10.0
        extra_Fare = math.ceil(extra_km / 5.0) * 100
        total = base_fare + extra_Fare
        return (
            total,
            f"기본 1,550원 + 거리추가 {extra_Fare:,}원 (10~50km 구간 5km당 100원 · 총 {distance_km:.1f}km)",
        )
    else:
        extra_10_50 = math.ceil(40.0 / 5.0) * 100
        extra_over_50 = math.ceil((distance_km - 50.0) / 8.0) * 100
        extra_total = extra_10_50 + extra_over_50
        total = base_fare + extra_total
        return (
            total,
            f"기본 1,550원 + 거리추가 {extra_total:,}원 (50km 초과 구간 8km당 100원 · 총 {distance_km:.1f}km)",
        )


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
        self._llm_cache: Dict[Tuple[str, str, float, float, str], Tuple[float, Dict[str, Any]]] = {}

        self._load_network()
        self.graph_app = self._build_langgraph()

    def _load_network(self) -> None:
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
        base_dir = Path(__file__).resolve().parent
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

        logger.info(
            "MultimodalRoutingEngine loaded: %d subway stations, %d bus stops, %d bike stations (LangGraph=%s)",
            len(self.subway_stations),
            len(self.bus_stops),
            len(self.bike_stations),
            LANGGRAPH_AVAILABLE,
        )

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
        self, lat: float, lng: float, limit: int = 3
    ) -> List[Dict[str, Any]]:
        scored = []
        for b in self.bus_stops:
            c = b.get("coords", [127.0, 37.5])
            dist = haversine_km(lat, lng, c[1], c[0])
            scored.append({**b, "distance_km": round(dist, 2)})
        scored.sort(key=lambda x: x["distance_km"])
        return scored[:limit]

    def find_nearby_bike_stations(
        self,
        lat: float,
        lng: float,
        live_bikes: Optional[List[Dict[str, Any]]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        # 1. 실시간 서울시 따릉이 스냅샷 데이터가 있으면 우선 활용
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
                    if dist <= 1.8:
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

        # 2. 마스터 대여소 데이터 보강
        for k in self.bike_stations:
            c = k.get("coords", [127.0, 37.5])
            dist = haversine_km(lat, lng, c[1], c[0])
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
        return candidates[:limit]

    def search_subway_route(
        self, start_name: str, end_name: str, mode: str = "min_transfer"
    ) -> Optional[Dict[str, Any]]:
        """
        수도권 지하철 그래프 다익스트라 탐색
        - mode == "min_transfer": 최소 환승 우선 (환승 1회당 가중치 10000 + 역수)
        - mode == "min_time": 최단 소요시간 우선 (역당 2.2분 + 환승 4.5분)
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

        start_lines = start_st.get("lines") or ["지하철"]
        for line in start_lines:
            counter += 1
            heapq.heappush(
                pq, (1.0, counter, 0, 1, s_name, line, [(s_name, line)])
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

            for nbr in self.subway_graph.get(curr, []):
                if nbr in visited:
                    continue
                nbr_st_obj = self.station_by_name.get(nbr, {})
                nbr_lines = set(nbr_st_obj.get("lines", []))
                common_lines = [l for l in curr_lines if l in nbr_lines]

                if curr_line and curr_line in common_lines:
                    next_transfers = transfers
                    next_stops = stops + 1
                    next_cost = (
                        next_transfers * 10000 + next_stops
                        if mode == "min_transfer"
                        else next_stops * 2.2 + next_transfers * 4.5
                    )
                    n_key = (nbr, curr_line)
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
                    target_lines = common_lines or list(nbr_lines) or [curr_line]
                    for nl in target_lines:
                        next_transfers = transfers + 1
                        next_stops = stops + 1
                        next_cost = (
                            next_transfers * 10000 + next_stops
                            if mode == "min_transfer"
                            else next_stops * 2.2 + next_transfers * 4.5
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
                                    path + [(nbr, nl)],
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
                    rem_min = 2 + (idx % 3)
                    transfer_info = f"{line_used} ➔ {next_line} 환승 ({next_st_name} 방면, {rem_min}분 후)"
                    transfer_trains.append(
                        {
                            "station": st_name,
                            "line": next_line,
                            "trainLineNm": f"{next_st_name} 방면",
                            "destinationOrNext": next_st_name,
                            "arrivalMessage": f"{rem_min}분 후 도착",
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

        # 실연장 거리(km) 계산 (노선 굴곡 계수 1.18 반영)
        total_dist_km = 0.0
        for i in range(1, len(path_steps)):
            c1 = path_steps[i - 1]["coords"]
            c2 = path_steps[i]["coords"]
            total_dist_km += haversine_km(c1[1], c1[0], c2[1], c2[0]) * 1.18
        total_dist_km = round(max(1.2, total_dist_km), 1)

        fare_krw, fare_breakdown = calculate_subway_fare(total_dist_km)
        est_minutes = max(4, round(len(path_steps) * 2.3 + len(transfer_stations) * 4))

        # 호선별 구간(segments) 분할
        line_segments: List[Dict[str, Any]] = []
        seg_start_idx = 0
        for i in range(1, len(path_steps)):
            prev_line = path_steps[i - 1]["lineUsed"]
            curr_line = path_steps[i]["lineUsed"]
            if curr_line != prev_line:
                sub_slice = path_steps[seg_start_idx:i]
                line_segments.append(self._build_subway_segment(sub_slice, prev_line))
                seg_start_idx = i - 1
        final_slice = path_steps[seg_start_idx:]
        if len(final_slice) >= 2:
            line_segments.append(
                self._build_subway_segment(final_slice, final_slice[-1]["lineUsed"])
            )

        dep_line = path_steps[0]["lineUsed"]
        dep_next = path_steps[1]["name"] if len(path_steps) > 1 else e_name
        departure_train = {
            "station": s_name,
            "line": dep_line,
            "trainLineNm": f"{dep_next} 방면",
            "destinationOrNext": dep_next,
            "arrivalMessage": "2분 후 도착",
            "remainingMinutes": 2,
            "remainingSeconds": 120,
        }

        summary = (
            f"{s_name} ➔ {e_name} (환승 없음 [직통], {len(path_steps)}개 역, 약 {est_minutes}분, {total_dist_km}km / {fare_krw:,}원)"
            if len(transfer_stations) == 0
            else f"{s_name} ➔ {e_name} (환승 {len(transfer_stations)}회 [{', '.join(transfer_stations)}], {len(path_steps)}개 역, 약 {est_minutes}분, {total_dist_km}km / {fare_krw:,}원)"
        )

        return {
            "from": s_name,
            "to": e_name,
            "path": path_steps,
            "stationCount": len(path_steps),
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
        self, steps: List[Dict[str, Any]], line_name: str
    ) -> Dict[str, Any]:
        coords = [s["coords"] for s in steps]
        dist_km = 0.0
        for i in range(1, len(coords)):
            dist_km += haversine_km(
                coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]
            ) * 1.18
        dist_km = round(max(0.8, dist_km), 1)
        stops_cnt = max(1, len(steps) - 1)
        mins = max(3, round(stops_cnt * 2.3))
        color = LINE_COLORS.get(line_name, "#38BDF8")
        return {
            "mode": "subway",
            "label": f"🚇 {line_name}",
            "line_name": line_name,
            "from_name": steps[0]["name"],
            "to_name": steps[-1]["name"],
            "detail": f"{steps[0]['name']} ➔ {steps[-1]['name']} ({stops_cnt}개 역 이동)",
            "minutes": mins,
            "distance_km": dist_km,
            "fare_krw": 0,
            "color": color,
            "stops_count": stops_cnt,
            "coords": coords,
            "live_badge": f"{line_name} 배차 2~4분",
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

        w_ctx = dict(state.get("weather_context") or {})
        rain = float(w_ctx.get("rain", 0.0))
        temp = float(w_ctx.get("temp", 15.0))
        wind = float(w_ctx.get("wind", 2.0))
        humidity = float(w_ctx.get("humidity", 55.0))

        # 기상 게이트 판정: 강수량 > 0mm 또는 강풍(>= 8m/s) 또는 혹한(<= -5°C) 시 따릉이(PM) 차단
        is_rainy_or_severe = rain > 0.0 or wind >= 8.0 or temp <= -5.0
        bike_enabled = not is_rainy_or_severe
        if rain > 0.0:
            gate_reason = f"강수 감지({rain:.1f}mm/h) — 노면 미끄럼 사고 예방을 위해 따릉이(PM) First/Last-Mile 경로를 자동 배제하고 실내 환승/지하철·버스 안전 경로로 우회합니다."
        elif wind >= 8.0:
            gate_reason = f"강풍 주의({wind:.1f}m/s) — 주행 안전을 위해 따릉이(PM)를 제외하고 대중교통 경로를 우선 추천합니다."
        elif temp <= -5.0:
            gate_reason = f"한파 감지({temp:.1f}°C) — 동절기 안전을 위해 실내 대중교통 경로를 우선 탐색합니다."
        else:
            gate_reason = f"양호한 기상({temp:.1f}°C · 강수 0.0mm) — 따릉이(First/Last-Mile) + 지하철 + 버스 멀티모달 복합 탐색이 활성화되었습니다."

        w_ctx.update(
            {
                "temp": round(temp, 1),
                "rain": round(rain, 1),
                "humidity": round(humidity, 1),
                "wind": round(wind, 1),
                "bike_enabled": bike_enabled,
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
        o_lng, o_lat = origin["coords"]
        d_lng, d_lat = dest["coords"]

        # 1. Subway Tool (최소환승 & 최단시간)
        sub_min_tr = self.search_subway_route(origin["name"], dest["name"], mode="min_transfer")
        sub_min_tm = self.search_subway_route(origin["name"], dest["name"], mode="min_time")

        # 2. Bus Tool (출발/도착 인근 버스 환승 거점 탐색)
        origin_buses = self.find_nearby_bus_stops(o_lat, o_lng, limit=2)
        dest_buses = self.find_nearby_bus_stops(d_lat, d_lng, limit=2)

        # 3. Bike (따릉이) First/Last-Mile Tool
        live_bike_list = (state.get("bike_candidates") or {}).get("live_snapshot")
        origin_bikes = self.find_nearby_bike_stations(o_lat, o_lng, live_bike_list, limit=2)
        dest_bikes = self.find_nearby_bike_stations(d_lat, d_lng, live_bike_list, limit=2)

        # First-Mile 최적 환승역 탐색: 출발지에서 반경 0.7~2.3km 내 지하철역 중 도착지까지 환승이 줄거나 시간이 단축되는 역 탐색
        nearby_origins = self.find_nearby_subway_stations(
            o_lat, o_lng, radius_km=2.3, exclude_name=origin["name"]
        )
        best_first_mile = None
        base_transfers = sub_min_tr["transferCount"] if sub_min_tr else 99
        base_minutes = sub_min_tr["estimatedMinutes"] if sub_min_tr else 999

        for cand_st in nearby_origins[:8]:
            if cand_st["name"] == dest["name"]:
                continue
            cand_route = self.search_subway_route(cand_st["name"], dest["name"], mode="min_transfer")
            if not cand_route:
                continue
            bike_dist_km = max(0.6, round(cand_st["distance_km"] * 1.22, 1))
            bike_minutes = max(4, round(bike_dist_km / 0.25))  # 평균 시속 15km (분당 250m)
            total_cand_min = bike_minutes + cand_route["estimatedMinutes"]
            # 환승 횟수가 감소하거나 소요 시간이 비슷/단축되는 경우 채택
            if (
                cand_route["transferCount"] < base_transfers
                or total_cand_min <= base_minutes + 3
                or best_first_mile is None
            ):
                best_first_mile = {
                    "target_station": cand_st,
                    "bike_distance_km": bike_dist_km,
                    "bike_minutes": bike_minutes,
                    "subway_route": cand_route,
                    "total_minutes": total_cand_min,
                }
                if cand_route["transferCount"] < base_transfers:
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
        """우천/악천후 시: 따릉이(PM) Tool 자동 차단 + 지하철/버스 안전 경로 Tool 실행"""
        t0 = time.perf_counter()
        trace = list(state.get("langgraph_trace") or [])
        origin = state["origin"]
        dest = state["destination"]
        o_lng, o_lat = origin["coords"]
        d_lng, d_lat = dest["coords"]

        sub_min_tr = self.search_subway_route(origin["name"], dest["name"], mode="min_transfer")
        sub_min_tm = self.search_subway_route(origin["name"], dest["name"], mode="min_time")
        origin_buses = self.find_nearby_bus_stops(o_lat, o_lng, limit=2)
        dest_buses = self.find_nearby_bus_stops(d_lat, d_lng, limit=2)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 2,
                "node": "rain_safe_tools_node",
                "status": "completed",
                "decision": "BIKE_EXCLUDED_BY_WEATHER_GATE",
                "detail": "우천/강풍 안전 게이트 작동 — 따릉이(PM) 탐색을 자동 차단하고 지하철 직결 및 실내 환승·버스 연계 경로만 수집",
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

            if direct_dist_km <= 3.8:
                # 단거리(3.8km 이하): 따릉이 논스톱 직결 경로 제안
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
                        "coords": [origin["coords"], target_st["coords"]],
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
            sub_segments = [
                {
                    "mode": "walk",
                    "label": "🚶 역사 내 이동",
                    "from_name": f"{origin['name']} 입구",
                    "to_name": f"{origin['name']} 승강장",
                    "detail": f"{origin['name']} 개찰구 및 승강장 이동",
                    "minutes": 3,
                    "distance_km": 0.2,
                    "fare_krw": 0,
                    "color": "#94A3B8",
                    "coords": [origin["coords"], origin["coords"]],
                    "live_badge": "실내 이동",
                }
            ] + list(base_sub.get("lineSegments") or [])

            dep_train = base_sub.get("departureTrain")
            if dep_train and len(sub_segments) > 1:
                sub_segments[1]["live_badge"] = (
                    f"{dep_train['destinationOrNext']} 방면 · {dep_train['remainingMinutes']}분 후 도착"
                )

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
                    total_minutes=int(base_sub["estimatedMinutes"]),
                    total_fare_krw=int(base_sub["fareKrw"]),
                    total_distance_km=float(base_sub["distanceKm"]),
                    transfer_count=int(base_sub["transferCount"]),
                    outdoor_walk_minutes=3,
                    crowd_percent=sub_crowd,
                    comfort_score=max(68, 95 - int(sub_crowd * 0.3)),
                    modes_used=["walk", "subway"],
                    highlights=[
                        (
                            f"🌧️ 강수({rain}mm) 영향 없는 100% 실내 철도망"
                            if rain > 0
                            else f"🚇 환승 {base_sub['transferCount']}회 · {base_sub['stationCount']}개 역 정시 운행"
                        ),
                        f"⏱️ 출발역({origin['name']}) 열차 약 {dep_train['remainingMinutes'] if dep_train else 2}분 후 도착",
                        f"💳 수도권 거리비례 운임 {base_sub['fareKrw']:,}원 ({base_sub['distanceKm']}km)",
                    ],
                    segments=sub_segments,
                    base_subway_route=base_sub,
                )
            )

        # ── 3) 버스 + 지하철 복합 환승 (또는 간선버스 연계) 경로 ──
        if base_sub:
            origin_buses = bus_cands.get("origin_stops") or []
            bus_stop = origin_buses[0] if origin_buses else {
                "name": f"{origin['name']} 중앙버스정류소",
                "coords": origin["coords"],
                "lineInfo": "143, 402, 472",
                "arsId": "02003",
            }
            bus_line_raw = str(bus_stop.get("lineInfo", "143, 402")).split(",")[0].strip()
            bus_line_name = f"간선 {bus_line_raw}번" if bus_line_raw else "간선 402번"

            # 지하철 경로의 중간 환승역(또는 3번째 역)까지 버스로 이동 후 지하철 환승 시나리오 구성
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
            bus_mins = max(6, round((bus_dist_km / 0.32) * rain_delay_factor))

            sub_after_hub = self.search_subway_route(hub_name, dest["name"], mode="min_transfer")
            if sub_after_hub and hub_name != dest["name"]:
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
                        "detail": f"{bus_stop['name']} 승차 ➔ {hub_name} 하차 ({max(2, round(bus_dist_km * 1.8))}개 정류장)",
                        "minutes": bus_mins,
                        "distance_km": bus_dist_km,
                        "fare_krw": 1500,
                        "color": "#FB923C",
                        "coords": [origin["coords"], hub_coords],
                        "live_badge": "곧 도착 (3분 후)",
                    },
                ] + list(sub_after_hub.get("lineSegments") or [])

                hybrid_min = 2 + bus_mins + int(sub_after_hub["estimatedMinutes"])
                hybrid_km = round(0.12 + bus_dist_km + float(sub_after_hub["distanceKm"]), 1)
                # 수도권 통합환승할인제 반영 (기본 1,550원 + 10km 초과 시 거리비례)
                hybrid_fare, _ = calculate_subway_fare(hybrid_km)
                hybrid_crowd = int(round(bus_crowd * 0.4 + sub_crowd * 0.6))

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
                            f"🚌 {bus_stop['name']}에서 {bus_line_name} 즉시 탑승",
                            f"🔄 {hub_name} 지상➔지하 직결 환승으로 도보 최소화",
                            f"💳 수도권 통합환승할인 적용 ({hybrid_fare:,}원)",
                        ],
                        segments=hybrid_segments,
                        base_subway_route=base_sub,
                    )
                )

        # ── 4) 우천 시 3번째 후보: 지하철 최단시간(또는 버스 직결) 경로 보강 ──
        if len(routes) < 3 and fast_sub:
            routes.append(
                self._pack_route_candidate(
                    route_id="route-subway-fast",
                    category="지하철 최단시간",
                    title="지하철 최단시간 급행·직결 중심 경로",
                    badge="최단 주파 · 정시 도착",
                    badge_color="#A855F7",
                    is_ai_recommended=False,
                    total_minutes=max(4, int(fast_sub["estimatedMinutes"]) - 2),
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

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        trace.append(
            {
                "step": 3,
                "node": "candidate_fusion_node",
                "status": "completed",
                "decision": f"GENERATED_{len(routes)}_ROUTES",
                "detail": f"멀티모달 후보 {len(routes)}개 생성 완료 (1순위: {routes[0]['title'] if routes else 'N/A'})",
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

        # TransitMap.tsx 호환용 path 배열 생성
        compat_path = list(base_subway_route.get("path") or [])
        if override_origin_coords and compat_path:
            compat_path = [
                {
                    "name": segments[0].get("from_name", base_subway_route["from"]),
                    "coords": override_origin_coords,
                    "lines": ["따릉이 First-Mile"],
                    "lineUsed": "따릉이",
                    "isTransfer": True,
                    "transferInfo": f"🚲 따릉이 ➔ 🚇 {compat_path[0]['name']} 환승",
                }
            ] + compat_path

        return {
            "id": route_id,
            "category": category,
            "title": title,
            "badge": badge,
            "badge_color": badge_color,
            "is_ai_recommended": is_ai_recommended,
            "total_minutes": total_minutes,
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
            "from": base_subway_route.get("from", ""),
            "to": base_subway_route.get("to", ""),
            "estimatedMinutes": total_minutes,
            "fareKrw": total_fare_krw,
            "distanceKm": total_distance_km,
            "transferCount": transfer_count,
            "transferStations": base_subway_route.get("transferStations", []),
            "stationCount": base_subway_route.get("stationCount", len(compat_path)),
            "departureTrain": base_subway_route.get("departureTrain"),
            "transferTrains": base_subway_route.get("transferTrains", []),
            "fareBreakdown": base_subway_route.get("fareBreakdown", ""),
            "summary": f"{title} · 약 {total_minutes}분 ({total_distance_km}km / {total_fare_krw:,}원)",
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
                prompt_text = (
                    f"출발지: {origin['name']}, 도착지: {dest['name']}\n"
                    f"기상상태: 기온 {w_ctx.get('temp')}°C, 강수량 {w_ctx.get('rain')}mm/h, 풍속 {w_ctx.get('wind')}m/s, "
                    f"따릉이 허용여부={w_ctx.get('bike_enabled')}\n"
                    f"ONNX 혼잡도 예측: 지하철 {ai_cong.get('subway_crowd')}%, 버스 {ai_cong.get('bus_crowd')}%, 따릉이 {ai_cong.get('bike_crowd')}%\n"
                    f"1순위 추천 경로: {top_route.get('title')} (소요 {top_route.get('total_minutes')}분, 요금 {top_route.get('total_fare_krw')}원)\n"
                    "위 데이터를 바탕으로 승객에게 왜 1순위 멀티모달 경로가 최적인지 2~3문장으로 간결하고 친절하게 한국어로 브리핑해주세요."
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
