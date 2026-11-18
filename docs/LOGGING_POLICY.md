# 📜 전역 로깅 정책 및 정형화 가이드 (`LOGGING_POLICY.md`)

> **상위 프로젝트**: [Weather & Transit Web](../README.md)  
> **시스템 아키텍처**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)  
> **백엔드 명세**: [BACKEND_INFERENCE_SERVER.md](./BACKEND_INFERENCE_SERVER.md)  
> **최근 변경일**: 2026-11-18

---

## 1. 개요 및 설계 철학

Weather & Transit Web은 실시간 기상청 관측, 대중교통(지하철, 버스, 따릉이) 공공 API, 32차원 ONNX 머신러닝 엔진, LangGraph 멀티모달 경로 탐색 등 복합적인 비동기 파이프라인으로 구동됩니다.

본 문서는 서비스 운영 중 발생하는 모든 관측치, API 연동 상태, 머신러닝 추론 결과 및 시스템 예외를 **체계적이고 정형화된 규격으로 기록하고 관제하기 위한 공식 로깅 정책**을 정의합니다.

### 🎯 핵심 3대 원칙
1. **정형화 (Structured Schema)**: 모든 로그는 비정형 텍스트 대신 표준화된 메타데이터(타임스탬프, 서비스 태그, 요청 파라미터, 응답 메트릭, 처리시간)를 포함해야 합니다.
2. **이원화 관제 (Dual Observability)**:
   - **백엔드**: `/health/dashboard` 관제 UI 및 SSE 실시간 스트림 (인메모리 링 버퍼 기반)
   - **프론트엔드**: 브라우저 개발자 도구 콘솔(F12)의 정형화된 도메인 배지 및 실측 데이터 Dump
3. **경량화 및 보안 (Efficiency & Security)**:
   - 메모리 누수 방지를 위한 고정 크기 링 버퍼(`maxlen=500`) 및 300ms 이내 중복 로그 단일화
   - 공공 API 개인키(`serviceKey`, `BUS_API_KEY`) 마스킹 처리

---

## 2. 표준 통합 로그 스키마 (Unified Log Schema)

백엔드와 프론트엔드 모두 아래의 표준 필드 규격을 준수합니다:

| 필드명 | 타입 | 필수 여부 | 설명 | 예시 |
| :--- | :--- | :---: | :--- | :--- |
| `timestamp` | string | 필수 | ISO 8601 UTC 타임스탬프 | `"2026-10-29T13:50:00.123Z"` |
| `level` | string | 필수 | 로그 레벨 (`DEBUG`, `INFO`, `WARN`, `ERROR`) | `"INFO"` |
| `service` | string | 필수 | 발생 도메인 (`KMA`, `BUS`, `SUBWAY`, `ONNX`, `LANGGRAPH`, `SYSTEM`) | `"ONNX"` |
| `action` | string | 필수 | 수행 작업 식별자 | `"infer_district_congestion"` |
| `params` | object | 선택 | 요청 입력 파라미터 | `{"district": "강남구", "hour": 22}` |
| `metrics` | object | 선택 | 수치형 결과 및 추론 지표 | `{"subway_crowd": 52, "bus_crowd": 48}` |
| `status` | string | 필수 | 성공/실패 상태 (`SUCCESS`, `FALLBACK`, `ERROR`) | `"SUCCESS"` |
| `duration_ms`| number | 선택 | 소요 시간(ms) | `14.2` |
| `message` | string | 필수 | 사람이 읽을 수 있는 요약 텍스트 | `"강남구 거점 혼잡도 32차원 추론 완료"` |

---

## 3. 백엔드 개발자 대시보드 로깅 정책 (`in_memory_log_handler.py`)

### 3.1 인메모리 링 버퍼 구조
- **저장소**: `collections.deque(maxlen=500)` 구조로 최근 500건의 로그를 메모리에 유지.
- **스트리밍**: `/health/dashboard` 관제 UI에서 Server-Sent Events(SSE) 또는 폴링 방식으로 실시간 렌더링.
- **포맷팅**: 레벨별 터미널 색상 및 HTML CSS 뱃지 적용.

