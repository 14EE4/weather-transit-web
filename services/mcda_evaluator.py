"""
교통수단별 혼잡도 및 MCDA 다기준 추천 스코어 평가 서비스 (OCP 전략 패턴)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, Mapping, Tuple

AHP_CRITERIA_WEIGHTS: Dict[str, float] = {
    "weather_safety": 0.5714,
    "punctuality": 0.2857,
    "crowd_comfort": 0.1429,
}

SCORE_META_THRESHOLDS: Dict[str, list[Tuple[int, str, str]]] = {
    "subway": [
        (85, "최우선 추천", "#38BDF8"),
        (70, "추천", "#38BDF8"),
        (0, "보통", "#FB923C"),
    ],
    "bus": [
        (80, "최우선 추천", "#38BDF8"),
        (65, "추천", "#38BDF8"),
        (45, "주의 필요", "#FB923C"),
        (0, "비추천", "#F43F5E"),
    ],
    "bike": [
        (75, "최우선 추천", "#10B981"),
        (55, "쾌적", "#10B981"),
        (35, "주의", "#FB923C"),
        (0, "비추천", "var(--color-muted)"),
    ],
}

_district_stats_ref: Mapping[str, Mapping[str, float]] = {}
_district_normalizer: Callable[[str], str] = lambda d: str(d or "").strip()


def configure_mcda_context(
    district_stats: Mapping[str, Mapping[str, float]],
    normalizer: Callable[[str], str],
) -> None:
    """자치구 통계 테이블 및 정규화 함수 주입 (DIP)"""
    global _district_stats_ref, _district_normalizer
    _district_stats_ref = district_stats
    _district_normalizer = normalizer


def get_crowd_color(val: int) -> str:
    if val < 45:
        return "#10B981"  # Emerald
    if val <= 75:
        return "#38BDF8"  # Sky
    return "#F43F5E"  # Rose


def get_score_meta(mode_id: str, score: int) -> Tuple[str, str]:
    """점수에 따른 라벨 및 테마 색상 반환 (테이블 기반 OCP 조회)"""
    rules = SCORE_META_THRESHOLDS.get(mode_id, SCORE_META_THRESHOLDS["bike"])
    for min_score, label, color in rules:
        if score >= min_score:
            return label, color
    return rules[-1][1], rules[-1][2]


def _compute_crowd_percent(volume: float, stats: Mapping[str, float], mode_prefix: str) -> int:
    p95 = stats[f"{mode_prefix}_p95"]
    v_min = stats[f"{mode_prefix}_min"]
    denom = max(1.0, p95 - v_min)
    return int(round(min(100.0, max(5.0, ((volume - v_min) / denom) * 100.0))))


class ModeEvaluator(ABC):
    """교통수단별 혼잡도/MCDA 스코어 평가 전략 인터페이스"""

    mode_id: str

    @abstractmethod
    def evaluate(
        self,
        volume: float,
        rain: float,
        stats: Mapping[str, float],
    ) -> Tuple[int, int, list[str]]:
        """(crowd_percent, mcda_score, reasons) 반환"""


class SubwayEvaluator(ModeEvaluator):
    mode_id = "subway"

    def evaluate(
        self,
        volume: float,
        rain: float,
        stats: Mapping[str, float],
    ) -> Tuple[int, int, list[str]]:
        crowd = _compute_crowd_percent(volume, stats, "subway")
        weather_penalty = 0.0
        delay_risk = 2.0
        crowd_penalty = 0.40 * crowd
        score = int(round(max(25.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

        reasons: list[str] = []
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


class BusEvaluator(ModeEvaluator):
    mode_id = "bus"

    def evaluate(
        self,
        volume: float,
        rain: float,
        stats: Mapping[str, float],
    ) -> Tuple[int, int, list[str]]:
        crowd = _compute_crowd_percent(volume, stats, "bus")
        weather_penalty = min(30.0, 3.5 * rain + (5.0 if rain > 0 else 0.0))
        delay_risk = 12.0 + 2.5 * rain
        crowd_penalty = 0.35 * crowd
        score = int(round(max(10.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

        reasons: list[str] = []
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


class BikeEvaluator(ModeEvaluator):
    mode_id = "bike"

    def evaluate(
        self,
        volume: float,
        rain: float,
        stats: Mapping[str, float],
    ) -> Tuple[int, int, list[str]]:
        crowd = _compute_crowd_percent(volume, stats, "bike")
        weather_penalty = min(85.0, (40.0 + 12.0 * rain) if rain > 0 else 0.0)
        delay_risk = 8.0
        crowd_penalty = 0.15 * crowd
        score = int(round(max(5.0, min(99.0, 100.0 - (weather_penalty + delay_risk + crowd_penalty)))))

        reasons: list[str] = []
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


MODE_EVALUATORS: Dict[str, ModeEvaluator] = {
    "subway": SubwayEvaluator(),
    "bus": BusEvaluator(),
    "bike": BikeEvaluator(),
}


def evaluate_mode(mode_id: str, volume: float, rain: float, district: str) -> Tuple[int, int, list[str]]:
    """레지스트리 기반 수단별 혼잡도·MCDA 스코어 평가"""
    evaluator = MODE_EVALUATORS.get(mode_id)
    if evaluator is None:
        raise ValueError(f"Unsupported transit mode: {mode_id}")
    norm_d = _district_normalizer(district)
    default_stats = next(iter(_district_stats_ref.values()))
    stats = _district_stats_ref.get(norm_d, _district_stats_ref.get("강남구", default_stats))
    return evaluator.evaluate(volume, rain, stats)


def evaluate_subway(volume: float, rain: float, district: str) -> Tuple[int, int, list[str]]:
    return evaluate_mode("subway", volume, rain, district)


def evaluate_bus(volume: float, rain: float, district: str) -> Tuple[int, int, list[str]]:
    return evaluate_mode("bus", volume, rain, district)


def evaluate_bike(volume: float, rain: float, district: str) -> Tuple[int, int, list[str]]:
    return evaluate_mode("bike", volume, rain, district)


def calculate_station_crowd(base: int, hour: int, rain: float, stop_type: str, station_name: str) -> int:
    """특정 지하철역/정류소의 시간대 첨두곡선, 기상 강수 민감도 및 고유 분산 반영 혼잡도 계산"""
    if 8 <= hour <= 9:
        time_mult = 1.25
    elif hour == 7:
        time_mult = 1.15
    elif 18 <= hour <= 19:
        time_mult = 1.22
    elif hour == 17:
        time_mult = 1.15
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
    rain_bonus = min(15, int(round(1.2 * rain * 2.2)))
    crowd = int(round(base * time_mult)) + hash_offset + rain_bonus
    return max(10, min(99, crowd))
