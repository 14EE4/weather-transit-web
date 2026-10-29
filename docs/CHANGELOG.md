# 📋 Frontend Changelog (프론트엔드 변경 이력)

> **상위 프로젝트**: [Weather & Transit Web](../../README.md)  
> **프론트엔드 가이드**: [Frontend README](../README.md)  
> **요구사항 명세서**: [REQUIREMENTS.md](../../docs/REQUIREMENTS.md)

---

## [2026-10-29]

### 🌓 다크 모드 및 화이트(라이트) 모드 테마 지원 & 전역 CSS 변수 정합화 (이슈 #12)
- **배경**:
  - 사용자 환경(주간 야외, 야간 실내 등) 및 시각적 편의성에 따라 화면 테마를 자유롭게 선택할 수 있도록 다크 모드와 화이트(라이트) 모드 전환 기능 지원 필요.
  - 기존 다크 테마 기반 하드코딩된 UI 요소들(대시보드 카드, 시간대 슬라이더, 지도 팝업, LangGraph 멀티모달 패널, B2B 기업용 관제 뷰)을 반응형 CSS 변수로 정합화.
- **주요 조치**:
  1. **전역 디자인 토큰 및 CSS 테마 시스템 구축 (`src/index.css`)**:
     - `html[data-theme="dark"]`: 심야/저조도 최적화 딥 네이비 배경(`--color-bg: #0A1628`), 서피스(`--color-surface: #111D35`), 카드(`--color-card: #162040`), 텍스트(`--app-text: #F0F6FF`).
     - `html[data-theme="light"]`: 주간/가독성 최적화 클린 화이트/소프트 그레이 배경(`--color-bg: #F4F7FB`), 서피스/카드(`--color-surface: #FFFFFF`), 연한 보더(`--color-border: #D9E2EF`), 딥 네이비 텍스트(`--app-text: #172033`).
     - MapLibre GL 팝업(`maplibregl-popup-content`), 입력창(`input`, `select`, `textarea`), 날씨 그라디언트 카드(`weather-gradient-*`)의 테마별 스타일 오버라이드.
  2. **원클릭 테마 토글 버튼 탑재 및 상태 영속화 (`src/App.tsx`, `src/AppM.tsx`)**:
     - 헤더 상단에 `☀️ 화이트 모드` / `🌙 다크 모드` 원클릭 토글 버튼 제공.
     - **OS/기기 시스템 테마(`prefers-color-scheme`) 기본값 자동 감지**: 저장된 테마가 없는 첫 방문 시 사용자의 기기(OS/브라우저) 다크/라이트 설정에 맞춰 자동으로 기본 테마 결정 및 OS 테마 변경 실시간 동기화 리스너 탑재.
     - `localStorage.getItem('weather-transit-theme')`를 통한 사용자 수동 선택 영속화 및 `index.html` 프리로더 스크립트로 첫 진입 시 흰 화면 깜빡임(FOUC) 원천 차단.
  3. **신규 컴포넌트 CSS 변수 전수 정합화 (`src/MultimodalRoutePanel.tsx`, `src/EnterpriseView.tsx`)**:
     - 메인 시간대별 기상 예보 & AI 교통 분석 슬라이더 카드(App.tsx, AppM.tsx), LangGraph 대기/브리핑 헤더 카드(MultimodalRoutePanel.tsx), 지도 내 LangGraph 구간 안내 박스 및 B2B 관제 테이블 내 하드코딩 색상(`#F0F6FF`, `#162040`, `rgba(255,255,255,...)` 등)을 `var(--app-text)`, `var(--color-card)`, `var(--color-card2)`, `var(--color-border)`, `var(--color-muted)`로 전면 치환하여 라이트 모드에서의 선명한 가독성 확보.
  4. **프로덕션 빌드 및 Docker 컨테이너 패키징 검증**:
     - `npm run build` 성공 검증 및 `docker compose build frontend` 컨테이너 재빌드 완료.

### 🚌 버스+지하철 복합 환승 경로 서울시 실시간 대중교통환승 API 연동 (이슈 #50 · ROUTING-02)
- **배경**:
  - 기존 멀티모달 경로 탐색 엔진(`multimodal_router.py`)에서 버스+지하철 복합 환승 경로를 생성할 때, 출발지 인근 정류소에서 직선거리 기반의 가상 버스 노선(임의 번호 `143, 402`)과 임의의 평균 시속으로 소요시간을 추정하여 추천하던 한계를 개선.
  - 공공데이터포털의 서울시 대중교통환승경로 조회 서비스(`getPathInfoByBusNSub`)를 연동하여, 실제 버스와 지하철이 결합된 공식 인가 환승 경로와 실시간 버스 도착 정보(`arrmsg1`, `arrmsg2`)를 연계 제공.
- **주요 조치**:
  1. **서울시 대중교통환승경로 API 연동 및 인메모리 캐싱 (`multimodal_router.py`)**:
     - `http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoByBusNSub` 연동 함수 `fetch_public_transit_transfer_routes` 구현.
     - 좌표계(WGS84 소수점 6자리), 타임아웃(2.5초 보호), 결과 10분 TTL 인메모리 캐시(`_transit_transfer_cache`) 탑재.
     - 버스 세그먼트(`routeNm`, `routeId`, `fname`, `fid`, `tname`, `tid`) 및 지하철 세그먼트(`railLinkList` 개수 기반 역수 산출) 자동 파싱.
  2. **수도권 버스 노선 색상 및 유형 뱃지 시스템 구축 (`multimodal_router.py`)**:
     - 노선 번호 체계에 맞춘 간선(파랑 `#3B82F6`), 지선(초록 `#10B981`), 광역/직행(빨강 `#EF4444`), 순환(노랑 `#F59E0B`), 심야(남색 `#6366F1`), 마을(연두 `#84CC16`) 색상 자동 매핑.
     - 프론트엔드 지도 및 타임라인에 `🚌 간선 421번` 형태의 표준화된 라벨링 제공.
  3. **실시간 버스 도착 정보 결합 및 Heuristic Fallback 안전 보장 (`multimodal_router.py`)**:
     - 경로 내 버스 승차 정류소에 대해 실시간 버스 도착 정보(`live_bus_arrivals`)를 매칭하여 `🟢 실시간: 3분후[1번째 전]` 뱃지 바인딩.
     - 비서울 시계 간 광역 이동(예: 송내역 ➔ 두정역) 또는 공공 API 장애/지연 시 기존 인근 버스 정류소 복도(Corridor) 기반 Heuristic Fallback으로 100% 안전 전환.
  4. **신규 전용 REST API 엔드포인트 신설 (`main.py`)**:
     - `GET /api/v1/transit/bus/transfer-path`: `startX`, `startY`, `endX`, `endY` 파라미터 유효성 검증(위경도 범위) 및 실시간 환승 경로 목록 반환.
  5. **프론트엔드 지도 버스 승하차 핀 시각화 고도화 (`src/TransitMap.tsx`)**:
     - 지도 상에 버스 승차 정류소 핀(`route-bus-pickup-pin`, `🚌 [노선명] 승차: [정류소명]`) 및 하차/환승 핀(`route-bus-drop-pin`, `🚌 [노선명] 하차: [정류소명]`) 신설.
     - 첫 세그먼트가 버스인 경우 출발 알약 배지에 탑승 버스 정보 자동 표출.
  6. **단위 테스트 스위트 보강 (`tests/test_multimodal_routing.py`)**:
     - `test_bus_subway_transfer_api_endpoint` 신설 및 전체 13개 단위 테스트 전원 통과(`OK`).