```python
{
    "timestamp": "2026-10-29T13:55:00.000Z",
    "level": "INFO",
    "service": "ONNX",
    "action": "predict_hourly_transit",
    "message": "[AI 머신러닝 엔진] 인천시 24시간 시계열 이용 수요 추론 완료",
    "details": {
        "district": "인천시",
        "feature_dim": 32,
        "peak_hour": 18,
        "model_version": "v2.1-multiyear-32d"
    }
}
```

### 3.2 중복 수집 방지 규칙 (Deduplication)
- 외부 API 폴링이나 React StrictMode에 의해 300ms 이내에 완전히 동일한 `(logger, level, message)` 시그니처가 유입될 경우, 링 버퍼에 중복 기록하지 않고 단일 이벤트로 합산 처리합니다.

---

## 4. 프론트엔드 브라우저 콘솔 로깅 정책 (`apiLogger.ts`)

### 4.1 도메인별 표준 배지 및 이모지 컨벤션

브라우저 F12 개발자 도구 콘솔에서 가독성을 극대화하기 위해 다음과 같은 CSS 스타일 배지와 이모지를 사용합니다:

| 도메인 | 이모지 | 콘솔 배지 텍스트 | 배지 배경색 | 주요 출력 페이로드 |
| :--- | :---: | :--- | :--- | :--- |
| **기상청** | 🌦️ | `[기상청 API허브]` | `#0284c7` (Sky Blue) | 관측 격자(`nx`, `ny`), 기온, 강수량, 발표시각 |
| **버스** | 🚌 | `[서울시 버스 OpenAPI]` | `#f59e0b` (Amber) | 정류소 ID, 노선명, 저상버스 잔여분/남은 정류소 |
| **지하철** | 🚇 | `[서울교통공사 지하철]` | `#10b981` (Emerald) | 지하철역명, 호선, 열차 도착 잔여시간, 방면 |
| **AI 모델** | ⚡ | `[AI 머신러닝 엔진]` | `#8b5cf6` (Purple) | 자치구, 기준 시각, 32차원 ONNX 수치(지하철·버스·따릉이) |
| **시계열 AI** | 📈 | `[24시간 시계열 AI]` | `#6366f1` (Indigo) | 24시간 전체 수단별 이용객 및 기상 추론 배열 |
| **경로 탐색** | 🚀 | `[LangGraph × FactChat]` | `#ec4899` (Pink) | 출발역 ➔ 도착역, 날씨 조건, 최적 추천 점수 및 요금 |

### 4.2 중복 출력 방지 윈도우
- `apiLogger.ts` 내부의 `dedupWindowMs`를 `300ms`로 설정하여, 컴포넌트 리렌더링으로 인한 동일 API 로깅 2회 중복 출력을 방지합니다.

---

## 5. 도메인별 데이터 계약 (Data Contracts)

### 5.1 기상 관측 로그 (`KMA`)
```typescript
interface WeatherLogPayload {
  district: string;
  grid: { nx: number; ny: number };
  temp: number;
  rain: number;
  humidity: number;
  wind_speed: number;
  base_time: string;
  source: 'kma_live_api' | 'fallback_cache';
}
```

### 5.2 32차원 ONNX 추론 로그 (`ONNX`)
```typescript
interface DistrictCongestionLogPayload {
  district: string;
  hour: number;
  weather_summary: { temp: number; rain: number; pty: number };
  hubs: Array<{
    name: string;
    subway_score: number;
    bus_score: number;
    bike_score: number;
    dominant_mode: string;
    level: '쾌적' | '보통' | '혼잡' | '매우 혼잡';
  }>;
  feature_dim: 32;
  model_version: 'v2.1-multiyear-32d';
}
```

### 5.3 LangGraph 멀티모달 경로 탐색 로그 (`LANGGRAPH`)
```typescript
interface MultimodalRouteLogPayload {
  from_station: string;
  to_station: string;
  hour: number;
  weather: { temp: number; rain: number };
  best_mode: string;
  estimated_minutes: number;
  transfer_count: number;
  fare_krw: number;
  segments: Array<{ mode: string; from: string; to: string; minutes: number }>;
}
```

