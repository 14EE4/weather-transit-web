# 📋 Frontend Changelog (프론트엔드 변경 이력)

> **상위 프로젝트**: [Weather & Transit Web](../../README.md)  
> **프론트엔드 가이드**: [Frontend README](../README.md)  
> **요구사항 명세서**: [REQUIREMENTS.md](../../docs/REQUIREMENTS.md)

---

## [2026-10-28]

### 🧠 LangGraph 및 FactChat LLM 기반 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 엔진 구축 (이슈 #18)
- **배경**:
  - 기존 단일 지하철 역-역 탐색을 넘어, 기상 실황/단기예보와 32차원 ONNX 수단별 혼잡도 및 실시간 따릉이 잔여 대수를 종합해 **도보 + 따릉이(First/Last-Mile) + 버스 + 지하철** 복합 경로를 오케스트레이션하는 지능형 라우팅 엔진 구축.
- **주요 조치**:
  1. **LangGraph `StateGraph` 5단계 멀티모달 라우팅 엔진 구현 (`multimodal_router.py`, `models/transit_network.json`)**:
     - `parse_context_node`: 출발/도착지 좌표 해석, 시간대별 기상청 단기예보(`kma_forecast_manager`) 및 32차원 ONNX 혼잡도 로드.
     - `weather_gate_router` (조건부 분기): 강수(`rain > 0mm`)·강풍(`>= 8m/s`)·혹한(`<= -5°C`) 시 `RAIN_SAFE_ONLY`로 분기하여 따릉이(PM) 구간을 자동 차단하고 실내 철도/버스 환승 경로로 우회.
     - `clear_multimodal_tools_node` / `rain_safe_tools_node`: 지하철 다익스트라(최소환승/최단시간), 인근 버스정류소, 실시간 따릉이 스냅샷(`_bike_snapshot_cache`) 연동.
     - `candidate_fusion_node`: `AI 멀티모달 최적(따릉이 First-Mile + 지하철)`, `지하철 최소환승`, `버스+지하철 복합 환승` 등 맞춤형 후보 경로 및 구간별(`segments`) 타임라인·운임·GeoJSON 좌표 생성.
     - `factchat_llm_briefing_node`: FactChat / BAZE 게이트웨이(`gpt-6-luna`) 연동 자연어 AI 브리핑 생성 (5분 TTL 캐시 및 XAI 폴백 내장).
  2. **백엔드 멀티모달 경로 탐색 엔드포인트 신설 (`main.py`)**:
     - `POST /api/v1/routes/multimodal-search` 및 `GET /api/v1/routes/multimodal-search` 추가.
  3. **프론트엔드 멀티모달 경로 추천 UI 및 지도 컬러 폴리라인 연동 (`MultimodalRoutePanel.tsx`, `App.tsx`, `AppM.tsx`, `TransitMap.tsx`)**:
     - `경로 추천` 페이지에 FactChat LLM 브리핑 배너, Weather Gate 상태 배지, LangGraph 노드 실행 트레이스 뷰어, 3종 멀티모달 후보 탭 및 구간별(`🚶 도보`, `🚲 따릉이`, `🚌 버스`, `🚇 지하철`) 상세 타임라인 카드 탑재.
     - `경로 추천` 페이지 좌측 날씨 현황 배지에 실시간 기상청 단기예보 연동 및 출발 시각 슬라이더(`00:00~23:00`) 추가.
     - `TransitMap.tsx`에 `multimodal-segments` GeoJSON 레이어를 추가하여 수단별 고유 색상 폴리라인 및 지도 사이드바 멀티모달 구간 요약 표시.
  4. **통합 테스트 및 문서 최신화 (`tests/test_multimodal_routing.py`)**:
     - 맑은 날 따릉이 First-Mile 활성화 vs 우천 시 따릉이 자동 차단 및 FactChat LLM 브리핑 검증 테스트 통과.
- **산출물**:
  - `multimodal_router.py` (신규)
  - `models/transit_network.json` (신규)
  - `main.py`, `requirements.txt`
  - `Weather-Transport Recommendation UI/src/MultimodalRoutePanel.tsx` (신규)
  - `Weather-Transport Recommendation UI/src/App.tsx`, `AppM.tsx`, `TransitMap.tsx`, `subwayGraph.ts`
  - `tests/test_multimodal_routing.py` (신규)
  - `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/BACKEND_INFERENCE_SERVER.md`, `docs/API_TEST_GUIDE.md`, `docs/CHANGELOG.md`, `docs/TODO.md`