### 📊 백엔드 독립형 실시간 로그 확인 및 헬스체크 모니터링 대시보드 구축 (이슈 #53)
- **배경**:
  - 일반 사용자용 메인 UI(`http://localhost:3100/`)에는 관리자/로그 기능이 노출되지 않도록 완벽히 격리하고,
  - 개발자 및 운영자가 브라우저 개발자 도구(F12)나 Docker CLI 터미널 없이도 URL 접근만으로 외부 공공 API 연동 상태, ONNX AI 추론 엔진, 서킷 브레이커, 실시간 서버 로그를 모니터링하고 트러블슈팅할 수 있는 백엔드 독립형 경량 대시보드 구축.
- **주요 조치**:
  1. **인메모리 순환 로그 버퍼 핸들러 구축 (`in_memory_log_handler.py`)**:
     - 파이썬 표준 `logging.Handler`를 기반으로 최근 `1,000~2,000건`의 실시간 로그를 메모리(`collections.deque`)에 안전하게 캡처 보관.
     - `_buf_lock = threading.RLock()`을 적용하여 `logging.Handler` 내부 락과의 데드락 충돌을 원천 차단.
     - 도메인 태그(기상청, 지하철, 버스, 따릉이, LangGraph, AI추론, 서킷브레이커, HTTP, 시스템) 자동 분류.
  2. **관리자 모니터링 및 제어 API 신설 (`main.py`)**:
     - `GET /api/v1/admin/logs`: 최근 로그 목록 필터링 조회 (레벨, 도메인, 키워드 검색 지원).
     - `GET /api/v1/admin/status`: 서버 가동시간(Uptime), 32차원 모델 상태, 공공 API 4종 서킷 브레이커 현황, 캐시 통계 반환.
     - `POST /api/v1/admin/cache/clear`: SQLite 시계열 캐시(`timeseries_cache.db`) 및 인메모리 단기 캐시 즉시 비우기.
  3. **단일 파일 경량 웹 대시보드 렌더링 (`/health/dashboard`, `admin_dashboard.py`)**:
     - 프론트엔드 React 의존성 없는 단일 HTML/Tailwind CDN 기반의 다크 테마 대시보드 서빙.
     - **상단 KPI 패널**: 기상청 API, 버스·지하철 연동, 따릉이 잔여량, AI ONNX 32차원 모델, 서킷 브레이커 상태 및 [캐시 비우기] 버튼.
     - **하단 라이브 로그 터미널**: `JetBrains Mono` 폰트, 실시간 자동 갱신(`1.5초` 주기 폴링), 로그 레벨/도메인 필터링, 키워드 검색, 최하단 자동 스크롤(Auto-scroll), 로그 텍스트 다운로드 기능.
  4. **Nginx 리버스 프록시 및 FastAPI Docs 연동 (`nginx.conf`)**:
     - Nginx에 `/health` 및 `/docs`, `/openapi.json` 프록시를 보강하여 `:3100` 및 `:8100` 모두에서 `/health/dashboard`와 Swagger UI 접근 지원.
     - FastAPI `/docs` 상단 설명에 대시보드 바로가기 링크 등록.

### 🎨 프론트엔드 정적 상수 분리, 스켈레톤 UI 전환 및 API 폴백 배지 명시화 (이슈 #29)
- **배경**:
  - `App.tsx` 및 `AppM.tsx` 마운트 초기 `0.1~0.5초` 동안 하드코딩된 숫자 배열(`DEFAULT_24H_DATA`, `TRANSPORT_SCORES`, `DISTRICT_DATA`)이 잠깐 번쩍이며 나타나는 현상 제거.
  - `TransitMap.tsx`에 남아있던 레거시 버스 하드코딩 정류소 ID(`111000299`) 및 임의 노선(`140`, `472`) 방어코드를 서울시 실시간 마스터 동적 조회로 완전 전환.
  - 외부 공공 API 장애/지연 시 백엔드가 반환하는 `SIMULATION_FALLBACK` 및 `CIRCUIT_OPEN` 추정치에 대해 사용자가 실시간 여부를 명확히 인지할 수 있도록 UI 배지 연동.
  - 활성 경로(길찾기) 모드에서 따릉이 대여소 마커 컬링 버그 및 도착/출발 알약과 따릉이 알약이 겹치는 UX 결함 개선.
