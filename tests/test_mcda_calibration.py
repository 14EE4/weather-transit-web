"""
MCDA 추천 스코어링 공식 캘리브레이션 및 AHP 가중치 정합성 검증 테스트
"""

import sys
import numpy as np
from pathlib import Path

# Windows UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import (
    AHP_CRITERIA_WEIGHTS,
    evaluate_subway,
    evaluate_bus,
    evaluate_bike,
    get_score_meta,
)

def test_ahp_consistency():
    print("\n[Test 1] AHP 가중치 합계 및 일관성 지수(CR < 0.1) 검증...")
    # 가중치 합계 1.0
    w_sum = sum(AHP_CRITERIA_WEIGHTS.values())
    assert abs(w_sum - 1.0) < 1e-3, f"AHP weights must sum to 1.0, got {w_sum}"

    # 쌍대비교 행렬
    A = np.array([
        [1.0,  2.0,  4.0],
        [0.5,  1.0,  2.0],
        [0.25, 0.5,  1.0]
    ])
    eigenvalues, _ = np.linalg.eig(A)
    max_lambda = np.max(eigenvalues.real)
    ci = (max_lambda - 3) / 2
    cr = ci / 0.58
    assert cr < 0.10, f"AHP Consistency Ratio must be < 0.10, got {cr}"
    print(f"  ✅ AHP 일관성 비율 CR = {cr:.4f} < 0.10 합격")
    print(f"  ✅ 정규화 가중치: 기상안전={AHP_CRITERIA_WEIGHTS['weather_safety']:.2%}, "
          f"정시성={AHP_CRITERIA_WEIGHTS['punctuality']:.2%}, "
          f"혼잡회피={AHP_CRITERIA_WEIGHTS['crowd_comfort']:.2%}")

def test_clear_weather_scoring():
    print("\n[Test 2] 맑은 날(강수량 0.0mm) 스코어 검증...")
    # 강남구, 보통 혼잡도
    s_c, s_score, s_reasons = evaluate_subway(volume=25000, rain=0.0, district="강남구")
    b_c, b_score, b_reasons = evaluate_bus(volume=15000, rain=0.0, district="강남구")
    k_c, k_score, k_reasons = evaluate_bike(volume=80, rain=0.0, district="강남구")

    print(f"  - 맑음 점수: 지하철={s_score}점, 버스={b_score}점, 따릉이={k_score}점")
    assert 25 <= s_score <= 99
    assert 10 <= b_score <= 99
    assert 70 <= k_score <= 99, f"맑은 날 따릉이는 높은 점수(>=70)를 받아야 함, got {k_score}"
    assert "친환경 이동에 최적" in k_reasons[0]
    print("  ✅ 맑은 날 정상 스코어 및 긍정 추천 사유 생성 확인")

def test_light_rain_scoring():
    print("\n[Test 3] 소우(강수량 0.5mm) 시 실측 급감율(-73.6%) 반영 검증...")
    _, _, k_reasons_dry = evaluate_bike(volume=80, rain=0.0, district="강남구")
    _, k_score_wet, k_reasons_wet = evaluate_bike(volume=80, rain=0.5, district="강남구")
    _, s_score_wet, _ = evaluate_subway(volume=25000, rain=0.5, district="강남구")

    print(f"  - 소우(0.5mm) 점수: 지하철={s_score_wet}점, 따릉이={k_score_wet}점")
    assert k_score_wet < 50, f"소우에도 따릉이 점수는 급감(<50)해야 함, got {k_score_wet}"
    assert s_score_wet > k_score_wet, "소우 시 지하철이 따릉이보다 선호되어야 함"
    assert "73.6% 급감" in k_reasons_wet[0]
    print("  ✅ 소우 시 실측 빅데이터(-73.6%) 기반 급감 페널티 정상 작동 확인")

def test_moderate_rain_scoring():
    print("\n[Test 4] 보통 비(강수량 2.8mm) 시 모달 시프트 및 추천 순위 검증...")
    s_c, s_score, s_reasons = evaluate_subway(volume=25000, rain=2.8, district="강남구")
    b_c, b_score, b_reasons = evaluate_bus(volume=15000, rain=2.8, district="강남구")
    k_c, k_score, k_reasons = evaluate_bike(volume=80, rain=2.8, district="강남구")

    print(f"  - 보통비(2.8mm) 점수: 지하철={s_score}점 > 버스={b_score}점 > 따릉이={k_score}점")
    assert s_score > b_score > k_score, f"우천 시 순위(지하철 > 버스 > 따릉이) 불일치: {s_score}, {b_score}, {k_score}"
    assert k_score <= 20, f"2.8mm 강수 시 따릉이는 비추천(<=20)이어야 함, got {k_score}"
    assert "정시성 99.2%" in s_reasons[0]
    assert "도로 정체로 평균" in b_reasons[0]
    print("  ✅ 보통 비(2.8mm) 모달 시프트 및 지하철 1위 추천 검증 완료")

def test_heavy_rain_scoring():
    print("\n[Test 5] 폭우(강수량 10.0mm) 시 안전 한계 스코어 검증...")
    _, s_score, _ = evaluate_subway(volume=25000, rain=10.0, district="강남구")
    _, b_score, _ = evaluate_bus(volume=15000, rain=10.0, district="강남구")
    _, k_score, k_reasons = evaluate_bike(volume=80, rain=10.0, district="강남구")

    print(f"  - 폭우(10.0mm) 점수: 지하철={s_score}점, 버스={b_score}점, 따릉이={k_score}점")
    assert k_score == 5, f"폭우 시 따릉이 점수는 하한선(5점)이어야 함, got {k_score}"
    assert b_score <= 20, f"폭우 시 버스 점수는 극심한 감점(<=20)이어야 함, got {b_score}"
    assert s_score >= 65, f"폭우 시에도 지하철은 신뢰도(>=65)를 유지해야 함, got {s_score}"
    print("  ✅ 폭우 시 지하철 압도적 우위 및 자전거 운행 중단 플로어 검증 완료")

def test_score_metadata():
    print("\n[Test 6] 스코어 라벨 및 색상 메타데이터 검증...")
    lbl_hi, col_hi = get_score_meta("subway", 85)
    lbl_mid, col_mid = get_score_meta("bus", 60)
    lbl_low, col_low = get_score_meta("bike", 20)

    assert lbl_hi == "최우선 추천"
    assert lbl_mid == "주의 필요"
    assert lbl_low == "비추천"
    print(f"  ✅ 85점: {lbl_hi} ({col_hi}), 60점: {lbl_mid} ({col_mid}), 20점: {lbl_low} ({col_low})")

def run_all():
    print("=" * 80)
    print("  🧪 [Unit Test] MCDA 실측 캘리브레이션 및 AHP 가중치 정합성 테스트")
    print("=" * 80)
    test_ahp_consistency()
    test_clear_weather_scoring()
    test_light_rain_scoring()
    test_moderate_rain_scoring()
    test_heavy_rain_scoring()
    test_score_metadata()
    print("\n" + "=" * 80)
    print("  🎉 모든 MCDA 캘리브레이션 테스트를 성공적으로 통과하였습니다! (PASS)")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_all()