### 🌦️ 기상청 단기예보(getVilageFcst/nph-dfs_shrt_grd) 연동 및 시간대별 동적 기상 자동 동기화 (이슈 #24)
- **배경**:
  - 기존에는 초단기실황(getUltraSrtNcst) API만 연동되어 현재 시점 단일 관측값만 제공되었으며, 시간대 슬라이더를 변경하거나 미래 시간대를 조회할 때 실제 예보 날씨가 연동되지 못하고 단순 sine 곡선 추정에 의존하던 한계 개선.
  - 시간대(00시~23시)에 따른 실제 기상청 예보 기온, 강수량, 하늘상태를 AI 모델 및 B2B 재배치 엔진에 실시간 주입 필요.
- **주요 조치**:
  1. **기상청 단기예보 격자 데이터 연동 및 캐싱 모듈 개발 (kma_forecast.py 신규)**:
     - 기상청 API허브 
ph-dfs_shrt_grd 엔드포인트 연동: 149×253 한반도 전역 격자 데이터 일괄 수신.
     - 서울시 25개 자치구 및 수도권 주요 도시 격자(nx, ny) 매핑을 통해 1회 호출로 서울 전역 24시간 매시간별 기온(TMP), 1시간 강수량(PCP), 하늘상태(SKY), 강수형태(PTY) 동시 추출.
     - 30분 TTL 인메모리 캐시 및 비동기 동시성 요청(syncio.gather) 처리로 <1ms 초저지연 서빙 보장.
     - API 미인증 또는 네트워크 장애 시 계절·시간대 인식 지능형 24시간 일교차 폴백 내장.
  2. **백엔드 시간대별 예보 엔드포인트 신설 및 AI 추론 파이프라인 연계 (main.py)**:
     - GET /api/v1/weather/forecast/hourly 신설: 25개 자치구별 24시간 정밀 기상 예보 반환.
     - GET /api/v1/transit/hourly-forecast: 일교차 추정 곡선 대신 기상청 실제 예보 기온/강수량을 시간대별로 우선 주입하여 24시간 수단별 교통 수요 산출.
     - POST /api/v1/b2b/fleet-rebalance: 실시간 관제 모드에서 시간대 슬라이더 이동 시 해당 시간대의 실제 예보 날씨를 자동 반영하여 수급 불균형 및 재배치 수량 산출.
     - POST /api/v1/recommendations: 기상 입력 생략 시 해당 시간대 예보 날씨 자동 반영.
   3. **통합 테스트 작성 (	ests/test_kma_forecast.py 신규)**:
      - 24시간 예보 무결성, 낮(14시)과 밤(21시) 기온 차이에 따른 대중교통 수요 변동성, B2B 시간대별 기상 동적 주입 자동 검증 스위트 통과.
   4. **프론트엔드 메인 '날씨 현황' 페이지 시간대 슬라이더(00시~23시) 탑재 (App.tsx, AppM.tsx)**:
      - 날씨 기반 교통 현황 상단에 인터랙티브 시간대 탐색 컨트롤 패널 신설.
      - 슬라이더 이동 시 기상청 단기예보 24시간 시계열 데이터와 즉시 연동되어 시간대별 기온, 강수량, 습도, 풍속, 하늘상태가 동적으로 변경.
      - 선택된 시간대 및 예보 날씨에 맞추어 3대 대중교통(지하철, 버스, 따릉이) AI 추천 점수와 예측 이용객 수가 실시간 자동 재추론.
      - '현재 실시간 관측 모드' 및 1-클릭 '현재 시각으로 복귀' 버튼 지원.
   5. **문서 갱신**:
      - docs/API_TEST_GUIDE.md: 기상청 단기예보 24시간 시계열 테스트 방법 및 검증 항목 추가.
- **산출물**:
  - kma_forecast.py (신규)
  - main.py
  - Weather-Transport Recommendation UI/src/App.tsx
  - Weather-Transport Recommendation UI/src/AppM.tsx
  - 	ests/test_kma_forecast.py (신규)
  - docs/API_TEST_GUIDE.md
  - docs/CHANGELOG.md