- **주요 조치**:
  1. **정적 폴백 상수 분리 모듈화 (`src/constants/fallbackData.ts`)**:
     - `DEFAULT_24H_DATA`, `FALLBACK_TRANSPORT_SCORES`, `CORRELATION_DATA`, `FALLBACK_DISTRICT_DATA` 및 관련 TypeScript 인터페이스를 전용 상수로 분리 격리.
  2. **추천 카드 및 혼잡도 테이블 Skeleton Shimmer UI 탑재 (`src/components/SkeletonLoader.tsx`)**:
     - 초기 API 응답 수신 전까지 세련된 은은한 펄스 효과의 스켈레톤 플레이스홀더를 렌더링하여 고정 숫자 깜빡임 원천 차단.
  3. **버스 정류소 ID 동적 해석 및 가짜 노선 제거 (`src/TransitMap.tsx`)**:
     - `stop.stId`가 누락된 경우 좌표 기반 인근 정류소 API(`/api/v1/transit/bus/stations/nearby?radius=350`)를 비동기로 동적 조회하여 실제 `stId`를 바인딩하도록 개선.
     - 하드코딩된 가짜 노선(`140`, `472`) 대신 정류소 실제 경유 노선(`stop.lineInfo`) 및 실시간 도착 노선으로 정규화.
  4. **공공 API 폴백/추정치 UI 배지 신설 (`src/TransitMap.tsx`)**:
     - 백엔드 응답 `source`가 `FALLBACK` 또는 `CIRCUIT`을 포함할 경우, 지하철 및 버스 도착 팝업에 `⚠️ 시간표 추정` (주황색) 배지를 명확히 구분 표출.
  5. **활성 경로 모드 따릉이 마커 가시성 및 일체형 알약 통합 (`src/TransitMap.tsx`)**:
     - 활성 경로 탐색 상태에서도 따릉이 필터가 켜졌거나 경로 세그먼트에 포함된 대여소는 마커 컬링에서 제외하여 100% 정상 표출.
     - 도보로 이동하여 따릉이를 탑승하는 중간 경유 대여소(`🚲 대여`) 핀이 출발 알약에 흡수되어 누락되지 않도록 독립 마커 생성 보장.
     - 첫 세그먼트가 도보(`walk`) 또는 따릉이(`bike`)로 시작하는 경우, 출발역 알약에서 불필요한 지하철 도착 정보(`departureTrain`)를 숨기고 실제 첫 행동(`🚶 도보 N분 ➔ 대여소`)을 직관적으로 표출.
     - 도착지와 따릉이 반납소가 인접/일치할 경우 두 핀이 겹치지 않도록 `🏁 도착`과 `🚲 따릉이 반납: (대여소명)`을 하나의 유려한 그라디언트 캡슐 알약으로 통합 병합.
     - 환승역과 따릉이 반납소가 겹칠 경우 환승 알약에 `🚲 따릉이 반납 ➔ 🚇 환승` 정보를 통합 표출하여 핀 포개짐 방지.

### 🚇 환승역 실측 도보시간·거리 반영 및 다익스트라 최적화 (이슈 #47 · ROUTING-01)
- **배경**:
  - 기존 지하철 및 멀티모달 경로 탐색에서 모든 환승역의 환승 도보시간을 일괄 `2.0분`으로 고정함에 따라, `0.5분대` 평면 환승역(김포공항, 금정 등)과 `5.0~8.0분대` 막장 환승역(노원 6.2분, 종로3가 6.5분, 고속터미널 4.5분 등) 간의 극심한 차이가 반영되지 않아 비현실적인 경로가 추천되는 문제 해결.