---

## 6. 로그 레벨 규정

1. **`INFO`**:
   - 실시간 외부 API 패치 정상 완료 (`200 OK`)
   - 32차원 ONNX 배치 추론 정상 완료 (`latency < 50ms`)
   - LangGraph 멀티모달 최적 경로 도출 완료
2. **`WARN`**:
   - 외부 공공 API 일시 지연 또는 결측치로 인해 Fallback 데이터로 전환된 경우
   - 서킷 브레이커 카운트 증가 (`failure_count >= 1`)
3. **`ERROR`**:
   - 서킷 브레이커 `OPEN` (요청 즉시 차단)
   - 공공데이터포털 API 인증 키 오류 또는 400/500 응답
   - MapLibre WebGL 셰이더 렌더링 런타임 오류

---

## 7. 보안 및 민감정보 보호

- API 키(`BUS_API_KEY`, `KMA_API_KEY`)는 쿼리스트링이나 로그 본문에 절대 원문 그대로 평문 노출하지 않으며, 앞 4자리 외에는 `****` 마스킹 처리합니다.
- 사용자 IP 주소 및 위치 좌표는 개인정보 보호를 위해 소수점 4자리 이하로 난수화하거나 자치구 단위로만 수집합니다.

---

## 8. 도메인별 주요 경고(`WARNING`) 및 폴백(Fallback) 로그 트러블슈팅 가이드

서버 콘솔과 관리자 대시보드(`/health/dashboard`) 로그 창에는 간결한 `1`줄 식별자를 유지하고(빈 예외 문자열 방지를 위해 `sanitize_exception()`으로 `ReadTimeout` 등 예외 클래스명을 보강), 각 경고 로그의 상세 원인 및 서버 무중단 동작 원리는 아래 기준표로 확인합니다.

### 8.1 한눈에 보는 경고 로그 요약표

