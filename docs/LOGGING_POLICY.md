# 📜 전역 로깅 정책 및 정형화 가이드 (`LOGGING_POLICY.md`)

> **상위 프로젝트**: [Weather & Transit Web](../README.md)  
> **시스템 아키텍처**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)  
> **백엔드 명세**: [BACKEND_INFERENCE_SERVER.md](./BACKEND_INFERENCE_SERVER.md)  
> **최근 변경일**: 2026-10-29

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