### 🏢 B2B 기업·운영사용 모빌리티 수요 예측 및 재배치 대시보드 구현 (이슈 #19)
- **배경**:
  - 프로젝트 개요에서 제시한 핵심 가치인 '모빌리티 운영사의 수급 불균형 해결 및 선제적 기기 재배치(Fleet Rebalancing)'를 시스템 상에서 실제로 관제하고 분석할 수 있는 B2B 전용 뷰 신규 구축 필요.
  - 기상 변화(강수/기온) 및 시간대에 따른 25개 자치구별 따릉이 잉여/부족 대수 및 버스 배차 증차 권고를 산출하는 고속 AI 분석 엔진 개발.
- **주요 조치**:
  1. **백엔드 B2B 재배치 분석 엔드포인트 구현 (`main.py`)**:
     - `POST /api/v1/b2b/fleet-rebalance` 신설: 25개 구 32차원 ONNX 일괄 추론 기반 수급 불균형(Surplus/Deficit) 자동 분석.
     - 맑은 날(기본) 대비 수요 증감률(Δ%) 및 자치구 거치대 용량 비례 따릉이 회수/추가배치 권고 대수 산출 (우천 시 잉여 회수, 피크 시간대 공급).
     - 버스 노선 밀집 구간 배차 증차 회수 산출 및 서울시 전체 집계 요약, 상위 5대 긴급 조치 구역 리턴 (평균 연산 지연시간 ~10ms).
  2. **프론트엔드 B2B 대시보드 뷰 신규 개발 (`EnterpriseView.tsx`, `App.tsx`)**:
     - 상단 네비게이션 헤더에 `기업용 분석(🏢)` 탭 추가 (`page === 'enterprise'`).
     - 관제 컨트롤 패널: 기상청 실시간 실황 연동 모드 / 가상 기상(강수량·기온·시간대) 슬라이더 조작 시뮬레이션 모드 지원.
     - 4대 핵심 KPI 카드: 총 따릉이 잉여 회수 권고 대수, 추가 배치 권고 대수, 시내버스 증차 권고 회수, ONNX 연산 레이턴시 표시.
     - 긴급 우선 조치 카드: 최우선 회수 상위 5개 구(급감율 및 회수 대수) & 최우선 공급 상위 5개 구 랭킹 카드.
     - 25개 자치구 인터랙티브 상세 테이블: 상태별 필터(회수/공급/안정), 자치구 검색, 수급 뱃지, 권장 조정 수량 및 구체적 운영 가이드라인 표출.
     - 운영/물류팀 전달용 일일 재배치 계획 CSV 다운로드 기능 탑재.
   3. **통합 테스트 작성 (	ests/test_kma_forecast.py 신규)**:
      - 24시간 예보 무결성, 낮(14시)과 밤(21시) 기온 차이에 따른 대중교통 수요 변동성, B2B 시간대별 기상 동적 주입 자동 검증 스위트 통과.
   4. **프론트엔드 메인 '날씨 현황' 페이지 시간대 슬라이더(00시~23시) 탑재 (App.tsx, AppM.tsx)**:
      - 날씨 기반 교통 현황 상단에 인터랙티브 시간대 탐색 컨트롤 패널 신설.
      - 슬라이더 이동 시 기상청 단기예보 24시간 시계열 데이터와 즉시 연동되어 시간대별 기온, 강수량, 습도, 풍속, 하늘상태가 동적으로 변경.
      - 선택된 시간대 및 예보 날씨에 맞추어 3대 대중교통(지하철, 버스, 따릉이) AI 추천 점수와 예측 이용객 수가 실시간 자동 재추론.
      - '현재 실시간 관측 모드' 및 1-클릭 '현재 시각으로 복귀' 버튼 지원.
   5. **문서 갱신**:
      - docs/API_TEST_GUIDE.md: 기상청 단기예보 24시간 시계열 테스트 방법 및 검증 항목 추가.
- **산출물**:
  - kma_forecast.py (신규)
  - main.py
  - Weather-Transport Recommendation UI/src/App.tsx
  - Weather-Transport Recommendation UI/src/AppM.tsx
  - 	ests/test_kma_forecast.py (신규)
  - docs/API_TEST_GUIDE.md
  - docs/CHANGELOG.md
