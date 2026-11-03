# 📋 Frontend Changelog (프론트엔드 변경 이력)

> **상위 프로젝트**: [Weather & Transit Web](../../README.md)  
> **프론트엔드 가이드**: [Frontend README](../README.md)  
> **요구사항 명세서**: [REQUIREMENTS.md](../../docs/REQUIREMENTS.md)

---

## [2026-11-03]

### 🧹 목업·폴백 데이터 전수 재감사 1차(P1) — 허위 도착정보 생성 제거 및 추정치 출처 표기 (이슈 #97)
- **배경/문제**:
  - `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`가 "목업 전수 전환 100% 완료"를 선언했음에도, 실시간 API 실패 시 **허위 수치를 생성하는 폴백 코드가 다수 잔존**해 있었음 (이슈 #96 작업 중 발견).
  - (a) 지하철·버스 도착 조회 실패 시 `remaining_minutes: 2` / `'배차 간격 2~5분 정상 운행'` 등 **가짜 도착시간**을 생성, (b) `App.tsx`/`AppM.tsx` 거점 상세 파이프라인이 **버스 정류소 ID를 `111000299`로 하드코딩**하고 `472 / 140` 가짜 노선 도착 카드를 표출, (c) AI 추론 폴백 점수(`28분/95점`)·혼잡도 기본값이 실측처럼 렌더링.
- **조치 내역** (`TransitMap.tsx`, `App.tsx`, `AppM.tsx`):
  1. **허위 도착정보 생성 전면 제거**: 지하철/버스 도착 조회 실패·빈 응답 시 빈 배열로 처리하고 `CLIENT_NO_DATA` 출처 코드 부여 → `실시간 열차/버스 도착 정보를 불러오지 못했습니다` 빈 상태 표출.
  2. **하드코딩 정류소 ID 제거**: `stId=111000299` 고정 호출을 `selectedStop.stId` 기반 동적 조회로 교체하고, `stId` 부재 시 요청 자체를 생략.
  3. **가짜 노선 카드 제거**: `{ route_name: '472', arrival_msg1: '곧 도착' }`, `{ route_name: '140' }` 등 허위 도착 데이터 삭제.
  4. **출처(추정) 배지 일원화**: 지하철 팝업 배지를 하드코딩 `실시간 API` → `FALLBACK/CIRCUIT/NO_DATA` 판정 기반 **`⚠️ 시간표 추정`**으로 동적 전환(버스와 동일 규칙).
  5. **대시보드 폴백 라벨링**: AI 추론 미연동 시 **`⚠️ 기본값(추정)`**, 혼잡도 미연동 시 **`⚠️ 추정`**, 24시간 차트 폴백 시 **`⚠️ 시계열 기본값(추정)`** 배지 표출(PC·모바일 동시).
  6. **재유입 방지 가드 테스트 신설 (`tests/test_no_mock_fallbacks.py`)**: 금지 리터럴(`remaining_minutes: 2`, `'배차 간격 2~5분 정상 운행'`, `'배차간격 유지 운행중'` 등)과 추정 배지 누락을 정적 검사.
- **검증**:
  - `tests/test_no_mock_fallbacks.py` — **6개 테스트 전부 통과** (작성 직후 App.tsx/AppM.tsx의 미수정 잔존 결함을 실제로 검출하여 추가 정비).
  - `npx tsc --noEmit` — **9건** (baseline 9건 동일, 신규 오류 0건).
  - `npm run build` — 성공.
- **영향도**: 실시간 API 장애 시에도 허위 도착시간·가짜 노선이 노출되지 않고, 모든 폴백 값이 **추정치로 명시**되어 데이터 신뢰도 확보. 동일 결함의 재유입은 CI 가드 테스트로 차단.
- **잔여(P2) 조치 완료 (동일 PR 반영)**:
  - `자주 찾는 경로` 미탐색 시 임의 대체값(`'25분'` / `'1,550원'`) 제거 → `—` 표기로 정직성 확보 (PC·모바일).
  - 정적 시드 마커 커버리지 고지: 지도 사이드바 안내에 `대표 거점(버스 {BUS_STOPS.length}개소 · 따릉이 {BIKE_STATIONS.length}개소 · 주요 지하철역)` 명시 (부분집합임을 오인 방지).
  - `triggerApiConsoleLog`의 데모 정류소 ID(`111000299` / `100100118`) 하드코딩 제거 → 선택 정류소 `stId` 기반 동적 조회.
  - 가드 테스트를 P2 패턴(데모 ID, 임의 대체값, 커버리지 고지)까지 확장 — **8개 테스트 통과**.

### 🧭 지도 보기 '실시간 대중교통 경로 안내' 버튼의 구버전 지하철 경로 UI 정리 및 LangGraph 멀티모달 일원화 (이슈 #96)
- **배경/문제**:
  - 지도 보기 탭 좌측 사이드바 하단 `🧭 실시간 대중교통 경로 안내` 버튼이 `findSubwayRoute()`(레거시 단일 지하철 최단경로)를 `handleSearchRoute('강남역', '서울역')`으로 고정 호출하여, 사용자가 선택한 출발·도착지와 무관한 구버전 경로 카드가 표출됨.
  - 동일한 "경로 안내" 기능이 탭 진입 위치에 따라 서로 다른 엔진/UI로 이원화되어, 지도 탭에서는 기상 게이트(`RAIN_SAFE_ONLY`) · 따릉이 First/Last-Mile · 32차원 ONNX 혼잡도 · FactChat XAI 브리핑이 전혀 반영되지 않음.
  - 마커 미선택 시 `강남구청 → 잠실역 / 28분 / 1,550원~ / 보통` 하드코딩 목업 카드가 실시간 데이터로 오인될 수 있는 상태였음.
- **조치 내역** (`App.tsx`, `AppM.tsx`):
  1. **지도 경로 진입 CTA 제거 및 '경로 추천' 탭 일원화**: `🧭 실시간 대중교통 경로 안내` 버튼을 삭제하고, 경로 탐색 진입점을 `경로 추천` 탭(LangGraph 멀티모달)으로 단일화. 지도에서는 팝업의 `[출발지/도착지 설정]`(양쪽 완료 시 자동 탭 전환)과 상단 안내 토스트의 `경로 추천 탭 이동` 버튼으로 진입.
  2. **하드코딩 기본값 제거 및 사이드바 영역 확장**: `handleSearchRoute('강남역', '서울역')` 고정 호출과 레거시 `findSubwayRoute()`의 지도 진입 경로를 완전 차단하고, 버튼이 차지하던 하단 고정 푸터(`padding: 16px 20px` + `14px` 버튼, 약 `78px`)를 제거하여 상세 정보 스크롤 영역(`flex: 1`)이 해당 공간을 그대로 흡수하도록 조정.
  3. **목업 카드 → 빈 상태(Empty State) 교체**: 가짜 소요시간·요금·혼잡도 대신 `LangGraph 멀티모달` 배지, 안내 문구, 실시간 기상 3종(자치구 기온 · 강수 · 풍속) 칩을 표출.
  4. **레거시 탐색 역할 명확화**: `handleSearchRoute`(지하철 전용 빠른 조회)는 경로 추천 탭의 지하철 조회 · 출발/도착 맞바꾸기에서만 사용하도록 주석으로 계약 명시.
  5. PC(`App.tsx`) · 모바일(`AppM.tsx`) 동일 로직 동시 반영.
- **검증**:
  - `npx tsc --noEmit` — 변경 전/후 오류 **9건 동일**(신규 타입 오류 0건, 전량 기존 결함).
  - `npm run build` — Vite 프로덕션 번들 빌드 성공(`1.29s`, `dist/assets/index-*.js 717.91 kB`).
  - 지도 보기 CTA 클릭 시 구버전 카드 미표출 및 경로 추천 탭 전환 확인.
- **산출물**: `Weather-Transport Recommendation UI/src/App.tsx`, `AppM.tsx`, `docs/TODO.md`, `docs/CHANGELOG.md`, `Weather-Transport Recommendation UI/docs/CHANGELOG.md`, `README.md`
- **영향도**: 경로 안내 진입 경로에 따른 결과 불일치 제거, 지도 탭에서도 기상 게이트 · AI 혼잡도 · XAI 브리핑 일관 적용, 데모 목업 데이터 제거로 데이터 신뢰도 확보.

### ⚡ 전사 공공 API 및 AI 추론 데이터 캐싱 정책 명세서(CACHING_POLICY.md) 제정 (이슈 #94)
- **배경/목적**:
  - 기상청 단기예보, 서울시 실시간 지하철, 공공데이터포털 버스 도착, 서울시 따릉이 실시간 거치 등 다수의 외부 공공 API와 32차원 ONNX AI 추론 엔진의 캐시 아키텍처 및 생명주기(TTL) 정책이 여러 기술 문서에 분산되어 있던 관리 비효율 해소.
  - 외부 공공 API 일일 트래픽 한도(쿼터) 초과를 원천 차단하고, 초저지연(SLA < 15ms) 응답 및 외부 서버 장애 시 무중단 서비스(Graceful Degradation)를 완벽히 보장하기 위한 공식 통합 캐싱 정책 수립.
- **조치 내역**:
  1. **공식 캐싱 가이드 명세서 제정 (`docs/CACHING_POLICY.md`)**:
     - **데이터 도메인별 캐시 정책 및 생명주기(TTL) 표준화**:
       - 🌦️ 기상청 24시간 단기예보 격자: `30분` (`1,800초`) TTL, 서울 25개 자치구 `00~23시` 예보 일괄 동기화 및 1ms 미만 인메모리 서빙.
       - 🚲 따릉이 실시간 거치 현황: `60초` (`1분`) TTL, 서울 전역 2,700여 개 대여소 전역 스냅샷 일괄 수집.
       - 🚇 지하철 실시간 도착 정보: `15초` TTL, 열차 이동 속도 반영 단기 보호.
       - 🚌 버스 실시간 도착 정보: `15초` TTL, 정류소 및 노선별 인메모리 보호.
       - 🧠 32차원 ONNX 시계열 피처: 인메모리 링버퍼(Deque) + SQLite WAL 모드 영속 저장소 연동, 초저지연(`100μs`, 0.1ms) 공급.
       - 🗺️ 브라우저 멀티모달 경로 검색: 로컬스토리지(`weather_transit_multimodal_cache_v5`) 기반 최근 12개 검색 경로 캐싱 (네트워크 요청 0건).
     - **3계층 다중 캐시 파이프라인(Client LocalStorage ➔ Server RAM ➔ Host Disk SQLite WAL) 구조화 및 Mermaid 다이어그램화**.
     - **고가용성 장애 격리(Fault-Tolerance) 체계화**: Circuit Breaker 상태 전이 규칙(임계 `5회` 실패 시 OPEN, `60초` 후 HALF-OPEN), Last Known Good(직전 정상 스냅샷) 스케일링, Cold-Start 지능형 일주 곡선(`HOURLY_DIURNAL_FACTORS`) 폴백 방어선 명시.
     - **운영자 관제 및 관리자 제어 엔드포인트 명세**: 시계열 캐시 진단(`GET /api/v1/cache/timeseries-status`), 관리자 수동 캐시 플러시(`POST /api/v1/admin/cache/clear`), 헬스체크(`GET /health`).
  2. **상위 문서 일체화**:
     - `README.md` 메인 공식 문서 표에 `docs/CACHING_POLICY.md` 바로가기 및 핵심 내용 링크 반영.
- **영향도**: 외부 API 트래픽 한도 고갈 위험을 완전히 제거하고, 서비스 응답 지연을 획기적으로 단축하며, 신규 개발자 및 운영진이 전체 캐시 수명과 복구 정책을 단일 문서에서 즉각 파악 가능하도록 개발 거버넌스 확립.

### 🚶🚏 버스 정류소 및 따릉이 대여소 출발/도착 시 First/Last-Mile 도보 세그먼트 보존 및 자동 삽입 (이슈 #89)
- **배경/문제**:
  - 버스 정류소나 따릉이 대여소를 출발지 또는 도착지로 지정하고 멀티모달 경로를 탐색할 때, `resolve_station()`이 버스/따릉이 정보를 가장 가까운 지하철역 객체로 강제 덮어쓰기(Snapping)하여 반환함으로써 추천 경로의 출발/도착지가 실제 버스 정류소나 따릉이 대여소가 아닌 인근 지하철역으로 둔갑하는 결함 발생.
  - 이로 인해 실제 버스 정류소에서 인근 지하철역까지 이동하는 First-Mile 도보 구간이나, 도착 지하철역에서 목적지 따릉이 대여소/버스 정류소까지 이동하는 Last-Mile 도보 구간이 경로 및 지도 마커에 누락됨.
- **조치**:
  1. **백엔드 거점 정체성 보존 및 인접 지하철역 링크 구조 정비 (`multimodal_router.py`)**:
     - `resolve_station()`에서 버스 정류소 및 따릉이 대여소 매칭 시 원래의 명칭, 좌표, `station_type`(`bus`/`bike`)을 온전히 유지하고 인접 지하철역을 `nearest_subway` 필드로 연결.
     - `MultimodalRouteRequest` 및 `_execute_multimodal_search`에 `from_coords`, `to_coords`, `from_type`, `to_type` 선택 필드를 신설하여 프론트엔드에서 좌표가 주입된 경우 100% 오차 없는 직접 거점 해석 지원.
     - 정류소 해석 시 `res["nearest_subway"] = res`로 인한 순환 참조(Circular Reference)와 FastAPI 직렬화 `RecursionError`를 원천 제거(`nearest_subway = None` 명시).
     - 검색 쿼리 정규화 비교 시 `역` 제거 여부에 따른 불일치(`서울역버스환승센터` vs `서울버스환승센터`)를 해소하기 위해 키워드 힌트(`is_bus_hint`, `is_bike_hint`) 우선순위 및 이중 정규화(`b_clean`, `b_norm`) 비교 알고리즘 탑재.
  2. **First-Mile / Last-Mile 도보 세그먼트 자동 계산 및 전 경로 결합 (`multimodal_router.py`)**:
     - `_make_walk_segment(from_node, to_node)` 헬퍼 구현: 하버사인 거리 기반 도보 거리(`km`) 및 소요시간(`minutes`, 분속 `65m/min` 기준 최소 `1분` 보장) 산출.
     - `_node_candidate_fusion()`에서 출발지가 버스/따릉이인 경우 인접 지하철 탑승역까지의 First-Mile 도보 세그먼트를 생성하여 `segments` 최전방에 삽입하고 총 소요시간/도보시간/이용 수단 목록(`modes_used`)에 `walk` 자동 반영.
     - 도착지가 버스/따릉이인 경우: 지하철 최소환승 경로뿐 아니라 **AI 멀티모달 최적(`route-ai-multimodal`), 버스-지하철 환승(`route-bus-subway-hybrid`), 지하철 최단시간(`route-subway-fast`) 등 모든 후보 경로 후미에 Last-Mile 도보 세그먼트(`last_walk_seg`)를 일괄 결합**하고 소요시간·도보시간·하이라이트 및 `compat_path` 목적지 명칭을 최종 동기화.
     - `_pack_route_candidate()`에서 `compat_path`의 출발/도착 지점을 실제 출발지/도착지 명칭 및 좌표로 갱신하고 첫 탑승역과 최종 하차역에 환승 안내 정보 부여.
  3. **프론트엔드 좌표 연동 및 UI 표출 일체화 (`MultimodalRoutePanel.tsx`, `App.tsx`, `AppM.tsx`, `TransitMap.tsx`)**:
     - `App.tsx` (PC) 및 `AppM.tsx` (모바일): `departureCoords`, `destinationCoords`, `departureType`, `destinationType` 상태를 신설하여 지도 팝업 클릭 또는 `UnifiedStationSearch` 선택 시의 정확한 좌표와 거점 유형을 `searchedRoute` 및 `MultimodalRoutePanel`로 완벽히 포워딩.
     - `TransitMap.tsx`:
       - 도착지가 도보 세그먼트인 경우 도착 핀 뱃지에 `🚶 {출발거점}에서 도보 {N}분` 이동 뱃지 시각화.
       - **출발 알약과 따릉이 대여소 핀 중복 겹침 해소**: 위치 인접 임계값 확장(`0.0015도`) 및 명칭 상호 매칭을 적용하여 출발지와 동일/인접한 대여소 핀은 출발 알약 내부(`🚲 따릉이 대여: ...`)로 일체형 통합하고 중복 마커 렌더링을 차단.
        - **대중교통 하차역 및 탑승역 전용 핀 신설 (`route-alight-pin`, `route-board-pin`)**:
          - 지하철/버스에서 하차 후 목적지까지 도보로 이동할 때 선 색상만 회색 점선으로 바뀌어 하차역 이름을 직관적으로 식별하기 어렵던 결함 해결.
          - 하차역 좌표에 다크 슬레이트 캡슐 알약(`route-alight-pin`: `🚇 지하철 하차` / `🚌 버스 하차` + 역명 + 호선 배지 + 혼잡도 + `🚶 하차 후 도보 N분 이동 (M m)`)을 명확히 표출.
          - 출발지에서 도보로 첫 역까지 이동해 탑승하는 지점에도 스카이블루 테마 탑승 핀(`route-board-pin`: `🚇 지하철 탑승` / `🚌 버스 탑승` + 탑승역명 + `🚶 도보 N분 후 탑승`)을 동시 표출하여 전체 여정의 승하차 변곡점을 완벽히 시각화.
          - 마커 클릭 시 역 상세 팝업 오픈 및 부드러운 시점 이동(`flyTo`) 지원, 출발/도착/환승 마커와의 인접 임계값(`0.0015도`) 중복 렌더링 원천 차단.
  4. **단위 테스트 추가 및 100% 통과 (`tests/test_multimodal_routing.py`)**:
     - `test_bus_and_bike_first_last_mile_walk_segments`: 버스 정류소 출발 및 도착 시 First/Last-Mile 도보 세그먼트 자동 삽입(`walk`), `from`/`to` 실제 거점 명칭 온전 보존 여부 전수 검증 통과.
- **영향도**: 사용자가 버스 정류소나 따릉이 대여소에서 출발/도착하더라도 인근 지하철역으로 왜곡되지 않고, 실제 거점과 연결 도보 안내를 정확하게 제공받음으로써 멀티모달 길찾기의 신뢰성과 정밀도 극대화.

---

## [2026-11-02]

### 🛡️ 전체 코드베이스 로깅 정책(LOGGING_POLICY.md) 준수 전수 감사 및 무음 예외·민감정보 정비 (이슈 #81)
- **배경/문제**:
  - `LOGGING_POLICY.md`의 보안 규정(§7)에도 불구하고 외부 HTTP 에러(`httpx.HTTPError`) 출력 시 URL 쿼리스트링 내 공공 API 개인키(`serviceKey=...`)가 로그에 평문 노출되는 잠재적 보안 취약점 존재.
  - `main.py`, `timeseries_cache.py`, `multimodal_router.py`, `TransitMap.tsx` 등 코드베이스 곳곳에 예외 이유가 기록되지 않고 무음으로 삼켜지던 빈 예외 블록(`except: pass`, `catch {}`) 존재.
- **조치**:
  1. **민감정보 마스킹 공통 모듈 신설 (`logging_utils.py`)**:
     - `mask_sensitive_text(text)`: 공공데이터포털 `serviceKey`, `auth_key`, `api_key`, `token`, `Bearer` 토큰을 정규식으로 감지하여 식별용 앞 4자리만 보존하고 나머지를 `****`로 자동 치환.
     - `sanitize_exception(exc)`: 예외 문자열 내 URL 쿼리 파라미터 API 키를 안전하게 마스킹하는 헬퍼 구현.
  2. **인메모리 링 버퍼 로그 핸들러 전역 마스킹 적용 (`in_memory_log_handler.py`)**:
     - `emit()` 단계에서 `mask_sensitive_text()`를 기본 적용하여, 백엔드 어떤 로거에서 출력된 문자열이라도 관리자 관제 대시보드(`/health/dashboard`) 및 메모리 버퍼에 저장되기 전 100% 자동 마스킹되도록 이중 방어선 구축.
  3. **백엔드 무음 예외 전면 색출 및 표준 레벨 로깅 부여**:
     - `main.py`: 기상청 단기예보 자동 조회 실패(`line 1426`, `line 3321`) 시 무음 디폴트 전환 대신 원인과 대체 적용 내역(`logger.warning`) 명시 기록. 버스/지하철/KMA 외부 통신 에러 출력 시 `sanitize_exception()` 적용.
     - `timeseries_cache.py`: 백그라운드 SQLite 비동기 큐 포화(`queue.Full`) 시 무음 `pass` 대신 `logger.warning` 경고 로그 기록.
     - `multimodal_router.py`: `dotenv` 로드 실패(`logger.debug`), LangGraph 미설치/로드 실패(`logger.info`), 실시간 따릉이 파싱 예외(`logger.debug`) 로깅 보강.
  4. **프론트엔드 빈 `catch` 블록 정비 (`TransitMap.tsx`)**:
     - 팝업 주변 버스 정류소 조회 및 지도 뷰 로컬스토리지 영속화 실패 시 무음 삼킴 대신 `console.debug`로 기록하여 브라우저 콘솔 관측성 확보.
  5. **단위 테스트 스위트 확장 (`tests/test_observability_logging.py`)**:
     - `test_sensitive_info_masking`: 공공 API 키 마스킹, Bearer 헤더 마스킹, 인메모리 핸들러 emit 시 자동 마스킹 3종 검증 케이스 추가 및 100% 통과.
- **영향도**: 외부 API 장애 및 네트워크 에러 시 개인키 누출 위험을 원천 차단하고, 백엔드/프론트엔드 전반의 무음 결함을 해소하여 운영 안정성과 장애 원인 추적 속도를 극대화.

### 🎨 WeatherMove 서비스 전용 브랜드 로고(SVG) 제작 및 브라우저 파비콘(Favicon) 전면 탑재 (이슈 #78)
- **배경/문제**:
  - 기존 웹 앱은 브라우저 탭에 전용 파비콘이 설정되어 있지 않아 기본 빈 문서 아이콘이 노출되었으며, 상단 헤더 로고가 단순 이모지(`🌦`)로 구성되어 있어 서비스의 시각적 완성도와 브랜드 아이덴티티가 미흡했음.
- **조치**:
  1. **브랜드 벡터 로고 및 파비콘 에셋 제작 (`Weather-Transport Recommendation UI/public/`)**:
     - `favicon.svg` & `favicon.ico`: 다크 스퀴클 배경 위에 기상 햇살(골드), 은은한 구름 아크(점선), 스카이블루-민트 그라데이션 모빌리티 쾌속 궤적선 및 3개 거점(출발->환승->도착) 핀을 융합한 세련된 벡터 심볼 디자인 (16x16, 32x32, 64x64 멀티 규격 지원).
     - `logo.svg`: 풀 브랜드 로고 벡터 에셋 (심볼 마크 + 'Weather' 볼드 타이포 + 'Move' 그라데이션 텍스트 + 'AI' 캡슐 뱃지).
     - `logo-symbol.svg`: 정사각형 모바일/앱 아이콘용 심볼 에셋.
  2. **`index.html` 파비콘 및 메타태그 연동**:
     - `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />` 및 `<link rel="alternate icon" href="/favicon.ico" />` 연동.
     - 서비스 타이틀을 `WeatherMove | 기상 맞춤형 대중교통 인텔리전스`로 격상하고 브랜드 설명 메타 태그 탑재.
  3. **헤더 네비게이션 UI 고도화 (`WeatherMoveLogo.tsx`, `App.tsx`, `AppM.tsx`)**:
     - 인라인 반응형 SVG 로고 컴포넌트(`WeatherMoveLogo.tsx`)를 신설하여 0ms 즉시 렌더링 및 호버 스케일 인터랙션, 원클릭 홈 복귀 지원.
     - PC(`App.tsx`) 및 모바일(`AppM.tsx`) 상단 GNB의 기존 이모지를 신규 브랜드 로고로 전면 교체하여 플랫폼 간 통일감 구축.
  4. **백엔드 관리자 대시보드 브랜딩 일체화 (`admin_dashboard.py`)**:
     - HTML 헤더에 인라인 SVG 파비콘 데이터 URI 연동 및 상단 헤더 심볼을 WeatherMove 브랜드 로고로 정합화.
- **영향도**: 브라우저 탭, 모바일 홈 화면, 관리자 대시보드 전반에 걸쳐 고유하고 전문적인 모빌리티 AI 서비스의 브랜드 아이덴티티와 높은 시각적 완성도 확립.

### 🚏🔍 경로 추천 탭 내 출발/도착지 검색을 통합 정류소(지하철·버스·따릉이) 검색으로 확장 및 전 수단 경로 탐색 호환 (이슈 #83)
- **배경/문제**:
  - 기존 경로 추천 탭(`App.tsx`, `AppM.tsx`)에서는 출발지/도착지 입력 인터페이스가 `searchSubwayStations()` 전용으로 구현되어 있어 지하철역만 검색 가능하였음.
  - 이로 인해 버스 정류소나 따릉이 대여소를 검색하거나 지도 팝업(이슈 #79)에서 버스/따릉이를 출발·도착지로 지정해 넘어오더라도, `MultimodalRoutePanel.tsx`의 `VALID_STATION_NAMES`가 지하철역 이름 집합으로 엄격히 제한되어 경로 탐색 API 호출이 차단되거나 지하철 경로 없음 알림창이 뜨는 제약 존재.
- **조치**:
  1. `UnifiedStationSearch.tsx`:
     - `variant="route"` 지원 추가: 카드 내부 스타일에 맞추어 상단 헤더 라벨, 지우기(`✕`) 버튼, 반응형 입력 필드 및 고우선순위(z-index 150) 통합 자동완성 드롭다운을 깔끔하게 렌더링.
     - 양방향 바인딩 지원: 외부 `value` 변경(출발/도착 맞바꾸기, 지도 팝업 주입, 즐겨찾기)과 내부 입력(`query`) 실시간 동기화.
     - 지하철(🚇), 버스 정류소(🚌), 따릉이 대여소(🚲)를 실시간 통합 검색하여 원클릭 선택 및 좌표 연동 지원.
  2. `App.tsx` (PC) 및 `AppM.tsx` (모바일) 동시 전면 개편:
     - 기존의 지하철 전용 입력창 및 드롭다운을 `UnifiedStationSearch variant="route"`로 전면 교체하여 코드 약 260줄 경량화 및 플랫폼 간 완전 동기화.
     - `handleSearchRoute`: 지하철 직결 경로가 없더라도 에러 alert를 띄우지 않고, 하단의 LangGraph × FactChat `MultimodalRoutePanel`이 버스·따릉이·지하철 복합 멀티모달 경로(3종)를 자연스럽게 탐색·제공하도록 방어.
     - **검색 시점 정밀화 (`searchedRoute`)**: 입력창에 역·정류소를 선택/입력하는 것만으로 백그라운드 탐색이 조기 발화되던 문제를 교정하여, 사용자가 **[🔍 최적 경로 검색]** 버튼이나 자주 찾는 경로를 명시적으로 클릭했을 때만 멀티모달 탐색이 시작되도록 검색 버튼 본연의 UX 복원.
     - **지도 팝업 강제 페이지 전환 제거**: 지도 마커 상세 팝업에서 `[🚩 출발지로 설정]`, `[🏁 도착지로 설정]`을 클릭했을 때 사용자의 의사와 무관하게 경로 탭으로 자동 이동하던 타이머를 전면 제거하고, 지도 탐색을 유지하며 토스트의 `[경로 추천 탭 이동 ➔]` 버튼을 통해 필요할 때 자율적으로 이동하도록 개선.
     - **사이드바 거점 상세 정보 내 출발/도착 상단 버튼 신설 및 지도 팝업 동기화 닫기**:
       - 지도 팝업에 날씨, AI 혼잡도 예측, 실시간 도착 정보가 길게 표시될 때 하단 출발/도착 버튼을 누르기 위해 스크롤을 내려야 했던 불편을 해소하기 위해, 좌측 사이드바(모바일 패널)의 '선택된 거점 상세 정보' 카드 상단(노선 정보 바로 아래)에 `[🚩 출발지로 설정]` 및 `[🏁 도착지로 설정]` 버튼을 신설하여 스크롤 없이 즉시 길찾기에 바인딩할 수 있도록 개선.
       - 사이드바 상세 정보의 `✕` 닫기 버튼을 누르면 지도 뷰의 거점 팝업(`activePopupRef`)도 즉시 함께 닫히도록 양방향 동기화(`TransitMapProps.selectedStop` 및 닫기 이펙트) 구현.
      - **거점 클릭 시 카메라 뷰포트 오프셋 보정 및 팝업 창 화면 세로 중앙 정렬**:
        - 역/정류소 클릭 시 마커 좌표(`stop.coords`)를 뷰포트 정중앙으로 이동시키면 역 하단으로 길게 전개되는 팝업 창 때문에 화면 상단은 텅 비고 하단은 짤리거나 스크롤해야 했던 문제 해결.
        - `TransitMap.tsx`의 `map.flyTo`에 세로 오프셋(`offset: [0, isMobile ? -120 : -150]`)을 적용하여 마커를 화면 상단으로 올리고 카메라 시야를 아래쪽으로 이동시켰으며, 팝업을 `anchor: 'top'`으로 고정하여 마커 하단 팝업 창 전체가 화면의 세로 중앙에 완벽하게 안착되도록 카메라 뷰포트 최적화.
      - **전체 보기('all') 화면 지하철역 마커 점(Dot) 마커 일원화 및 화면 시야 최적화**:
        - 전체 보기 모드에서 지하철역만 예외적으로 역 이름 알약 배지가 표출되어 화면 전역을 텍스트로 뒤덮던 시각적 피로도를 해소.
        - 버스·따릉이와 동일하게 '전체 보기'에서는 모든 대중교통 거점을 깔끔한 혼잡도 원형 점(Dot) 마커로 정갈하게 표출하고, 역 이름 알약 배지는 '지하철역 보기'(`filterType === 'subway'`) 선택 시에만 표출되도록 수단 간 일관성 확립 (검색·선택·경로 역은 항상 알약 배지로 유지).
  3. `MultimodalRoutePanel.tsx`:
     - `VALID_STATION_NAMES`의 지하철역 단독 제약을 해제하고, `hasValidRouteInput`이 모든 유효한 거점명(`cleanFrom && cleanTo && cleanFrom !== cleanTo`)에 대해 LangGraph 멀티모달 경로 탐색을 정상 발화하도록 확장.
  4. `multimodal_router.py` & `main.py`:
     - `resolve_station()` 고도화: 지하철역뿐 아니라 버스 정류소(이름, ARS-ID, stId) 및 서울시 전역 따릉이 대여소(마스터 허브 52개소 + 실시간 스냅샷 약 2,500개소의 이름, stationNo, 대여소 번호 접두어 제거 매칭)를 인접 대중교통 거점으로 정밀하게 해석.
     - 버스 정류소나 따릉이 대여소가 출발/도착지로 지정되더라도 최적의 First/Last-Mile 멀티모달 추천 경로(AI 추천, 최단 시간, 최소 환승 3종)를 성공적으로 도출.
     - **따릉이/도보 단독 경로 지도 환승 핀 오염 결함 원천 해결**: 지하철을 전혀 타지 않는 순수 따릉이 라이딩(`route-ai-bike-direct`) 또는 도보 직통 경로에 `base_subway_route`의 지하철역 환승 정보가 상속되어 지도에 타 경로의 환승 캡슐(`🔄 환승 역명`) 핀이 잘못 노출되던 문제를 교정. `multimodal_router.py`에서 비지하철 경로는 세그먼트 기반 독자 `compat_path`를 생성하고 `transfer_stations`/`transfer_trains`를 원천 공백(`[]`) 처리하였으며, `TransitMap.tsx`에서도 `transferCount > 0` 및 대중교통 이용 여부 가드를 추가하여 렌더링을 완전히 격리.
- **영향도**: 사용자가 지하철역뿐만 아니라 집 근처 버스 정류소나 따릉이 대여소를 자유롭게 출발/도착지로 지정하여 날씨 맞춤형 멀티모달 복합 경로를 직관적으로 검색할 수 있게 됨.

---

### 🗺️🚩 지도 거점(지하철역·정류소·따릉이) 상세 팝업 내 '출발/도착' 설정 버튼 탑재 및 경로 추천 탭 원클릭 연동 (이슈 #79)
- **배경/문제**:
  - 사용자가 지도 뷰에서 마커를 클릭하여 팝업창(기상, AI 혼잡도, 도착정보)을 확인한 뒤 길찾기를 하려면, 경로 추천 탭으로 이동해 역·정류소 이름을 검색창에 다시 수동 타이핑해야 하는 불편한 UX 단절 존재.
- **조치**:
  1. `TransitMap.tsx`:
     - 거점 상세 팝업(`buildStationPopupHtml`) 하단에 `[🚩 출발지로 설정]` 및 `[🏁 도착지로 설정]` 액션 버튼 툴바 탑재.
     - 라이트/다크 모드 공통 테마 스타일(`var(--color-card2)`, `var(--color-border)`, `var(--app-text)`, 프라이머리 호버 하이라이트) 적용.
     - 팝업 열림/닫힘 시 이벤트 위임(`data-action="set-origin"`, `data-action="set-destination"`) 핸들러 및 최신 콜백 ref(`onSetOriginRef`, `onSetDestinationRef`) 연동.
     - `TransitMapProps`에 `onSetOrigin`, `onSetDestination` 콜백 속성 추가.
  2. `App.tsx` (PC) 및 `AppM.tsx` (모바일) 100% 동시 동기화:
     - `handleSetOriginFromMap`: 출발지(`departure`)에 거점 이름 자동 주입 및 로컬 스토리지 동기화.
     - `handleSetDestinationFromMap`: 도착지(`destination`)에 거점 이름 자동 주입 및 로컬 스토리지 동기화.
     - **스마트 카카오맵 스타일 인터랙션**: 출발지 설정 시 "지도에서 도착지를 마저 선택하세요" 가이드 토스트를 띄워 지도 탐색을 유지하고, 도착지까지 양쪽 모두 설정되면 자동으로 경로 추천 탭(`setPage('route')`)으로 전환.
     - 지도 상단에 슬릭한 글래스모피즘 피드백 토스트 배너 탑재 (원클릭 [경로 추천 탭 이동 ➔] 버튼 및 ✕ 닫기 지원).
- **영향도**: 지도 뷰에서 원하는 대중교통 거점을 원클릭으로 길찾기 출발지·도착지에 즉시 바인딩하여 PC와 모바일 전반의 탐색 편의성과 사용자 경험 대폭 향상.

---

### 🛡️🔍 FactChat LLM 연동 무음 Fallback 개선 및 외부 버스 API 장애 시 관측성·Graceful Degradation 강화 (이슈 #80)
- **배경/문제**:
  1. `.env`에 `FACTCHAT_API_KEY`가 미설정되었거나 더미 상태인 경우, 또는 LLM 호출 시 HTTP 401/429/500 에러 발생 시 경고 로그 없이 조용히 자체 XAI 룰 엔진으로 Fallback되어 관리자가 원인을 인지하기 어려움 (Silent Degradation).
  2. 서울시 버스 서버(`ws.bus.go.kr`)가 503 점검/과부하 상태일 때, 백엔드 `GET /api/v1/transit/bus/stations/nearby`가 HTTP 502 Bad Gateway를 던져 클라이언트 콘솔에 다량의 빨간색 에러 발생.
  3. 경로 탐색 후 지도 카메라가 출발지에서 도착지로 날아가는 동안(`easeTo`/`flyTo`), 렌더 프레임마다 주변 정류장 조회가 발생하여 1초에 수십 건의 `nearby` 요청 연타가 발생하고 서킷브레이커가 불필요하게 OPEN되는 현상.
  4. 인메모리 로거(`in_memory_log_handler.py`)에서 시스템 명칭(`weather-transit-backend`)에 포함된 'weather' 키워드로 인해 버스 API 에러 로그가 `[기상청]` 도메인으로 잘못 라벨링되는 현상.
- **조치**:
  1. `multimodal_router.py`:
     - 유효한 FactChat API 키 부재 시 명시적 `logger.warning("[FactChat] 유효한 FACTCHAT_API_KEY가 설정되지 않아 XAI 규칙 엔진으로 대체 브리핑을 생성합니다.")` 출력.
     - HTTP 비정상 응답(401, 429 등) 및 네트워크 예외 시 상태 코드/사유를 담은 명시적 WARNING 로그 기록.
     - `langgraph_trace` 및 `ai_briefing` 페이로드에 `fallback_reason` 필드를 추가하여 프론트엔드 모니터링 콘솔에서도 전환 원인을 즉시 확인 가능하도록 개선.
  2. `main.py` (`get_nearby_bus_stations`):
     - 서울시 버스 API 키 부재, 503 장애, 타임아웃, 서킷브레이커 오픈 시 HTTP 502를 던지지 않고 `HTTP 200` 정상 응답과 함께 `"stations": []` (빈 목록) 및 Fallback 사유를 반환하는 Graceful Degradation 전면 적용.
  3. `TransitMap.tsx`:
     - `map.isMoving()` 및 `map.isRotating()` 감지 로직을 추가하여 카메라 애니메이션 이동 중에는 주변 정류장 조회를 자동 유예하고, 카메라가 완전히 정지한 후 500ms 디바운스 뒤 1회만 호출하도록 방어.
     - 외부 API 지연 시 `console.error` 대신 `console.warn`으로 완화.
  4. `in_memory_log_handler.py`:
     - 도메인 태그 판별 우선순위를 재설계하여, 서킷브레이커 ➔ LangGraph ➔ 버스 ➔ 지하철 ➔ 따릉이 순서로 정확히 매핑하고 시스템 명칭 `weather`로 인한 기상청 오분류 원천 제거.
  5. `tests/test_observability_logging.py`:
     - 도메인 정밀 판별, 502 없는 주변 정류장 200 OK Fallback, FactChat 트레이스 내 `fallback_reason` 주입 검증 단위 테스트 추가 (전원 통과).
- **영향도**: 외부 API 점검 시 브라우저 콘솔 에러 폭주 원천 차단, 실시간 AI 브리핑 추론 상태의 완벽한 가시성 및 관측성(Observability) 확보.

---

## [2026-10-31]
### 🌦️⏱️ Docker 컨테이너 및 기상청 API KST(한국 표준시) 동기화 및 초단기실황 발표 시점 보정 (이슈 #75)
- **배경/문제**:
  1. Docker 컨테이너 기본 타임존이 UTC(UTC+0)로 구동되어, 현재 시각이 17시(KST)임에도 컨테이너 내부 `datetime.now()`가 08시로 계산되어 기상청 초단기실황(`getUltraSrtNcst`)을 아침 8시(`base_time: "0800"`) 데이터로 조회하는 결함 발생.
  2. 기상청 초단기실황 API(`getUltraSrtNcst`)의 공식 데이터 생성 시각(매시 40분 이후)과 달리 `minute < 10`만 직전 시간을 조회하도록 되어 있어, `10~39분` 사이 호출 시 기상청 데이터 미생성(NO_DATA) 오류 위험 존재.
- **조치**:
  1. `Dockerfile.backend`: `tzdata` 패키지 설치, `ENV TZ=Asia/Seoul`, `/etc/localtime` 심볼릭 링크 및 `/etc/timezone` 설정으로 컨테이너 시스템 타임존을 대한민국 표준시(KST)로 동기화.
  2. `docker-compose.yml`: `backend` 및 `frontend` 서비스에 `TZ=Asia/Seoul` 환경변수 주입.
  3. `main.py`, `kma_forecast.py`, `timeseries_cache.py`: `get_kst_now()` 헬퍼 함수를 전역 도입하여 호스트 환경과 무관하게 항상 일관된 KST(UTC+9) `datetime`으로 시간/날짜/시간대를 계산하도록 수정.
  4. `main.py` 초단기실황(`get_current_weather`): `now.minute < 40`일 때 직전 시간(`H-1:00`)을 조회하도록 발표 기준 시점을 보정하고, 매시 40분 이후 정시 데이터 요청 시 기상청 배치 지연으로 비어있을 경우 직전 시간대로 1회 안전 재시도(Graceful Fallback)하는 방어 로직 추가.
- **영향도**: 백엔드 `/api/v1/weather/current`, AI 시계열 예측, 헬스체크 타임스탬프 및 프론트엔드 기상 로거의 한국 표준시(KST) 100% 정합성 확보.

---

### 🚌🎨 버스 정류장 점 색상 혼잡도 연동(보통=파랑) 및 전체 보기 모드 복원 (이슈 #72)
- **배경/문제**:
  1. 주변 버스 정류장(live-bus-stations-circle) 레이어 색상이 #34D399(초록색)으로 하드코딩되어 있어, 실제 혼잡도가 '보통(45~74%, 파란색)'이어도 초록색으로 잘못 표출되는 결함 존재.
  2. 전체 보기(ilterType === 'all') 모드에서 주변 버스 정류장이 켜지지 않아 버스가 보이지 않던 문제.
- **조치**:
  1. TransitMap.tsx: loadNearbyStations에서 각 정류장 feature에 시간대·기상·역 해시 기반 혼잡도 수치(crowd), 라벨(label), 색상(color)을 계산하여 주입.
  2. live-bus-stations-circle 레이어의 circle-color를 ['coalesce', ['get', 'color'], '#38BDF8']로 바인딩하여 🟢 여유(<45%), 🔵 보통(45~74%), 🔴 혼잡(>=75%)이 정확한 색상으로 점에 반영되도록 수정.
  3. 전체 보기(ilterType === 'all') 모드에서도 주변 버스 정류장 점이 정상 표출되도록 활성화 조건 복원.
  4. 버스 원형 점에 마우스 호버(Hover) 시 [🚌 정류장명 · 혼잡도% (라벨)] 미니 말풍선 툴팁 즉각 표출.
- **영향도**: 지도 상의 버스 정류장 시각적 데이터 정합성 확보 및 전체/버스 모드 사용성 개선.

---
### 🗺️✨ 전체 보기 지도 마커 상호 가림(Cluttering) 해소 및 점 마커 호버 툴팁 탑재 (이슈 #71)
- **배경/문제**: '전체 보기(🌐)' 모드에서 줌 확대 시 지하철역, 주요 버스 거점(55곳), 따릉이 거점(52곳)이 모두 큰 알약 배지로 바뀌어 번화가(강남, 홍대, 종로 등)에서 글자가 서로 심하게 겹치고 도로를 가리는 결함 존재. 또한 전체 보기 상태에서도 실시간 주변 버스 정류장 초록 점들이 나타나 시야가 매우 난잡해짐.
- **조치**:
  1. TransitMap.tsx: '전체 보기' 모드에서는 대중교통의 주축인 지하철역만 알약 배지로 정돈 표출하고, 버스 및 따릉이 거점은 혼잡도 3색 미니 점(Dot)으로 고정하여 지하철 글자와의 겹침 원천 차단.
  2. 실시간 주변 버스정류장(live-bus-stations-circle) 레이어를 오직 ilterType === 'bus'(버스 전용 탭)에서만 켜지도록 분리하여 전체 뷰의 시야를 깔끔하게 확보.
  3. 알약 마커 충돌 검사 여백(halfW, halfH)을 실제 알약 너비(~125px)에 맞춰 넉넉하게 확장하여 역 이름 글자가 1px도 겹치지 않도록 방지.
  4. 점(Dot) 마커 호버 인터랙션 추가: 점에 마우스를 올리면 부드러운 스케일 애니메이션과 함께 [🚌/🚲 이름 · 혼잡도% (라벨)] 미니 말풍선 툴팁이 즉시 표출됨.
- **영향도**: 프론트엔드 지도 뷰포트 시각적 가독성 및 탐색성 대폭 개선 (PC/모바일 공용 TransitMap.tsx).

---
### 🚌✨ 모든 버스 정류장(검색·주변·노선) 상세 팝업 UI 및 기상·AI 추론 기능 일원화 (이슈 #70)
- **배경/문제**: 기존에는 55개 주요 거점 버스 정류장(BUS_STOPS)에만 자치구/혼잡도 칩, 기상청 실시간 기상, ONNX 32차원 AI 모델 추천 혼잡도, 실시간 도착정보 및 노선 보기가 제공되었고, 상단 검색창에서 선택한 정류장(selectedBusStation) 및 지도 확대 시 나타나는 일반 정류장(live-bus-stations-circle), 노선 경유 정류장에는 텍스트 몇 줄만 표시되는 불일치 결함 존재.
- **조치**:
  1. TransitMap.tsx: 상세 팝업 렌더러 uildStationPopupHtml 및 상세 정보 Fetch/이동 파이프라인 openStationDetail을 공통 함수로 모듈화.
  2. 검색 정류장 마커(selectedBusStation): 선택 및 클릭 시 주요 거점과 100% 동일한 풀 스펙 팝업(기상청 날씨 + AI 추론 혼잡도 + 실시간 버스 도착정보 + 노선 보기) 오픈.
  3. 일반 버스 정류장(handleStationClick): 원 클릭 시 TransitStop 객체로 매핑하여 동일한 풀 스펙 상세 팝업 및 앱 사이드패널 연동(onSelectStop) 일원화.
  4. 노선 경유 정류장(onBusRouteStopClick): 점 클릭 시 동일한 상세 팝업으로 연동.
  5. 미사용 구형 loadBusArrivals 헬퍼 제거 및 코드 중복 670여 줄 정리.
- **영향도**: 프론트엔드 지도 팝업 기능 전면 일원화, PC/모바일(TransitMap.tsx) 동시 적용.

---

### 🐛🚲 버스 정류장 검색 API 호출 오류 수정 및 따릉이 대여소 검색 신규 지원 (이슈 #67)
- **배경/문제**: Docker(Nginx 프록시) 환경에서 VITE_API_BASE_URL=""이 || 단락 평가로 http://127.0.0.1:8000으로 폴백되어 버스 정류장 검색이 
et::ERR_CONNECTION_REFUSED로 실패. 따릉이 선택 시 검색 UI가 없어 지하철·버스와 일관성 부족.
- **조치**:
  1. BusStationSearch.tsx: 	ypeof === 'string' 판별로 빈 문자열을 유효 값으로 처리.
  2. BikeStationSearch.tsx 신규: /api/v1/transit/bike/stations/search 연동, 잔여 자전거/거치대 표시, 선택 시 지도 포커스 이동.
  3. App.tsx·AppM.tsx 동시 반영: 교통수단 ike 선택 시 따릉이 대여소 검색창 노출 (지하철 검색창은 버스·따릉이 선택 시 숨김).
- **영향도**: 프론트엔드만 변경, 백엔드 API 변경 없음.

### 🔍 지하철·버스·따릉이 검색 UI 통합 및 전체 탭 통합 검색 (이슈 #68)
- **배경**: 지도 사이드패널 검색이 지하철(인라인)·버스·따릉이 컴포넌트로 분리되어 UI가 제각각이었고, '전체' 탭에서는 지하철역만 검색됨.
- **조치**:
  1. UnifiedStationSearch.tsx 신규: 단일 입력창·드롭다운. 전체=지하철+버스+따릉이 병렬 검색(종류별 상위 5건, 그룹 헤더·아이콘 구분), 개별 탭=해당 종류만(상위 15건).
  2. 키보드 탐색(↑↓/Tab/Enter/Esc), debounce 350ms, 요청 취소, 바깥 클릭 닫기, 버스·따릉이 중 하나가 실패해도 나머지 결과 표시.
  3. App.tsx·AppM.tsx의 개별 검색 UI를 통합 컴포넌트로 교체(선택 시 해당 교통수단 탭으로 전환 및 지도 포커스).
- **영향도**: 프론트엔드만 변경. BusStationSearch.tsx는 타입(BusStationResult)만 사용, BikeStationSearch.tsx는 통합 컴포넌트로 대체되어 미사용.
### 🎨🚌 지도 팝업 X버튼·버스 노선 창 테마 적용 및 전 정류장 버스 노선 보기 통일 (이슈 #69)
- **배경/문제**: 라이트 모드에서 팝업 닫기(X) 버튼이 ackground: var(--app-text) + 어두운 글자색으로 식별 불가, 버스 노선 창은 배경 
gba(17,29,53,0.96) 하드코딩 및 내부 박스에 ar(--app-text)(글자색)를 배경으로 오용. 주요 거점 정류장 팝업에는 노선 보기 버튼이 없어 정류장별 동작이 불일치.
- **조치**:
  1. index.css: 팝업 닫기 버튼을 --color-card2/--app-text/--color-border 변수 기반으로 통일(라이트 전용 오버라이드 제거).
  2. TransitMap.tsx: 버스 노선 창 배경·닫기 버튼·접근 차량 박스를 테마 변수로 교체.
  3. 주요 거점 버스 팝업 도착 행에 노선 보기 ↗ 버튼 추가(이벤트 위임), 해석된 정류소 ID(stId)를 도착 데이터에 포함.
  4. 버그 수정: 거점에 stId가 없을 때 인근 정류소를 찾는 로직이 존재하지 않는 stop.coordinates를 참조하여 항상 건너뛰던 문제를 stop.coords로 수정.
  5. 노선 보기에서 경유 정류장을 클릭하면 팝업이 겹치던 문제 수정: 경유 정류장 점이 주변 정류장 원 레이어와 겹쳐 두 레이어의 클릭 핸들러가 각각 팝업을 띄우던 것이 원인. 겹치면 경유 정류장 팝업만 표시하고, 정류장 팝업을 `busStopPopupRef`로 한 번에 하나만 유지(노선 변경·닫기 시 정리).
- **영향도**: 프론트엔드만 변경(PC/모바일 공용 TransitMap.tsx·index.css).
---
## [2026-10-29]

### 📜 전역 로깅 정책 문서 신설 및 백엔드·프론트엔드 정형화 (이슈 #64)
- **배경**:
  - 백엔드(`/health/dashboard`)와 프론트엔드(브라우저 콘솔)에 걸쳐 다양한 API 송수신 및 AI 추론 로그가 출력되고 있었으나, 시스템 전체를 관통하는 통일된 로깅 정책 문서가 부재하여 필드 규격, 타임스탬프 형식, 도메인 분류가 파편화되어 있었음.
- **주요 조치**:
  1. **공식 전역 로깅 정책 문서 신설 (`docs/LOGGING_POLICY.md`)**:
     - 통합 로그 스키마(Unified Log Schema) 정의 (`timestamp`, `level`, `service`, `action`, `params`, `metrics`, `status`, `duration_ms` 등).
     - 백엔드 링 버퍼(`maxlen=500`), 300ms 중복 방지, 서킷 브레이커 연동 정책 수립.
     - 프론트엔드 F12 콘솔 도메인 배지, 이모지 컨벤션, JSON Dump 규칙 및 보안 마스킹 가이드라인 수립.
  2. **백엔드 인메모리 핸들러 정형화 (`in_memory_log_handler.py`)**:
     - `iso_timestamp`(ISO 8601 UTC) 및 `service` 필드를 표준 엔트리에 포함하도록 보강.
  3. **프론트엔드 콘솔 로거 표준 인터페이스 탑재 (`apiLogger.ts`)**:
     - `StandardLogRecord` 인터페이스 정의 및 ISO 8601 타임스탬프(`getLogTimestamp()`) 표준화.
  4. **컨테이너 재빌드 및 배포 검증**:
     - 백엔드 및 프론트엔드 컨테이너 재빌드 완료.

### 📱 모바일 환경 경로 추천 크래시 핫픽스, 지도 가림 최적화 및 기업용 관제 탭 복구 (이슈 #62)
- **배경**:
  - 모바일 환경(화면 폭 768px 이하, `AppM.tsx` 실행)에서 '경로 추천' 탭 진입 시 화면이 백지(Blank Page)로 멈추는 P0 Blocker 버그 발생.
  - 브라우저 콘솔에서 `layers.live-bus-stations-circle.paint.circle-stroke-color: color expected, "var(--color-surface)" found` MapLibre WebGL 셰이더 에러 발생.
  - 모바일 환경에서 'B2B 기업용 관제' 탭이 메뉴에서 누락되어 접근 불가.
  - 모바일 '지도 보기' 탭에서 상단 날씨 박스, 하단 긴 안내 배지, 우측 하단 대형 범례 박스가 화면의 60% 이상을 가려 지도를 보기 어려운 UX 결함 발생.
- **주요 조치**:
  1. **경로 추천 화면 런타임 크래시 해결 (`AppM.tsx`)**:
     - 상단에 누락된 `import MultimodalRoutePanel from './MultimodalRoutePanel'`를 추가하여 `ReferenceError` 원천 제거.
     - PC용 400px 고정 2열 그리드(`gridTemplateColumns: '400px 1fr'`)를 모바일 전용 1열 세로 반응형 구조(`flexDirection: 'column'`, `padding: 16px 16px 80px'`)로 전면 개편.
  2. **MapLibre WebGL 스타일 파서 CSS 변수 검증 에러 해결 (`TransitMap.tsx`)**:
     - `live-bus-stations-circle` 및 버스 노선 레이어의 `circle-stroke-color`에 전달되던 `var(--color-surface)` 문자열을 테마 감지 실측 색상(`isDark ? '#111D35' : '#FFFFFF'`)으로 치환하여 셰이더 검증 통과.
  3. **모바일 지도 뷰포트 오버레이 슬림화 (지도 가림 90% 이상 제거)**:
     - **상단 실시간 날씨**: 2줄 상세 카드에서 `🌧️ 14°C · 강수 0mm` 형태의 초소형 컴팩트 알약(Pill) 배지로 압축.
     - **하단 긴 설명 배지**: 모바일 화면에서는 지도를 가리지 않도록 자동 숨김 처리.
     - **우측 하단 혼잡도 범례**: 화면을 차지하던 대형 박스 대신 우측 하단 플로팅 `ℹ️ 범례` 버튼으로 개편하고, 클릭 시에만 팝오버로 확인할 수 있도록 토글화.
  4. **모바일 날씨 현황 상단 배너 중복 수치 제거 및 1열 카드 적층 (`AppM.tsx`)**:
     - 상단 '기상청 초단기실황' 배너에 억지로 들어가 있던 4종 수치(기온, 강수, 습도, 풍속)가 바로 아래 대형 날씨 카드의 수치와 100% 동일한 중복 요소임을 확인하고 배너에서 제거.
     - 배너를 1줄 관측 연동 상태 및 지역 배지로 슬림화하여 스마트폰 화면에서 글자가 세로로 줄바꿈되어 깨지던 결함 원천 해결.
     - 하단 3개 대형 카드를 모바일 세로 1열 적층(`flexDirection: 'column'`, `gap: 16px`)으로 개편하여 시원한 가독성 확보.
  5. **모바일 B2B 기업용 관제 탭 복구 (`AppM.tsx`)**:
     - `EnterpriseView` 컴포넌트 import 및 `Page` 타입에 `enterprise` 추가.
     - 상단 네비게이션에 `🏢 기업용 관제` 탭 신설 및 터치 친화적 가로 스크롤(`overflowX: 'auto'`) 지원.
  6. **동별 거점 혼잡도 및 시계열 AI 예측 상세 콘솔 로거 신설 (`apiLogger.ts`, `App.tsx`, `AppM.tsx`)**:
     - 사용자가 동(자치구)이나 시간대를 변경할 때 백엔드 32차원 ONNX AI 모델 배치 추론 결과(`/api/v1/districts/live-congestion`)와 24시간 시계열 AI 예측 결과(`/api/v1/predict/hourly`)가 브라우저 개발자 콘솔(F12)에 투명하게 출력되도록 `logDistrictCongestionCall`, `logHourlyForecastCall` 신설 및 연결.
     - 주요 8대 거점(강남구 역삼·삼성동 등)의 공간 인프라 및 시계열 통계 기반 실제 AI 추론 혼잡도(지하철, 버스, 따릉이)와 날씨 요인을 브라우저 콘솔에서 즉시 검증 가능하도록 디버깅 편의성 대폭 강화.
  7. **모바일 헤더 GitHub 리포지토리 바로가기 버튼 복구 (`AppM.tsx`)**:
     - PC 버전에만 존재하고 모바일 상단 헤더에서 누락되었던 공식 GitHub 소스코드 바로가기 아이콘 버튼을 모바일 헤더 우측(테마 토글 버튼 좌측)에 복구.
  8. **날씨 현황 중복 관측 바 제거 및 대형 날씨 패널로 일원화 통합 (`App.tsx`, `AppM.tsx`)**:
     - 날씨 화면 상단에 별도로 떠 있던 '기상청 실시간 관측 현황 바'와 바로 아래의 '날씨 카드'가 동일한 기상 수치를 중복 표출하던 구조를 개편.
     - 상단의 겉돌던 별도 관측 바를 완전히 제거하고, 아래의 완성형 대형 날씨 패널 헤더에 기상청 실시간 연동/단기예보 배지, 관측소 지역, KMA 격자 좌표 및 공식 발표 시각을 자연스럽게 일원화 통합하여 화면 가독성 및 공간 효율 극대화.
  9. **모바일 날씨 패널 내부 핵심 지표 2x2(2열 2행) 그리드 복구 (`AppM.tsx`)**:
     - 모바일 전역 CSS의 `div[style*="grid-template-columns"] { 1fr !important }` 강제 규칙으로 인해 날씨 카드 내부의 습도·풍속·강수량·체감온도 4개 객체가 1열로만 길게 세로 적층되어 좌우 여백이 낭비되던 결함 발견.
     - `.weather-metrics-grid` 전용 클래스 및 `grid-template-columns: repeat(2, minmax(0, 1fr)) !important` 명시를 적용하여 PC 버전과 동일하게 2*2 그리드로 빈자리 없이 알맞게 차오르도록 개선.
  10. **모바일 지도 권역 바로가기 버튼 제거 및 경로 안내 초슬림 1줄 알약화 (`TransitMap.tsx`)**:
     - 모바일 지도 상단 좌측을 가리던 `📍 강남·역삼`, `📍 잠실·송파`, `📍 여의도`, `📍 서울역·도심` 4대 권역 이동 버튼을 모바일 화면(`isMobile`)에서 완전히 숨김 처리하여 베이스 맵 시야 확보.
     - 경로 탐색 후 지도 상단에 크게 떠 있던 2단 상세 경로 플로팅 카드(`출발 ➔ 도착`, `최소 환승 n회`, 탑승 잔여시간 행)를 모바일 전용 초슬림 1줄 배지(`🟢 출발 ➔ 🔴 도착 · n환승 · n분 [✕]`)로 전면 압축하여 지도 가림 현상을 완전히 해소.
  11. **모바일 버스정류장 검색 및 버스 정류소 마커 포커싱 기능 탑재 (`AppM.tsx`)**:
     - PC 버전에만 존재하고 모바일에서 누락되었던 `BusStationSearch` 컴포넌트와 `selectedBusStation` 상태를 완벽히 탑재.
     - 모바일 지도 탭에서 '🚌 버스' 수단 선택 시 서울시 1만 2천 개 버스정류장을 정류소명/정류소번호로 실시간 검색하고, 선택 시 지도가 해당 정류소로 부드럽게 이동(`flyTo`)하며 마커 포커싱 및 도착정보 팝업이 즉시 연동되도록 구현. PC-모바일 정보 격차 100% 해소.
  12. **경로 탐색 시 지도 상의 불필요한 중간 경유역 마커 겹침 원천 차단 (`TransitMap.tsx`)**:
     - 경로 활성화 시 경로 상의 수많은 중간역 알약 마커들이 일반 지도 뷰에서 다닥다닥 노출되어 심하게 겹치던 결함 해결.
     - 모바일 환경(`isMobile`)에서는 중간역 알약 마커를 전면 숨김 처리하여, 오직 **[🟢 출발역 ➔ 🔄 환승역 ➔ 🔴 도착역]**(및 버스 승하차, 따릉이 대여/반납) 핵심 노드 전용 핀만 깨끗하고 선명하게 표시되도록 개편.
     - PC 환경에서도 광역 뷰(`zoom < 14.5`)에서는 중간역 알약 마커를 숨겨 겹침을 방지하고, 초근접 확대 시에만 세부 노출되도록 최적화.

### 🕒 경로 추천 시간대 슬라이더 현재 시각 복귀 버튼 신설 (이슈 #59)
- **배경**:
  - 경로 추천 탭(`activeTab === 'route'`)에서 출발 시각 및 날씨/혼잡도를 조절하는 시간대 슬라이더를 조작한 후, 실시간 현재 시각으로 빠르게 복귀할 수 있는 버튼이 없어 수동으로 슬라이더를 드래그해야 하는 UX 불편 개선 필요.
- **주요 조치**:
  1. **현재 시각 원클릭 복귀 버튼 추가 (`App.tsx`, `AppM.tsx`)**:
     - 경로 추천 상단 날씨 배지 및 시간대 슬라이더(`🕒 출발 시각 HH:00`) 우측에 `!isCurrentHour` 조건부 `🔄 현재 시각` 버튼 신설.
     - 클릭 시 `setSelectedHour(nowHour)`를 호출하여 원클릭으로 현재 시각으로 즉시 재설정.
     - 다크/화이트 모드 테마 변수(`var(--color-primary)`, `color-mix(...)`)를 온전히 적용하여 시각적 가독성 및 UI 일관성 보장.
  2. **프로덕션 빌드 및 Docker 컨테이너 패키징 검증**:
     - `npm run build` 검증 완료 및 `docker compose build frontend; docker compose up -d frontend` 적용.



### 🐛 서울시 버스 API NoneType 응답 방어 및 인메모리 로그 중복 출력 개선 (이슈 #57)
- **배경**:
  - 실시간 운영 환경 및 `/health/dashboard` 관제 로그 스트리밍에서 다음 2가지 결함이 발견됨:
    1. 서울시 저상버스 도착 API(`getLowArrInfoByStId`) 호출 시, 운행 대기나 저상버스 미운행 정류소에 대해 공공데이터포털이 `{"msgBody": {"itemList": null}}`을 응답할 때 dict 슬라이싱(`items[:10]`)에서 `TypeError: 'NoneType' object is not subscriptable`이 발생하여 서킷 브레이커(`bus_circuit_breaker`)가 연속 실패 5회로 서킷을 OPEN 차단하는 결함.
    2. 인메모리 로그 핸들러(`InMemoryLogHandler`)가 루트 로거와 자식 로거(`uvicorn`, `weather_transit_api`, `multimodal_router` 등)에 중복 등록되어 `propagate=True` 전파로 인해 모든 로그 라인이 2회씩 연속 중복 수집/출력되는 결함.
- **주요 조치**:
  1. **서울시 버스 도착 API `NoneType` 방어 처리 (`main.py`, `multimodal_router.py`)**:
     - `items = msg_body.get("itemList") or []` 형태로 정규화하여 `itemList`가 `None`이어도 안전하게 빈 리스트(`[]`)로 치환.
     - `isinstance(items, dict)` 및 `isinstance(items, list)` 검사를 추가하고, 리스트 내 개별 `item` 역시 딕셔너리 검사(`if not isinstance(item, dict): continue`)를 보강.
     - 저상버스 운행 편수가 0건인 정상 응답(빈 리스트)에 대해 서킷 브레이커가 실패 카운트를 올리지 않고 정상(`record_success()`)으로 처리하여 서킷이 항상 `CLOSED` 상태를 유지하도록 개선.
  2. **인메모리 로그 핸들러 중복 수집 원천 차단 (`in_memory_log_handler.py`)**:
     - `attach_in_memory_log_handler()`에서 루트 로거(`logging.getLogger()`)에만 핸들러를 등록하고, 자식 로거(`uvicorn`, `uvicorn.access`, `uvicorn.error`, `weather_transit_api` 등)에는 중복 핸들러를 붙이지 않고 상위 전파(`propagate = True`)만 보장하도록 구조 개선.
     - `InMemoryLogHandler.emit()` 메서드에 직전 시그니처(`timestamp_str, logger_name, message`) 기반 중복 필터링(Deduplication) 안전장치를 이중 구축.
  3. **검증 및 Docker 반영**:
     - `docker compose build backend; docker compose up -d backend` 컨테이너 재빌드.
     - `/health` 서킷 브레이커 상태 확인(`seoul_bus: CLOSED`), 문제 정류소(`stId=123000600`) 실시간 호출 성공(HTTP 200, 정상 메시지 응답), `/api/v1/admin/logs`에서 로그 라인이 1건씩 중복 없이 정상 기록됨을 확인.


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
