import sys
import json
import time
from datetime import datetime

# Windows console UTF-8 reconfigure
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from main import app, build_feature_vector, WeatherInput, registry

def run_tests():
    print("=" * 80)
    print("  🚀 [Weather & Transit AI] ONNX 모델 추론 및 FastAPI 백엔드 통합 검증  ")
    print("=" * 80)

    # 1. TestClient 초기화 (lifespan 컨텍스트 트리거 -> 모델 인메모리 로딩 & 웜업)
    print("\n[Step 1] FastAPI TestClient 기동 및 ONNX 세션 인메모리 로딩 확인...")
    with TestClient(app) as client:
        # 헬스체크 확인
        health_resp = client.get("/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        health_data = health_resp.json()
        print(f"  ✅ 헬스체크 상태: {health_data['status']}")
        print(f"  ✅ 모델 로드 완료 여부: {health_data['models_loaded']}")
        print(f"  ✅ 지원 자치구 수: {len(health_data['available_districts'])}개")
        assert health_data['models_loaded'] is True, "Models not loaded in registry!"

        # 2. 32차원 피처 벡터 조립 함수(build_feature_vector) 검증
        print("\n[Step 2] 사양서 규격 32차원 Feature Vector 조립 함수 검증...")
        weather_test = WeatherInput(temp=14.0, rain=2.8, humidity=86.0, wind=3.8)
        feat_vec = build_feature_vector("강남구", 8, weather_test)
        print(f"  ✅ 생성된 Feature Vector 차원 수: {len(feat_vec)}차원 (기대값: 32)")
        assert len(feat_vec) == 32, f"Expected 32 features, got {len(feat_vec)}"
        print(f"  - [0..3] 시간 sin/cos: {feat_vec[0]:.4f}, {feat_vec[1]:.4f}, {feat_vec[2]:.4f}, {feat_vec[3]:.4f}")
        print(f"  - [4..7] 캘린더 (요일={feat_vec[4]}, 주말={feat_vec[5]}, 공휴일={feat_vec[6]}, 러시아워={feat_vec[7]})")
        print(f"  - [8..15] 기상 (기온={feat_vec[8]}°C, 풍속={feat_vec[9]}m/s, 습도={feat_vec[10]}%, 강수={feat_vec[11]}mm)")
        print(f"  - [14] 체감온도: {feat_vec[14]:.2f}°C, [15] 불쾌지수: {feat_vec[15]:.2f}")
        print(f"  - [16..20] 공간 인코딩 (구코드={feat_vec[16]}, 역수={feat_vec[17]}, 버스정류소={feat_vec[18]})")
        print(f"  - [21..23] 기본 래그(1h) (따릉이={feat_vec[21]:.1f}, 버스={feat_vec[22]:.1f}, 지하철={feat_vec[23]:.1f})")

        # 3. 시나리오 A: 맑은 날 출근 시간대 (강남구, 08시, 강수량 0.0mm)
        print("\n[Step 3] 시나리오 A: 맑은 날 출근시간 (강남구, 8시, 기온 20°C, 강수량 0.0mm)")
        payload_clear = {
            "district": "강남구",
            "hour": 8,
            "weather": {
                "temp": 20.0,
                "rain": 0.0,
                "humidity": 50.0,
                "wind": 1.8
            }
        }
        res_clear = client.post("/api/v1/predict/recommendation", json=payload_clear)
        assert res_clear.status_code == 200, f"Error: {res_clear.text}"
        data_clear = res_clear.json()
        print(f"  ⏱ 처리 지연 시간: {data_clear['latency_ms']} ms")
        print(f"  🌤 기상 요약: {data_clear['weather_summary']['condition']} - {data_clear['weather_summary']['description']}")
        print("  📊 추천 수단 랭킹:")
        for r in data_clear['recommendations']:
            print(f"    - {r['icon']} {r['name']} ({r['id']}): 점수 {r['score']}점 ({r['scoreLabel']}) | "
                  f"혼잡도 {r['crowd']}% ({r['crowdLabel']}) | 예측 수요 {r['predicted_demand']:,}건")
            print(f"      사유: {r['reasons'][0]}")

        # 4. 시나리오 B: 폭우 출근 시간대 (강남구, 08시, 강수량 12.0mm)
        print("\n[Step 4] 시나리오 B: 폭우 출근시간 (강남구, 8시, 기온 14°C, 강수량 12.0mm) - 우천 모달 시프트")
        payload_rain = {
            "district": "강남구",
            "hour": 8,
            "weather": {
                "temp": 14.0,
                "rain": 12.0,
                "humidity": 92.0,
                "wind": 4.5
            }
        }
        res_rain = client.post("/api/v1/predict/recommendation", json=payload_rain)
        assert res_rain.status_code == 200, f"Error: {res_rain.text}"
        data_rain = res_rain.json()
        print(f"  ⏱ 처리 지연 시간: {data_rain['latency_ms']} ms")
        print(f"  🌧 기상 요약: {data_rain['weather_summary']['condition']} - {data_rain['weather_summary']['description']}")
        print("  📊 폭우 시 추천 수단 랭킹:")
        bike_score_rain = 0
        subway_score_rain = 0
        for r in data_rain['recommendations']:
            print(f"    - {r['icon']} {r['name']} ({r['id']}): 점수 {r['score']}점 ({r['scoreLabel']}) | "
                  f"혼잡도 {r['crowd']}% ({r['crowdLabel']}) | 예측 수요 {r['predicted_demand']:,}건")
            for reason in r['reasons']:
                print(f"      • {reason}")
            if r['id'] == 'bike': bike_score_rain = r['score']
            if r['id'] == 'subway': subway_score_rain = r['score']

        # 우천 시 모달 시프트 검증: 따릉이는 비추천 감점, 지하철은 정시성 우대
        assert bike_score_rain <= 40, f"Bike score should be penalized during heavy rain, got {bike_score_rain}"
        assert subway_score_rain >= 65, f"Subway score should remain preferred during rain, got {subway_score_rain}"
        print(f"\n  ✅ 우천 모달 시프트 검증 완료: 지하철({subway_score_rain}점) >> 따릉이({bike_score_rain}점, 안전사고 감점 반영)")

        # 5. 시나리오 C: What-If 가상 기상 시뮬레이터 API 검증
        print("\n[Step 5] What-If 가상 시뮬레이터 API 검증 (POST /api/v1/simulate/weather-impact)...")
        payload_sim = {
            "simulated_rain_mm": 5.0,
            "simulated_temp": 12.0,
            "hour": 9
        }
        res_sim = client.post("/api/v1/simulate/weather-impact", json=payload_sim)
        assert res_sim.status_code == 200, f"Error: {res_sim.text}"
        data_sim = res_sim.json()
        shift = data_sim['modal_shift_summary']
        print(f"  ⏱ 처리 지연 시간(25개 자치구 전체 연산): {data_sim['latency_ms']} ms")
        print(f"  💬 시뮬레이션 분석: {shift['commentary']}")
        print(f"  📉 따릉이 수요 변동률: {shift['bike_demand_change_rate'] * 100:.1f}%")
        print(f"  📈 지하철 수요 변동률: {shift['subway_demand_change_rate'] * 100:.1f}%")
        print(f"  📊 25개 자치구 혼잡도 계산 샘플 (첫 3개 구):")
        for dc in data_sim['district_congestion'][:3]:
            print(f"    - {dc['district']}: 지하철 혼잡도 {dc['subway_crowd']}%, 버스 {dc['bus_crowd']}%, 따릉이 {dc['bike_crowd']}%")

        # 6. SLA Latency 성능 벤치마크 (10회 연속 호출 평균 지연시간 측정)
        print("\n[Step 6] 추론 레이턴시(SLA) 10회 연속 벤치마크 테스트...")
        latencies = []
        for i in range(10):
            t0 = time.perf_counter()
            _ = client.post("/api/v1/predict/recommendation", json=payload_clear)
            latencies.append((time.perf_counter() - t0) * 1000)

        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        print(f"  ⚡ 평균 지연시간: {avg_lat:.2f} ms (Min: {min_lat:.2f} ms, Max: {max_lat:.2f} ms)")
        print(f"  🎯 사양서 SLA 기준(15ms 이하) 충족 여부: {'충족 (PASS)' if avg_lat <= 15.0 else '초과'}")

    print("\n" + "=" * 80)
    print("  🎉 모든 검증 테스트를 성공적으로 통과하였습니다! ")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_tests()
