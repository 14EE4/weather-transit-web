import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

def test_station_weather_ai_pipeline():
    with TestClient(app) as client:
        stations = [
            ("강남", 37.4979, 127.0276, "강남구"),
            ("홍대입구", 37.5575, 126.9245, "마포구"),
            ("잠실", 37.5133, 127.1001, "송파구"),
            ("서울역", 37.5562, 126.9723, "중구"),
        ]
        for name, lat, lng, dist in stations:
            # 1. Weather
            w_res = client.get(f"/api/v1/weather/current?district={dist}&lat={lat}&lng={lng}&station={name}")
            assert w_res.status_code == 200, f"Weather failed for {name}"
            w = w_res.json()
            
            # 2. AI Inference
            ai_payload = {
                "district": dist,
                "hour": 9,
                "weather": {
                    "temp": w["temp"],
                    "rain": w["rain"],
                    "humidity": w["humidity"],
                    "wind": w["wind"]
                }
            }
            ai_res = client.post("/api/v1/predict/recommendation", json=ai_payload)
            assert ai_res.status_code == 200, f"AI prediction failed for {name}"
            ai = ai_res.json()
            sub_rec = next(r for r in ai["recommendations"] if r["id"] == "subway")

            # 3. Train arrivals
            arr_res = client.get(f"/api/v1/transit/subway/arrival?station={name}")
            assert arr_res.status_code == 200, f"Arrival failed for {name}"
            arr = arr_res.json()

            print(f"=== {name}역 ({dist}) ===")
            print(f"  [KMA LCC 격자]: ({w['nx']}, {w['ny']}) | 기온: {w['temp']}°C, 강수: {w['rain']}mm, 습도: {w['humidity']}%, 풍속: {w['wind']}m/s")
            print(f"  [AI ONNX 추론]: 지하철 혼잡도 {sub_rec['crowd']}%, 예측 승객수 {sub_rec['predicted_volume']:,}명, 점수 {sub_rec['score']}점, 레이턴시 {ai['latency_ms']}ms")
            print(f"  [실시간 열차]: 도착 열차 {len(arr.get('arrivals', []))}대 수신")

        print("\n>>> All Station Weather -> AI Inference -> Train Arrival Pipelines Verified Successfully!")

if __name__ == "__main__":
    test_station_weather_ai_pipeline()
