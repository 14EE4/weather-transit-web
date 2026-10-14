# 📊 weather-transit-web API 구조 문서

> 본 문서는 `weather-transit-web` 프로젝트의 백엔드(FastAPI) 및 프론트엔드(React) API 구조를 정리한 문서입니다.

---

## 1. 전체 아키텍처 개요

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  Frontend (React + Vite)     │        │  Backend (FastAPI, main.py)       │
│  MapLibre GL 지도 대시보드    │  HTTP  │  - 3개 ONNX 모델 추론             │
│  App.tsx / TransitMap.tsx    │ ─────▶ │  - 공공 API 중계 + 서킷브레이커     │
│  PORT 3100 (Nginx) / 8443(dev)│  /api  │  PORT 8100 (호스트) / 8000 (컨테이너)│
└─────────────────────────────┘        └──────────────┬───────────────────┘
                                                       │ httpx (async)
                     ┌─────────────────────────────────┼──────────────────────────────┐
                     ▼                                 ▼                              ▼
             기상청 API허브                     서울 열린데이터광장               공공데이터포털
        (getUltraSrtNcst 초단기실황)      (realtimeStationArrival)      (서울 버스도착정보)
```

- **백엔드**: `main.py` (단일 파일, 1960줄, FastAPI)
  - `timeseries_cache.py` (시계열 래그/기상 차분 인메모리 캐시)
  - `feature_schema.py` (피처 스키마 SSoT 로더·검증 — 기동 시 차원·순서 assert)
  - `models/*.onnx` (따릉이/버스/지하철 수요예측 모델 3종, 기동 시 메모리 로딩)
- **프론트엔드**: `Weather-Transport Recommendation UI/src/` (App.tsx, TransitMap.tsx가 `fetch`로 직접 호출)
- **리버스 프록시**: `nginx.conf` → 프론트 컨테이너가 `/api/` 와 `/health` 를 백엔드(`backend:8000`)로 프록시 (CORS 원천 해소)

---

## 2. 백엔드 API 엔드포인트 (총 10개)

`main.py`는 `APIRouter` 없이 `@app.get/post` 로 단일 `FastAPI` 앱에 정의되어 있습니다.

| # | 메서드 | 경로 | 태그 | 설명 |
|---|--------|------|------|------|
| 1 | GET | `/health` | System | 헬스체크, 모델 로딩 상태, 서킷브레이커 상태 |
| 2 | GET | `/api/v1/system/circuit-breakers` | System | 서킷브레이커 상세 메트릭 + 스냅샷 캐시 현황 |
| 3 | GET | `/api/v1/cache/timeseries-status` | System | 시계열 캐시 진단 (`?district=` 옵션) |
| 4 | POST | `/api/v1/predict/recommendation` | Inference | **핵심** — 32차원 피처 → 3모델 추론 → MCDA 추천 |
| 5 | POST | `/api/v1/simulate/weather-impact` | Simulation | What-If 기상 시뮬레이터 (모달 시프트 + 25개구 혼잡도) |
| 6 | GET | `/api/v1/districts/live-congestion` | Inference | 8대 거점/25개구 실시간 혼잡도 (30초 캐시) |
| 7 | GET | `/api/v1/transit/hourly-forecast` | Inference | 24시간 시계열 수요/혼잡도 예측 (60초 캐시) |
| 8 | GET | `/api/v1/weather/current` | Live Public APIs | 기상청 초단기실황 실시간 관측 |
| 9 | GET | `/api/v1/transit/subway/arrival` | Live Public APIs | 서울시 지하철 실시간 도착 (15초 캐시) |
| 10 | GET | `/api/v1/transit/bus/arrival` | Live Public APIs | 서울시 버스 실시간 도착 (15초 캐시) |

---

## 3. 각 엔드포인트 상세

### 🔹 시스템/진단 (System)

**GET `/health`** — 파라미터 없음
```json
{ "status": "ok", "models_loaded": true,
  "feature_schema": { "path": "benchmarks/2026-10-14/feature_schema.json", "status": "verified",
                      "model_version": "v2-전처리_2-32d", "feature_dim": 32,
                      "model_input_dims": { "bike": 32, "bus": 32, "subway": 32 } },
  "circuit_breakers": { "kma_weather":"CLOSED","seoul_subway":"CLOSED","seoul_bus":"CLOSED" },
  "available_districts": ["강남구", "..."], "timestamp": "..." }
```

- `feature_schema` 는 **기동 시 피처 스키마(SSoT) 검증 결과**입니다(`feature_schema.py` → `main.py::ModelRegistry`).
  - `status`: **`verified`(현행 배포 상태 — 모델 입력 차원 = 스키마 차원, 2026-10-14 32차원 교체)** / `legacy-subset-25d`(25차원 레거시 자산을 배포 슬롯에 반입한 경우) / `mixed-32d/25d`(수단별 혼합) / `not-found`(스키마 미발견 → 검증 생략)
  - 스키마 순서가 코드(`main.py::FEATURE_ORDER_32`)와 다르면 **서버가 기동하지 않습니다**(조용한 예측 붕괴 방지).
  - 경로 재정의: `FEATURE_SCHEMA_PATH` 환경변수(미지정 시 `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json` 자동 탐색).

**GET `/api/v1/system/circuit-breakers`** — 3개 서킷브레이커의 상태/실패횟수/쿨다운 잔여시간/누적성공·폴백 + 스냅샷 캐시 개수 반환

**GET `/api/v1/cache/timeseries-status?district=마포구`** — `district` 지정 시 해당 구의 11차원 시계열 피처(`*_lag_1h`, `*_roll_mean_3h`, `temp_diff_1h` 등) 즉시 반환

### 🔹 추론 (Inference)

**POST `/api/v1/predict/recommendation`** — 응답모델 `PredictionResponse`

요청 `PredictionRequest`:
```json
{ "district": "강남구", "hour": 8,
  "weather": { "temp":14.0, "rain":0.0, "humidity":60.0, "wind":2.0 },
  "station": "강남역", "stop_type": "subway", "base_crowd": 88 }
```
동작: `build_feature_vector()`로 **32차원** 조립 → 3개 ONNX 세션 병렬 추론 → `evaluate_subway/bus/bike()` MCDA 스코어 산출 → 점수 내림차순 정렬. `station`+`base_crowd` 전달 시 `calculate_station_crowd()`로 역 고유 혼잡도로 보정.

응답:
```json
{ "status":"success", "timestamp":"...", "district":"강남구", "station":"강남역",
  "corridor_district":"...", "latency_ms": 3.2,
  "weather_summary": { "condition":"...", "description":"..." },
  "recommendations": [
    { "id":"subway","icon":"🚇","name":"지하철","score":91,"scoreLabel":"최우선 추천",
      "scoreColor":"#38BDF8","reasons":["..."],"estimated_time_min":35,"fare_krw":1400,
      "crowd":72,"crowdLabel":"...","crowdColor":"...",
      "predicted_volume":7920,"predicted_demand":7920 } ]
}
```

**GET `/api/v1/districts/live-congestion?rain=&temp=&hour=&include_all=`** — 쿼리 4개 모두 Optional. `HOTSPOT_DEFINITIONS`(강남역삼동/명동/여의도 등 8곳) 배치 추론, `include_all=true`면 25개구 전체 추가. 30초 캐시.

**GET `/api/v1/transit/hourly-forecast?district=강남구&rain=&temp=`** — 0~23시 반복 추론. 일교차 곡선(`sin`) + 출퇴근 피크 반영. 60초 캐시.

> ⚠️ 위 두 엔드포인트(4·6·7)와 시뮬레이션은 `registry.is_loaded`가 False면 **503** 반환.

### 🔹 시뮬레이션 (Simulation)

**POST `/api/v1/simulate/weather-impact`** — `SimulationRequest { simulated_rain_mm, simulated_temp, hour }`
- 강수/맑음 2개 시나리오를 강남구 기준 추론 후 모달 시프트율(따릉이→지하철/버스 전이) 계산
- 25개 자치구별 혼잡도(`district_congestion`) 일괄 산출

### 🔹 실시간 공공 API 중계 (Live Public APIs)

**GET `/api/v1/weather/current?district=강남구&lat=&lng=&station=`** — 응답모델 `RealtimeWeatherResponse`
- `resolve_weather_target()`이 위경도→기상청 격자(nx,ny) 변환, 미지정 시 `DISTRICT_KMA_GRID` 사용
- 매시 10분 이전 호출 시 **직전 정각 시간대로 자동 보정**
- 10분 캐시 + 서킷브레이커 + Last-Known-Good + 계절/시간대 지능형 폴백 (`source` 필드: `KMA_APIHUB_LIVE` / `KMA_CACHED_STALE` / `KMA_CIRCUIT_OPEN_STALE` / `KMA_FALLBACK` 등)
- 응답: `temp, rain, pty, pty_desc, humidity, wind, nx, ny, base_date, base_time, source`

**GET `/api/v1/transit/subway/arrival?station=강남`** — 응답모델 `SubwayArrivalResponse`
- 역명 끝 "역" 제거 후 조회, 서울역은 `["서울","서울역"]` 병렬 조회, `subwayId → 호선명` 매핑
- 15초 캐시 + 서킷브레이커 + 폴백. 응답: `station, clean_station, arrivals[{line, destination, message, remaining_seconds, remaining_minutes, train_status, updn_line}], source`

**GET `/api/v1/transit/bus/arrival?stId=111000299&busRouteId=`** — 응답모델 `BusArrivalResponse`
- `busRouteId` 있으면 `getArrInfoByRouteAll`, 없으면 `getLowArrInfoByStId` 엔드포인트 사용
- 인증키 **이중 인코딩 방지**(`urllib.parse.unquote`) 처리, 15초 캐시 + 서킷브레이커 + 폴백

---

## 4. 복원력(Resilience) 계층 — 공통 설계 패턴

모든 Live API(8~10번)가 동일한 4단계 패턴을 공유합니다:

```
① 인메모리 TTL 캐시  →  ② 서킷브레이커 OPEN 체크(즉시 스냅샷/폴백)
   →  ③ 외부 API 호출(httpx, timeout 4s)  →  ④ 실패 시 Last-Known-Good → 지능형 폴백
```

- **서킷브레이커**: `CircuitBreaker` 클래스 (CLOSED→OPEN→HALF_OPEN), 임계 3회 실패, 쿨다운 30~45초
  - `kma_circuit_breaker`(45s) / `subway_circuit_breaker`(30s) / `bus_circuit_breaker`(30s)
- **캐시 딕셔너리**: `_weather_cache`, `_subway_cache`, `_bus_cache` + `_*_last_good` 스냅샷
- **지능형 폴백**: `generate_intelligent_weather_fallback`(계절·시간대 기반), `generate_intelligent_subway_fallback`, `generate_intelligent_bus_fallback`
- **`source` 필드**로 데이터 출처(LIVE/STALE/FALLBACK)를 항상 노출 → 프론트에서 신뢰도 판별 가능

---

## 5. 핵심 데이터 모델 (Pydantic)

| 모델 | 용도 |
|------|------|
| `WeatherInput` | 기상 입력 (temp, rain, humidity, wind) |
| `PredictionRequest` / `RecommendationItem` / `PredictionResponse` | 추천 API |
| `SimulationRequest` / `ModalShiftSummary` / `DistrictCongestionItem` / `SimulationResponse` | 시뮬레이션 |
| `RealtimeWeatherResponse` | 날씨 |
| `SubwayArrivalItem`/`SubwayArrivalResponse` | 지하철 |
| `BusArrivalItem`/`BusArrivalResponse` | 버스 |
| `DistrictLiveCongestionItem`/`LiveDistrictCongestionResponse` | 실시간 혼잡도 |
| `HourlyForecastItem`/`HourlyForecastResponse` | 시간대별 예측 |

**핵심 헬퍼**: `build_feature_vector()` (32차원), `prepare_session_input()`, `evaluate_subway/bus/bike()` (MCDA), `get_score_meta()` / `get_crowd_label/color()`, `calculate_station_crowd()`, `normalize_district_name()`, `resolve_weather_target()`

---

## 6. 프론트엔드 API 소비 구조

- **Base URL 결정** (`App.tsx:441`, `TransitMap.tsx:10`의 `getApiBaseUrl`): `import.meta.env.VITE_API_BASE_URL` → 없으면 현재 호스트의 `:8100` → 최종 폴백 `http://localhost:8100`
- **호출 방식**: 별도 axios/API 레이어 없이 컴포넌트에서 `fetch(`${API_BASE_URL}/api/v1/...`)` 직접 호출
- **로깅**: `src/apiLogger.ts`의 `logWeatherApiCall` / `logBusApiCall` / `logSubwayApiCall` / `logAIPredictionCall` — 중복 방지 키 기반으로 F12 콘솔에 진본 페이로드 출력
- **정적 참조 포트 주의**: `App.tsx`는 버스 도착에 `stId=111000299`(구산동사거리), `TransitMap.tsx:1208`은 클릭한 정류소의 `targetStId`를 사용하는 등 하드코딩된 값이 일부 존재

---

## 7. 환경 변수 & 포트

| 변수 | 용도 |
|------|------|
| `KMA_APIHUB_KEY` | 기상청 API허브 (초단기실황) |
| `SEOUL_SUBWAY_API_KEY` | 서울 열린데이터광장 (지하철 도착) |
| `DATA_GO_KR_API_KEY` | 공공데이터포털 (버스 도착) |
| `VITE_API_BASE_URL` | 프론트가 참조하는 백엔드 URL |

| 포트 | 컨텍스트 |
|------|----------|
| `8000` | 백엔드 컨테이너 내부 (`main.py` uvicorn 기본) |
| `8100` | 백엔드 호스트 노출 (`docker-compose` `${BACKEND_PORT:-8100}`), 프론트 기본 base |
| `3100` | 프론트 Nginx (`${FRONTEND_PORT:-3100}`) |
| `8443` | Vite 개발 서버 (`vite.config.ts` `PORT` 기본값) |

---

## 8. ⚠️ 주의사항 (문서 간 불일치)

- **README/`.env.example`** 은 `VITE_API_BASE_URL=http://localhost:8000` 로 안내하지만, 실제 **프론트 코드는 8100을 기본값**으로 사용 → 문서와 런타임 기본 포트 불일치
- `APIRouter`로 모듈화되지 않고 `main.py` **단일 파일에 전 엔드포인트 집중** (테스트는 `tests/`에서 `TestClient(app)`로 통합 검증)
- CORS는 `allow_origins=["*"]` + `allow_credentials=True` 조합(프로덕션에선 Nginx 프록시로 우회)