| 도메인 배지 | 로그 메시지 패턴 | 발생 원인 | 서버 자동 조치 (Graceful Fallback) | 운영 점검 포인트 |
| :--- | :--- | :--- | :--- | :--- |
| `[기상청]` | `KMA Grid [VAR] YYYYMMDDHH error: ReadTimeout (기존 예보 폴백)` | 30분 주기 단기예보 격자 갱신 시 동시 다발 요청 중 일부가 `8.0초` 타임아웃 초과 | 성공한 시간대 격자는 실측 반영, 타임아웃된 특정 시간대·변수만 보간값(`generate_fallback_24h`)으로 대체 | `KMA 단기예보 24시간 캐시 갱신 완료` 로그가 이어지면 서비스 정상 (별도 조치 불필요) |
| `[기상청]` | `KMA API call failed: ..., activating circuit breaker & fallback.` | 기상청 초단기실황 API(`getRealtimeWeather`) 응답 지연 또는 HTTP 오류 | 직전 정상 스냅샷(`_weather_last_good`) 또는 지능형 기상 폴백 반환 | `KMA_APIHUB_KEY` 유효성 및 기상청 API허브 서버 상태 확인 |
| `[버스]` | `Seoul Bus API error: ... (스냅샷/배차 폴백)` | 공공데이터포털(`ws.bus.go.kr`) 도착정보 API `4.0초` 타임아웃 또는 네트워크 오류 | 직전 정상 스냅샷(`_bus_last_good`) 또는 노선 배차간격 폴백 반환 | 일시적 지연은 자동 복구. 반복 시 공공데이터포털 점검 여부 확인 |
| `[버스]` | `[서울 버스] Nearby bus station API 연결 실패/타임아웃 (...) -> 200 빈 목록 Fallback` | 지도 주변 정류소 조회(`getStationByPos`) `4.0초` 타임아웃 또는 서버 502/503 | 브라우저 502 에러 폭주 차단을 위해 `HTTP 200` 빈 목록(`stations: []`) 반환 | 지도 정적 마스터 정류소 레이어는 정상 표출됨 |
| `[버스]` | `getStationByPos API 헤더 오류` / `서울시 버스 노선·위치·도착 API 오류` (`headerCd != "0"`) | `DATA_GO_KR_API_KEY`의 **서울시 버스 OpenAPI 5종 활용신청 누락**, 인증키 오설정 또는 일일 트래픽 한도 초과 | 빈 목록 폴백 반환 또는 해당 버스 상세 API `502` 응답 | 공공데이터포털 마이페이지에서 5종 API(정류소·노선·위치·도착·환승) 승인 상태 및 트래픽 확인 |
| `[버스]` | `[버스 검색] getStationByName 안내 응답 (4: ...)` | API 장애가 아니라 검색 결과 `0건` 또는 심야 운행 종료 상태 (`headerCd` `"4"`, `"7"`) | 정상 `HTTP 200` 빈 목록(`count: 0`) 반환 | 정상 동작 (검색어 철자 확인) |
| `[LangGraph]` | `[FactChat] LLM Gateway 응답 본문이 비어 있어 XAI 규칙 엔진으로 Fallback합니다.` | 추론형 LLM(`gpt-6-luna`)이 `max_tokens` 한도(과거 `240`, 현행 `700`으로 상향)를 내부 추론(Thinking)에 소진해 빈 본문(`content=""`) 반환 | 내장 **LangGraph XAI 규칙 엔진**으로 `0ms` 전환하여 한국어 브리핑 정상 생성 | 사용자 화면 브리핑은 정상 표출 (`fallback_reason="EMPTY_LLM_RESPONSE"`) |
| `[LangGraph]` | `fetch_public_transit_transfer_routes error: ... (다익스트라 폴백)` | 대중교통 환승경로 API(`getPathInfoByBusNSub`, `timeout=2.5s`) 지연 또는 오류 | 자체 다익스트라 지하철+버스 복합 탐색 엔진으로 무중단 경로 생성 | 자체 라우팅으로 정상 동작 |
| `[지하철]` / `[따릉이]` | `Seoul Subway API error: ... (배차 폴백)` / `Seoul bike API error: ... (스냅샷 폴백)` | 서울 열린데이터광장(`swopenAPI`, `openapi.seoul.go.kr:8088`) 응답 지연·오류 | 직전 정상 스냅샷 또는 시간대 표준 배차간격·마스터 대여소 DB로 대체 | `SEOUL_SUBWAY_API_KEY` / `SEOUL_BIKE_API_KEY` 만료 여부 확인 |
| `[서킷브레이커]` | `[CircuitBreaker:NAME] 연속 실패 3회 발생! 서킷을 OPEN 상태로 차단합니다` | 동일 외부 API가 연속 `3`회(`failure_threshold=3`) 실패 | 쿨다운(`30초` 또는 KMA `45초`) 동안 외부 호출 차단 후 스냅샷/폴백 즉시 응답 | 쿨다운 후 `HALF_OPEN` 프로빙 성공 시 `CLOSED`로 자동 복귀 |

---

### 8.2 기상청 API (`[기상청]`) 에러 로그 상세 해설

1. **`KMA Grid [PCP/TMP/PTY/SKY] YYYYMMDDHH error: ReadTimeout (기존 예보 폴백)`**
   - **발생 구조 (`kma_forecast.py`)**: 백엔드는 `30분`마다 `refresh_forecast_cache()`를 실행해 당일 남은 시간대(`now.hour`부터 최대 `14`개 시간대) × `4`개 기상 변수(`TMP` 기온, `PCP` 강수량, `SKY` 하늘상태, `PTY` 강수형태) = **최대 약 `20~56`개 격자 요청**을 `asyncio.gather`로 동시 전송합니다. 각 요청은 한반도 `149×253` = `37,697`개 격자점 데이터를 `timeout=8.0초` 안에 내려받습니다.
   - **원인**: 기상청 API허브 서버 응답이 일시적으로 `8초`를 초과하면 `httpx.ReadTimeout` 예외가 발생합니다. (`httpx.ReadTimeout`은 기본 예외 문자열 `str(e)`가 `""`이므로 `sanitize_exception()`이 예외 클래스명 `ReadTimeout`을 보강합니다.)
   - **서비스 영향**: **무중단 부분 보간**. 같은 사이클에서 성공한 시간대·변수의 실측 격자 데이터는 정상 반영되며, 타임아웃이 난 일부 시간대·변수만 보간값(`generate_fallback_24h`)으로 채워져 `34`개 권역 예보 캐시는 정상 완료됩니다.