- **주요 조치**:
  1. **실측 환승 데이터셋 구축 및 공식 출처 기재 (`models/station_transfer_times.json`, `stationTransferTimes.json`)**:
     - 서울 열린데이터광장(`OA-13290`: https://data.seoul.go.kr/dataList/OA-13290/S/1/datasetView.do) 및 공공데이터포털(`15044419`: https://www.data.go.kr/data/15044419/fileData.do)의 실측 데이터(기준보행속도 1.2m/s) 기반으로 수도권 주요 환승역 40여 개 역에 대한 93개 호선별 환승 쌍 구축 (`walkMinutes`, `distanceM`, `transferType`).
     - 프론트엔드(`src/data/stationTransferTimes.json`) 및 백엔드(`models/station_transfer_times.json`)에 동일 스키마로 배포 (상세 명세: `docs/CURRENT_DATA_SPEC.md` §7).
  2. **프론트엔드 다익스트라 최적 경로 탐색 및 UI 반영 (`Weather-Transport Recommendation UI/src/subwayGraph.ts`)**:
     - `TRANSFER_TIMES_MAP`을 구축하여 `getStationTransferTime`이 93개 실측 쌍에 대해 실제 도보시간/거리 반환.
     - 다익스트라 우선순위 계산 시 동일 환승 횟수 조건에서 `trInfo.walkMinutes * 1.5` 도보 페널티를 주입하여 막장 환승역 자동 회피 및 개념 환승역 우선 선택.
     - 경로 세그먼트 타임라인에 `[호선] ➔ [호선] 환승 (유형 도보 N.N분 · Mm / 방면, N분 후 도착)` 상세 안내 실시간 바인딩.
  3. **백엔드 멀티모달 라우터 정합성 연동 (`multimodal_router.py`)**:
     - 백엔드 다익스트라 탐색 우선순위 큐(PQ) 가중치에 `(tr_walk * 1.5)`를 반영하여 프론트엔드 경로 탐색 결과와의 정합성 확보.
  4. **공식 백로그 업데이트 (`docs/TODO.md`)**:
     - `[ROUTING-01]` 과제를 완료(`[x]`) 처리.

### 📋 목업 감사 과제 공식 TODO.md 일원화 및 백로그 단일화 개편 (이슈 #45)
- **배경**:
  - `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`의 초기 목업 데이터(24시간 차트, 혼잡도, 시뮬레이션 버튼 등) 전수 조사가 100% 완료됨에 따라, 문서 중복 탐색 혼선을 방지하고 개발 관리 창구를 단일화하기 위해 남은 경로 정밀화 과제를 공식 `docs/TODO.md`로 통합.
- **주요 조치**:
  1. **공식 백로그 통합 (`docs/TODO.md`)**:
     - `§0-2. 멀티모달 경로 탐색 물리/실시간 정밀화 4대 과제` 신설:
       - `[ROUTING-01 · P1]` 환승역별 실제 환승통로 도보거리/소요시간(`0.5~8.0분`) 반영 (가성비 1위 Quick Win)
       - `[ROUTING-02 · P1]` 버스+지하철 복합경로 서울시 실노선/환승 API(`getBusSubwayPathList`) 연동 (핵심 기능)
       - `[ROUTING-03 · P2]` 9호선/1호선 급행열차 스킵 다이어 분리 및 추천 (체감 효과 우수)
       - `[ROUTING-04 · P2]` 도보 및 따릉이 실도로망(OSRM/보행로) GeoJSON 연동 (후순위 정밀화)
  2. **레거시 목업 감사 문서 아카이빙 (`docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`)**:
     - 상단에 목업 전수 전환 완료 및 `docs/TODO.md` 이관 완료 공식 배너 삽입.
     - 전체 요약 테이블 내 잔여 영역을 `➡️ TODO.md 이관` 상태로 최신화하여 단일 관리 체계 확립.

### 🗺️ 지도 뷰포트 확대값(Zoom) 유지 복원 및 광역 줌아웃 Dot 마커 컬링 구현 (이슈 #43)
- **배경**:
  - 다른 탭(날씨·현황, 경로 추천 등)에서 '지도 보기' 탭으로 재진입할 때, 사용자가 이전에 설정해둔 축소 배율(Zoom Level)이 유지되지 않고 특정 확대 배율(15.5 또는 13.0)로 강제 확대되는 불편 발생.
  - 지도 화면을 광역/수도권 단위로 대폭 축소(Zoom-out)했을 때, 메이저 지하철 환승역들이 점(Dot) 마커 상태로 남아 화면 중앙에 까맣게 겹쳐 뭉치는 시각적 결함 발생.
- **주요 조치**:
  1. **지도 보기 탭 전환 시 확대값 영속 복원 (UI-01)**:
     - Weather-Transport Recommendation UI/src/App.tsx: 상단 네비게이션 탭 전환 시 잔여 검색 포커스 좌표(ocusedCoords)를 클리어하여 의도치 않은 자동 lyTo(zoom: 15) 트리거 방지.
     - Weather-Transport Recommendation UI/src/TransitMap.tsx:
       - map.on('zoomend', saveCurrentMapView) 및 컴포넌트 언마운트(cleanup) 핸들러에서 최종 뷰포트(중심, 줌)를 즉시 로컬 스토리지에 영속화.
       - prevActiveRouteRef를 도입하여, 활성 경로가 실제로 존재하다가 닫혔을 때만 easeTo(13.0) 복귀를 수행하도록 분기하여 초기 마운트 시 저장된 줌 덮어쓰기 원천 차단.
  2. **광역 줌아웃 시 점(Dot) 마커 단계별 컬링 및 뭉침 방지 (UI-02)**:
     - Weather-Transport Recommendation UI/src/TransitMap.tsx:
       - **초광역 뷰 (Zoom < 10.5)**: 사용자가 지도를 많이 축소했을 때 메이저 역을 포함한 모든 점 마커를 100% 숨김(display = 'none') 처리하여 지도 가독성 극대화.
       - **중간 광역 뷰 (10.5 <= Zoom < 11.5)**: 메이저 환승역 점 마커(반경 12px) 간에도 placedBoxes 충돌 검사를 적용해 인접한 역끼리 까맣게 뭉치는 현상 제거.
       - 하단 줌 레벨 안내 툴팁 인디케이터(Zoom < 10.5: '광역 지도 (마커 숨김): 지도를 확대하면 주요 거점이 표시됩니다') 텍스트 동기화.


### 📝 전사 시스템 문서 다년도(2023~2025 63만 건) 규격 전수 동기화 (이슈 #41)
- **배경**:
  - 신규 `2023~2025` 3개년 28열 통합데이터 도입 및 32차원 ONNX v2.1 모델 반입에 따라 기존 문서들에 남아있던 과거 단년도(20.9만 건) 및 25차원 배포 관련 잔여 서술을 전수 교정.
- **주요 조치**:
  1. `README.md`: 데이터 규모를 20.9만 건에서 `2023~2025` 3개년 62.9만 건으로 최신화.
  2. `docs/SYSTEM_ARCHITECTURE.md`: §6.1 원천 데이터셋 사양(62.9만 행 28열) 및 §6.2 현행 32차원 v2.1 모델 명세(`CURRENT_DATA_SPEC.md`, `CURRENT_MODEL_PERFORMANCE.md` 링크) 동기화.
  3. `docs/BACKEND_INFERENCE_SERVER.md`: 25차원 배포 시절 주석 정정 및 현행 32차원 실피처 계약, `/health` JSON 예시(`v2.1-multiyear-32d`) 최신화.
  4. `docs/API_STRUCTURE.md`: `/health` 엔드포인트 응답 예시 및 경로를 `v2.1-multiyear-32d` 기준으로 갱신.
  5. `docs/DOCKER_CONTAINERIZATION_PLAN.md`: Dockerfile COPY 경로를 2026-10-29 스키마로 동기화.
  6. `docs/PROJECT_PROGRESS_REPORT.md`: §3.2 모델 개선 지표를 2026-10-29 최종 평가 수치(버스 MAPE 13.81% 등)로 갱신.

### 📚 현행 모델/데이터 명세 분리 및 과거 레거시 문서/자산 아카이빙 개편
- **배경**:
  - 기존 `docs/` 디렉터리에 과거 버전(25차원, 구 32차원 더미 변수) 개발/인수인계 문서와 현행 문서가 혼재되어 탐색 혼선 발생.
  - 사용자의 "현재 모델과 데이터 문서만 깔끔하게 읽을 수 있도록 분리" 요청에 따라 구조 개편 및 아카이빙 수행.
- **주요 조치**:
  1. **현행 모델 & 데이터 표준 문서 신설**:
     - `docs/CURRENT_DATA_SPEC.md`: `2023~2025` 3개년 28열 표준 데이터셋 명세 (컬럼 28개 상세, 결측치 도메인 규칙, 32차원 벡터 빌드 공식, 자치구 인프라 통계 표).
     - `docs/CURRENT_MODEL_PERFORMANCE.md`: 2026-10-29 신규 학습된 v2.1 32차원 모델 3종 최종 성능($R^2 \ge 0.989$, 버스 MAPE 13.81% 개선, 0.05ms 레이턴시), 세대별 비교표, Optuna 최적 파라미터.
     - `docs/AI_MODEL_SPEC.md`: 구버전 서술을 제거하고 현행 v2.1 32차원 단일 기준으로 전면 슬림화 리팩토링.
  2. **과거 문서 및 모델 자산 아카이빙**:
     - `docs/archive/` 생성: `DATA_PREPROCESSING_HANDOFF_v2.md`, `MODEL_PERFORMANCE_REPORT_v1_v2.md`, `AI_INFERENCE_MODEL_SPEC_initial.md` 격리 보관 및 인덱스 `README.md` 작성.
     - `benchmarks/archive/` 생성: `original/`, `2026-10-12/`, `2026-10-14/` 과거 모델 및 실험 폴더 이동 및 인덱스 `README.md` 작성.
  3. **코드 및 인덱스 동기화**:
     - `benchmarks/evaluate_models.py`: `MODEL_SETS`를 `current_32d`(`benchmarks/2026-10-29/`) 및 `archive/` 경로로 동기화.
     - `benchmarks/README.md`, `README.md`: 신규 문서 구조 및 아카이브 바로가기 링크 반영.

### 🔄 `2023~2025` 3개년 28열 통합데이터 포맷 동기화 및 학습 파이프라인 개편 (이슈 #30)
- **배경**:
  - 2023, 2024, 2025년 3개년 대규모 교통·날씨 통합데이터(`data/통합데이터/`) 도입에 따라 데이터 규격이 33열에서 28열로 표준화됨.
  - 미사용 5개 컬럼(`지하철_하차`, `지하철_하차_결측`, `풍향(deg)`, `풍향(deg)_결측`, `풍향0_풍속양수`) 삭제 반영.
- **주요 조치**:
  1. **학습/평가 파이프라인(`benchmarks/evaluate_models.py`, `retrain_25d.py`) 수정**:
     - `지하철_하차` 컬럼 유무 확인 방어 로직 추가로 신규 28열 CSV 로드 시 `KeyError` 원천 차단.
     - 2023+2024 Train(42.0만 건) 및 2025 Test(20.9만 건) 다년도 분할 데이터셋 자동 감지 및 로드 지원.
  2. **Colab 학습 노트북(`benchmarks/CastTransit.ipynb`, `retrain_25d_colab.ipynb`) 개편**:
     - 구글 드라이브 신규 3개년 경로(`data/통합데이터/`) 자동 탐색 및 병합 로더 탑재.
     - 28열 포맷에 맞춘 `지하철_하차` 결측 처리 방어 로직 및 다년도 데이터셋 분할(`2023~2024` Train/Val ➔ `2025` 1년 전체 Test) 지원.
     - 2023, 2024 대한민국 실제 공휴일 캘린더 통합 반영 (`main.py::KR_HOLIDAYS` 동기화).
  3. **AI 모델 사양서 및 진행 보고서 동기화**:
     - `docs/AI_MODEL_SPEC.md`에 28열 표준 컬럼 규격 및 3개년 다년도 분할 체계 명시.
     - `docs/PROJECT_PROGRESS_REPORT.md` 데이터 전처리 및 증강 영역 갱신.
  4. **신규 32차원 ONNX 모델(`benchmarks/2026-10-29/`) 학습 완료 및 배포 모델(`models/`) 전면 반입**:
     - 3개년 63만 건 기반 Optuna 튜닝 완료:
       - 🚲 따릉이: $R^2=0.9894$, $\text{RMSE}=15.88$, $\text{MAPE}=16.08\%$ (전 지표 우세)
       - 🚌 버스: $R^2=0.9928$, $\text{RMSE}=476.17$ (기존 대비 RMSE -16.7% 대폭 개선)
       - 🚇 지하철: $R^2=0.9950$, $\text{RMSE}=674.22$, $\text{MAE}=284.44$
     - `models/` 서빙 슬롯으로 모델 3종 및 `feature_schema.json` 복사 반입 완료.
- **산출물**:
  - `benchmarks/2026-10-29/lgb_{bike,bus,subway}_demand.onnx` (신규)
  - `benchmarks/2026-10-29/feature_schema.json` (신규)
  - `models/lgb_{bike,bus,subway}_demand.onnx` (갱신)
  - `models/feature_schema.json` (갱신)
  - `benchmarks/results/comparison_20261029_144330.{json,md}` (신규)
  - `benchmarks/CastTransit.ipynb`
  - `benchmarks/retrain_25d_colab.ipynb`
  - `benchmarks/evaluate_models.py`
  - `benchmarks/retrain_25d.py`
  - `benchmarks/README.md`
  - `main.py`
  - `docs/AI_MODEL_SPEC.md`
  - `docs/PROJECT_PROGRESS_REPORT.md`
  - `docs/CHANGELOG.md`

### 🧹 대용량 학습용 `data/통합데이터/` 폴더 `.gitignore` 제외 규칙 추가 (이슈 #38)
- **배경**:
  - `2023~2025` 교통·날씨 대용량 학습/테스트 데이터셋(약 70MB 및 가공검증 파일)이 저장소에 업로드되어 Git 용량을 비대화시키는 것을 방지.
  - 로컬 환경에는 원본 파일들을 그대로 보존하면서, Git 저장소 경량화 원칙 준수.
- **주요 조치**:
  - `.gitignore`에 `data/통합데이터/` 경로를 추가하여 하위 모든 CSV 및 JSON 파일의 Git 추적 제외.
- **산출물**:
  - `.gitignore`
  - `docs/CHANGELOG.md`

### 📊 프로젝트 분야별 진행상황 및 정형 테스트(QA/UAT) 종합 보고서 구축 (이슈 #36)
- **배경**:
  - 데이터 증강, AI 모델 개선, 지역/시간 선택, 교통수단 추천, 경로 추천, 지도 시각화 등 각 분야별 진행 상황과 자동화 구현 및 정형 인간 테스트(QA/UAT) 기준 평가 상태를 체계적으로 정리하여 프로젝트 문서화 및 향후 계획 수립에 활용.
- **주요 조치**:
  1. **`docs/PROJECT_PROGRESS_REPORT.md` 신규 작성**:
     - 6대 분야별 구현 현황 및 진행률 비교 (자동화 구현 기준 90.8% vs 인간 정형 QA 기준 67.5%).
     - 데이터 증강(20.9만 건 실측, 11차원 동적 피처, 강수 모달시프트) 및 AI 모델 개선(32차원 ONNX, Optuna 튜닝 등) 상세 기술.
     - 4대 서비스 기능(지역/시간 선택, 교통수단 추천 및 B2B 관제, 경로 추천 및 LLM 브리핑, 지도 시각화 및 도로 코리더) 상세 정리.
     - 인간 테스터를 위한 분야별 UAT/QA 정형 테스트 체크리스트 및 수도권 대표 10대 경로 실측 대조 테스트 세트 구축.
  2. **`README.md` 문서 인덱스 동기화**:
     - `docs/` 디렉토리 목록에 `PROJECT_PROGRESS_REPORT.md` 등록.
- **산출물**:
  - `docs/PROJECT_PROGRESS_REPORT.md` (신규)
  - `README.md`
  - `docs/CHANGELOG.md`

---

## [2026-10-28]

### 🐛 버스+지하철 복합 경로(Hybrid) 지도 중복 표출 버그 해결 및 버스 실노선 폴리라인(Polyline) 연동 (이슈 #34)
- **배경**:
  - `route-bus-subway-hybrid` 경로 선택 후 '지도 보기' 진입 시, 버스 이동 구간(예: 송내역 ➔ 금천구청역)임에도 불구하고 직결 지하철 전체 경로(송내 ➔ 구로 환승 ➔ 금천구청 ➔ 두정)가 함께 `compat_path`에 남아있어 1호선 이동선 및 구로역 환승 핀, 중간 지하철역 마커가 지도와 사이드바에 중복·혼선 표출되는 결함 발견.
  - 버스 이동 구간의 지오메트리가 단순 2개 점(출발정류소 ➔ 환승정류소)만 연결된 대각선 직선으로 표출되어 지도 현실감이 떨어지는 문제 해결 필요.
- **주요 조치**:
  1. **하이브리드 경로 `compat_path` 및 환승 메타데이터 정규화 (`multimodal_router.py`)**:
     - `route-bus-subway-hybrid` 패킹 시 `base_subway_route`를 전구간 지하철(`base_sub`) 대신 버스 하차 후 지하철 구간(`sub_after_hub`)으로 분리.
     - `custom_compat_path`를 도입하여 `[출발지(도보) ➔ 버스탑승정류소 ➔ 환승역(지하철 탑승) ➔ 목적지 지하철역 목록]`으로 올바르게 구성.
     - 1호선 북부 중복 역들(중동, 부천, 온수, 구로역 등) 및 무관한 구로역 환승 마커를 완전 제거하고, 실제 환승 지점인 금천구청역만 환승역 핀으로 표출.
  2. **버스 노선 실제 도로 복도(Corridor) 폴리라인 생성 엔진 구현 (`multimodal_router.py`, `main.py`)**:
     - `generate_bus_corridor_coords`: 기구현된 서울시 버스 노선 정류소 조회 API(`get_bus_route_stations`, `main.py`) 캐시와 연동하고, 수도권 역사/정류소 네트워크 기반 복도(Corridor) 분석 및 도로망 보간 알고리즘을 구축하여 15~35개의 자연스러운 도로 주행 폴리라인 좌표열 생성.
     - 버스 이동 구간이 대각선 직선 대신 실제 간선도로를 따라 부드럽게 주행하는 현실적 지오메트리로 표출.
  3. **프론트엔드 캐시 무효화 및 단위 테스트 (`MultimodalRoutePanel.tsx`, `tests/test_multimodal_routing.py`)**:
     - `MultimodalRoutePanel.tsx` 로컬스토리지 캐시 키 상향(`v4` ➔ `v5`)으로 과거 중복 경로 캐시 자동 무효화.
     - `test_hybrid_bus_subway_route_and_bus_polyline_corridor` 단위 테스트 추가 (구로역 환승 제거, 금천구청역 환승 바인딩, 1호선 북부역 제외, 버스 15+ 좌표열 검증 등 12개 테스트 통과).

### 🚀 멀티모달 경로 탐색 정밀화: 서울시 버스·지하철 실환승 API 연동, 환승역별 실측 도보시간 및 급행열차 반영 (이슈 #27)
- **배경**:
  - 기존 멀티모달 탐색에서 환승역별 보행 시간이 일률적인 2.0분(또는 프론트엔드 4분)으로 고정되어 있던 한계를 극복하고, 서울교통공사 실측 통계 기반 정밀 환승 도보 시간 및 환승 난이도를 반영.
  - 9호선 급행, 1호선 경인/경부 급행 등 수도권 급행열차의 일반역 무정차 통과(Skip) 다이어 및 소요시간 단축 모델링 구축.
  - 서울시 대중교통 실시간 버스 도착 API(`get_bus_arrival`) 및 버스-지하철 환승 API(`getPathInfoByBusNSub`)를 연계하여 버스+지하철 하이브리드 경로에 실시간 잔여시간 및 정류소 정보를 실시간 주입.
- **주요 조치**:
  1. **주요 환승역 실측 도보시간 및 환승거리 마스터 데이터 구축 (`models/station_transfer_times.json`)**:
     - 서울역(1호선↔공항철도 5.5분/350m, 1호선↔4호선 2.8분/180m), 노원역(4호선↔7호선 6.2분/312m), 종로3가역(1호선↔5호선 6.5분/420m), 고속터미널역(3호선↔7호선 4.5분, 7호선↔9호선 4.2분), 김포공항역(5호선↔9호선 0.8분, 9호선↔공항철도 0.5분 평면환승), 금정역(1호선↔4호선 0.5분/30m) 등 40+ 환승 페어 마스터 데이터 구축.
     - 백엔드 `multimodal_router.py`와 프론트엔드 `subwayGraph.ts`에 동시 적용하여 환승 도보 세그먼트 정밀화 및 다익스트라 최단시간(`min_time`) 라우팅 비용에 직접 반영.
  2. **수도권 지하철 급행열차(Express) 운행 스펙 및 정차역 스킵 모델링 (`multimodal_router.py`)**:
     - `EXPRESS_SPECS` 정의: 9호선 급행, 1호선 경인/경부급행, 수인분당선 급행의 정차역 리스트, 운행속도(55~60km/h), 통과역당 절약시간(1.05~1.15분) 탑재.
     - `_build_subway_segment`: 양 끝 정차역이 급행 정차역이고 통과하는 일반역이 2개 이상일 때 급행열차로 자동 감지, `🚇 {line_name}(급행)` 라벨링, 통과역 수 및 절약 시간(`time_saved_minutes`) 자동 계산.
  3. **실시간 버스 도착 API(`get_bus_arrival`) 및 대중교통 연계 (`main.py`)**:
     - `_execute_multimodal_search`에서 출발지 인근 버스 정류소의 실시간 버스 도착 정보(`DATA_GO_KR_BUS_KEY`)를 호출하여 `live_bus_arrivals`로 멀티모달 엔진에 전달.
     - 버스+지하철 하이브리드 경로(`route-bus-subway-hybrid`)의 버스 세그먼트에 실시간 도착 뱃지(`🟢 실시간: {도착메시지}`) 및 노선명 매칭 주입.
  4. **단위 테스트 및 빌드 검증 (`tests/test_multimodal_routing.py`)**:
     - 실측 환승시간 조회, 9호선 급행 스킵 감지(김포공항➔신논현 14개 역 무정차 통과, 16분 단축), 실시간 버스 도착 뱃지 주입 등 신규 테스트 추가 (총 11개 테스트 통과).
     - Docker 컨테이너 재빌드(`backend`, `frontend`) 및 `/health`, `/api/v1/routes/multimodal-search` 정상 동작 검증 완료.
  5. **경로 추천 페이지 출발/도착 초기화 및 60분 이상 시간-분 포맷팅 적용**:
     - 프론트엔드(`App.tsx`, `AppM.tsx`, `MultimodalRoutePanel.tsx`, `subwayGraph.ts`):
       - 출발지/도착지 입력창에 개별 삭제(✕ 지우기) 버튼 및 출발·도착 맞바꿈(⇅) 버튼 추가.
       - `🔄 초기화` 버튼을 검색 버튼 우측에 배치하여 출발지, 도착지, 추천 경로 선택 상태 및 로컬 스토리지 일괄 초기화 지원.
       - 예상 소요시간이 60분 이상일 경우 `X시간 Y분` 포맷(`formatDurationMinutes`)으로 환산 표기 (예: 65분 ➔ `1시간 5분`, 60분 ➔ `1시간`).
       - 멀티모달 후보 카드, 상세 요약, 세그먼트별 소요시간 툴팁, 지도 액티브 경로 카드 및 최근 검색 경로까지 일관된 시간 포맷 적용.
     - 백엔드(`multimodal_router.py`):
       - `format_duration_kr` 유틸리티 함수 구현 및 후보 경로 `formatted_duration`, `summary` 필드에 시간-분 포맷팅 적용.
  6. **구로역 분기(경인·경부) 및 1·2·5·경의중앙선 지선 토폴로지/분기역 환승 규칙 동기화**:
     - 백엔드 `models/transit_network.json`, `data/subway_stations_with_coords.json`, `data/subway_graph.json`을 프론트엔드 마스터(`subwayData.ts`, `subwayGraph.ts`, 614개 역)와 100% 동기화하여 구로역↔가산디지털단지역 단절 및 1호선 지선(광명셔틀·서동탄지선·연천) 오연결 해결.
     - `multimodal_router.py`에 7대 분기역(`구로역`, `금천구청역`, `병점역`, `강동역`, `가좌역`, `성수역`, `신도림역`) 계통 환승 규칙(`BRANCH_TRANSFER_RULES` / `check_branch_transfer`) 및 수도권 외 구간(평택~신창, 가평~춘천) 운임 특례 이식.
     - `MultimodalRoutePanel.tsx` 로컬스토리지 캐시 버전(`v4`) 갱신 및 `test_guro_branch_and_line1_branch_topology` 회귀 방지 단위 테스트 추가.
- **산출물**:
  - `models/station_transfer_times.json` (신규)
  - `models/transit_network.json`
  - `data/subway_stations_with_coords.json`
  - `data/subway_graph.json`
  - `multimodal_router.py`
  - `main.py`
  - `Weather-Transport Recommendation UI/src/App.tsx`
  - `Weather-Transport Recommendation UI/src/AppM.tsx`
  - `Weather-Transport Recommendation UI/src/MultimodalRoutePanel.tsx`
  - `Weather-Transport Recommendation UI/src/subwayGraph.ts`
  - `tests/test_multimodal_routing.py`
  - `docs/CHANGELOG.md`

### 🏛️ 시스템 아키텍처 다이어그램 및 명세서에 LangGraph 및 FactChat LLM 파이프라인 반영 (이슈 #31)
- **배경**:
  - 이슈 #18을 통해 구축된 LangGraph 5단계 멀티모달 라우팅 엔진 및 FactChat LLM 브리핑 파이프라인을 `README.md` 및 `docs/SYSTEM_ARCHITECTURE.md` 다이어그램과 명세서에 전면 반영하여 시스템 설계 문서의 정합성 확보.
- **주요 조치**:
  1. **`README.md` 전체 시스템 아키텍처 플로우차트 갱신**:
     - `S4 서빙 엔진`과 `S7 프론트엔드` 사이에 **`S6 LangGraph × FactChat 멀티모달 오케스트레이션 (multimodal_router.py)`** 파이프라인(5단계 노드, 기상 게이트 조건부 분기, 다목적 효용 랭킹)을 명시적으로 추가.
  2. **`docs/SYSTEM_ARCHITECTURE.md` 전면 최신화**:
     - **C4 컨텍스트 다이어그램 (§2)**: `LangGraph Multimodal Agent` 및 외부 `FactChat / BAZE Gateway (gpt-6-luna)` 연동 관계 추가.
     - **엔드투엔드 파이프라인 플로우차트 (§2.1)**: 5단계 StateGraph 노드(`parse_context`, `weather_gate_router`, `clear/rain_safe_tools`, `candidate_fusion`, `factchat_llm_briefing`) 흐름 반영.
     - **전체 계층형 아키텍처 (§3)**: 기존 5-Tier에서 `Agent & Multimodal Orchestration Layer`가 포함된 **6-Tier 계층형 아키텍처**로 개편.
     - **주요 컴포넌트 상세 설계 (§4)**: `4.5 LangGraph 멀티모달 오케스트레이션 엔진 및 FactChat LLM 브리핑` 상세 절 신설.
     - **데이터 흐름 및 시퀀스 다이어그램 (§5)**: `5.4 LangGraph 멀티모달 복합 경로 탐색 및 FactChat AI 브리핑 흐름` 시퀀스 다이어그램 추가.
     - **라우팅 에셋 명세 (§9)**: `multimodal_router.py`, `models/transit_network.json`, `MultimodalRoutePanel.tsx` 명세 체계화.
  3. **`docs/ONNX_LANGGRAPH_INTEGRATION.md` 기술 명세서 신설**:
     - 32차원 ONNX 3개 모델(지하철, 버스, 따릉이)의 실시간 추론 결과가 LangGraph 5단계 노드와 다목적 효용 함수(Multi-Objective Utility Score), 출퇴근 피크 분산 보너스(+14.0점), FactChat LLM 프롬프트 팩트 주입에 연동되는 전 과정과 수식·실전 시나리오를 심층 기술.
  4. **`README.md` 환경 변수 설정 및 API 활용 신청 안내에 LLM 게이트웨이 추가**:
     - `.env` 템플릿에 `FACTCHAT_BASE_URL`, `FACTCHAT_API_KEY`, `FACTCHAT_MODEL_NAME` 변수 수록
     - `FactChat / BAZE API Gateway` 발급처, OpenAI 호환 규격 및 키 미설정 시 자동 XAI 폴백 동작 원리 명시
- **산출물**:
  - `docs/ONNX_LANGGRAPH_INTEGRATION.md` (신규)
  - `README.md`
  - `docs/SYSTEM_ARCHITECTURE.md`
  - `docs/BACKEND_INFERENCE_SERVER.md`
  - `docs/CHANGELOG.md`

### 🧠 LangGraph 및 FactChat LLM 기반 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 엔진 구축 및 정밀 교정 (이슈 #18)
- **배경**:
  - 기존 단일 지하철 역-역 탐색을 넘어, 기상 실황/단기예보와 32차원 ONNX 수단별 혼잡도 및 실시간 따릉이 잔여 대수를 종합해 **도보 + 따릉이(First/Last-Mile) + 버스 + 지하철** 복합 경로를 오케스트레이션하는 지능형 라우팅 엔진 구축.
  - 초기 구현 후 발견된 ① 서울역 출발 시 회현역 경유 후 다시 서울역으로 돌아오는 제자리걸음 루프 버그, ② 무조건 따릉이를 1순위로 고정하던 문제, ③ 부천 송내역 등 비서울권에서 서울시 전용 따릉이(서울식물원 등 15km 점프)가 추천되던 문제, ④ 정거장 수 off-by-one 및 노선별 주행시간·배차간격 미검증 문제, ⑤ 탭 전환 시 재로딩 및 지도 알약 마커 겹침 문제를 전수 해결.
- **주요 조치**:
  1. **LangGraph `StateGraph` 5단계 멀티모달 라우팅 엔진 구현 (`multimodal_router.py`, `models/transit_network.json`)**:
     - `parse_context_node`: 출발/도착지 좌표 해석, 시간대별 기상청 단기예보(`kma_forecast_manager`) 및 32차원 ONNX 혼잡도 로드.
     - `weather_gate_router` (조건부 분기): 강수(`rain > 0mm`)·강풍(`>= 8m/s`)·혹한(`<= -5°C`) 시 `RAIN_SAFE_ONLY`로 분기하여 따릉이(PM) 구간을 자동 차단하고 실내 철도/버스 환승 경로로 우회.
     - `clear_multimodal_tools_node` / `rain_safe_tools_node`: 지하철 다익스트라(최소환승/최단시간), 인근 버스정류소, 실시간 따릉이 스냅샷(`_bike_snapshot_cache`) 연동.
     - `candidate_fusion_node`: `AI 멀티모달 최적(따릉이 First-Mile + 지하철)`, `지하철 최소환승`, `버스+지하철 복합 환승` 등 맞춤형 후보 경로 및 구간별(`segments`) 타임라인·운임·GeoJSON 좌표 생성.
     - `factchat_llm_briefing_node`: FactChat / BAZE 게이트웨이(`gpt-6-luna`) 연동 자연어 AI 브리핑 생성 (5분 TTL 캐시 및 XAI 폴백 내장).
  2. **다목적 효용 함수(Multi-Objective Utility Score) 및 루프 방지·권역 검증 (`multimodal_router.py`)**:
     - **제자리걸음 루프 차단**: First-Mile 따릉이 반납역이 출발역과 동일하거나 반납역에서 도착역까지의 남은 지하철 경로가 출발역 자체를 다시 경유하는 경우 후보에서 제외하고, 출발역보다 목적지에 실질적으로 가까워지거나 환승 횟수를 줄여주는 직접 환승 허브(예: `서울역 ➔ 공덕역` 후 공항철도/경의중앙선 무환승 1정거장)를 탐색하도록 개선.
     - **합리적 1순위 산정 (`_evaluate_route_utility`)**: 소요시간(분)·환승횟수·요금(원)·혼잡도(%)·기상을 종합한 효용 점수로 후보를 정렬하여, 직통 지하철이 더 빠르고 저렴하면 지하철을 1순위로, 따릉이가 환승과 시간을 단축하면 따릉이 멀티모달을 1순위로 동적 추천.
     - **서울시 행정구역(`is_in_seoul`) 경계 검증 및 반경 850m 제한**: 부천(`송내역`, `중동역`, `부천역`), 인천(`부평역`), 경기(`수원역`, `판교역`) 등 비서울권 역사에서 서울시 전용 공공자전거인 따릉이를 자동 배제하고, 인근 정류소/대여소 매칭 반경을 850m 이내로 제한하여 원거리 직선 점프 폴리라인 버그 원천 차단.
  3. **19개 노선별 주행속도·배차간격 물리 산식 및 실시간 열차 도착 연동 (`multimodal_router.py`, `main.py`, `subwayGraph.ts`)**:
     - 수도권 19개 노선별 표정속도·역 정차시간(`LINE_OPERATING_SPECS`) 및 첨두/평시/심야 배차간격(`get_line_headway`) 테이블 구축.
     - 정거장 수 off-by-one 버그(`len(steps)` ➔ `max(1, len(steps) - 1)`) 수정으로 1정거장 이동 시 정확히 `1정거장 (2~3분)` 산출.
     - 서울 열린데이터광장 실시간 지하철 도착 API(`get_subway_arrival`)를 멀티모달 라우터에 직접 주입하여 실제 열차 대기시간 반영 및 `구간 소요시간 합계 == 총 소요시간(total_minutes)` 100% 일치 보장.
  4. **프론트엔드 멀티모달 UI, 로컬 캐싱 및 지도 마커 겹침 해결 (`MultimodalRoutePanel.tsx`, `App.tsx`, `AppM.tsx`, `TransitMap.tsx`)**:
     - 인메모리 + `localStorage`(`weather_transit_multimodal_cache_v3`, `weather_transit_route_departure/destination`) 캐싱으로 `지도` ↔ `경로 추천` 탭 전환 시 재로딩 없이 0ms 즉시 복원.
     - 경로 탐색 중 로딩 배너 표시 및 브라우저 콘솔(`F12`)에 LangGraph 5단계 노드 트레이스·후보 테이블 실시간 로깅.
     - `TransitMap.tsx`: 다중 호선 환승역(예: 서울역)이 경의중앙선으로 잘못 고정되던 현상을 실제 탑승 호선으로 동적 보정하고, 경로 핀(`출발 · 서울역`)과 기본 역 알약 마커(`서울역 33%`)가 겹치던 현상을 기본 마커 숨김 처리로 완벽 해결.
  5. **통합 테스트 및 하드코딩/목업 데이터 전수 감사 (`tests/test_multimodal_routing.py`, `docs/TODO.md`, `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`)**:
     - 맑은 날/비 오는 날/다목적 효용 랭킹/비서울권(송내역) 따릉이 배제/물리적 주행시간·배차간격 정합성 6대 자동화 테스트 통과.
     - 코드베이스 내 잔존 하드코딩·미검증 근사치·정적 폴백 데이터를 전수 조사하여 `docs/TODO.md` 및 `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`에 수정 방안 문서화 완료.
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