---

### 8.3 서울시 버스 OpenAPI (`[버스]`) 장애 진단 상세 해설

버스 기능이 동작하지 않거나 경고가 뜰 때는 아래 `4가지` 원인으로 구분됩니다.

1. **공공데이터 서버 일시 지연/타임아웃 (`ReadTimeout`, `ConnectTimeout`)**:
   - `getLowArrInfoByStId`(도착정보 `4.0초`), `getStationByPos`(주변 정류소 `4.0초`), `getStationByName`(정류소 검색 `6.0초`), `getStaionByRoute`/`getBusPosByRtid`(`10.0초`)에서 응답 지연 시 발생.
   - 도착정보·주변 정류소는 `502` 대신 직전 스냅샷·배차 폴백 또는 `HTTP 200` 빈 목록으로 전환하여 지도·앱 UI 마비를 방지합니다.
2. **공공데이터포털 서울시 버스 OpenAPI 5종 활용신청 일부 누락 (`headerCd != "0"`)**:
   - 본 서비스는 ① 정류소정보(`stationinfo`), ② 노선정보(`busRouteInfo`), ③ 버스위치(`buspos`), ④ 버스도착(`arrive`), ⑤ 대중교통환승경로(`pathinfo`) **5종 API 모두** 활용승인이 필요합니다.
   - 검색이나 주변 정류소는 되는데 특정 노선선·실시간 버스 위치가 실패한다면 **노선/버스위치 API 활용신청 누락**이 주원인입니다.
3. **정상 0건/운행 종료 (`headerCd` `"4"`, `"7"`)**:
   - `getStationByName` 또는 도착정보 호출 시 심야 운행 종료나 일치 정류소가 없는 경우 공공데이터가 코드 `"4"`(`결과가 없습니다`)·`"7"`을 반환하며, 장애가 아닌 정상 안내입니다.
4. **인증키 미설정 및 일일 트래픽 한도 초과**:
   - `DATA_GO_KR_API_KEY`가 미설정된 경우 `DATA_GO_KR_BUS_KEY 미설정` 또는 `NO_BUS_API_KEY`가 기록되며, 개발계정 일일 트래픽(보통 `1,000건` 내외) 초과 시에는 다음 날 자정 초기화 또는 운영계정 승인이 필요합니다.

---

### 8.4 FactChat LLM 빈 응답 (`[LangGraph]`) 상세 해설

- **`[FactChat] LLM Gateway 응답 본문이 비어 있어 XAI 규칙 엔진으로 Fallback합니다.`**
  - 경로 탐색 `4단계`(`_node_factchat_llm_briefing`)에서 외부 BAZE/FactChat LLM(`gpt-6-luna`) 호출 시 `HTTP 200` 응답은 왔지만 `choices[0].message.content`가 비어 있는 상태입니다.
  - 추론(Reasoning) 계열 모델은 내부 추론 토큰(`reasoning_tokens`)과 최종 출력 텍스트 토큰을 `max_tokens` 한도 안에서 함께 사용합니다. 초기 설정(`max_tokens=240`, `timeout=5.0s`)에서 간혹 내부 추론에 한도를 소진해 본문이 비어 돌아오는 현상을 완화하기 위해 현행 코드에서는 **`max_tokens=700`, `timeout=8.0s`**로 상향하여 정상 LLM 브리핑(`FACTCHAT_LLM_LIVE`) 성공률을 확보했습니다. 그럼에도 게이트웨이 정책이나 한도 초과로 빈 본문이 오면 서버는 즉시 **내장 LangGraph XAI 규칙 엔진(`LANGGRAPH_XAI_ENGINE`)**으로 `0ms` 전환해 브리핑 문장을 정상 생성합니다.


