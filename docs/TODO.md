# 📋 Weather & Transit Web 프로젝트 TODO 및 백로그 (Backlog)

본 문서는 Weather & Transit Web 서비스의 향후 개발 및 개선 과제를 관리하는 공식 TODO 리스트입니다.

---

## 📌 우선순위별 개발 백로그

### 🗺️ 0. 지도 인터랙션 및 시각화 고도화 (Next Sprint / 우선 착수) — **완료 (이슈 #43)**
- [x] **[UI-01] 지도 탭 이동 시 이전 줌(확대값) 및 중심 좌표 영속 유지 (완료 · 2026-10-29)**:
  - 다른 탭(경로 추천 등)에서 `지도 보기` 탭으로 전환할 때 이전 줌 레벨이 유지되지 않고 특정 확대값(15.5)으로 강제 줌인되는 현상 수정.
  - 마운트 시 `STORAGE_SELECTED_STOP_KEY`에 의한 강제 `flyTo(15.5)` 및 `focusedCoords` 잔여 상태 간섭을 차단하고, 사용자가 직전에 보던 `STORAGE_MAP_VIEW_KEY`(center, zoom)를 온전히 복원.
  - `zoomend` 및 언마운트 시점 즉시 영속화, `prevActiveRouteRef`로 경로 해제 시에만 `easeTo(13.0)` 복귀하도록 격리 완료.
- [x] **[UI-02] 광역 축소 시 주요 지하철역 점(Dot) 마커 겹침 방지 및 단계적 숨김 (완료 · 2026-10-29)**:
  - 지도 축소 시 버스/따릉이는 숨겨지나 지하철 주요 허브역(priority >= 250)은 점 마커로 남아있어, 광역 뷰(서울 전역 또는 수도권 원경)에서 점들끼리 서로 뭉쳐서 겹치는 현상 해결.
  - 초광역 뷰(`currentZoom < 10.5`)에서 메이저 역 점 마커도 완전히 숨김(`display: none`) 처리하여 축소 시 깨끗한 베이스 맵 제공.
  - 중간 광역 뷰(`10.5 <= currentZoom < 11.5`)에서 메이저 점 마커 간 충돌 박스(`dotBox` 12px) 검사를 적용하여 겹침 원천 제거 완료.
- [x] **[UI-03] 다크 모드 및 화이트(라이트) 모드 테마 전환 및 전역 영속화 (완료 · 2026-10-29 · 이슈 #12)**:
  - 다크/화이트 모드 원클릭 토글 버튼 탑재 (`Weather-Transport Recommendation UI/src/App.tsx`, `AppM.tsx`).
  - 전역 CSS 변수 시스템(`src/index.css`) 구축 및 지도 팝업, 멀티모달 패널, 기업용 관제 뷰 전수 CSS 변수 정합화.
  - `localStorage` 기반 테마 영속화로 새로고침 및 탭 전환 시에도 사용자 테마 100% 보존.
- [x] **[UI-04] 경로 추천 시간대 슬라이더 현재 시각 복귀 버튼 신설 (완료 · 2026-10-29 · 이슈 #59)**:
  - 경로 추천 탭(`activeTab === 'route'`)의 출발 시각 조절 슬라이더에 현재 시각이 아닐 때(`!isCurrentHour`) `🔄 현재 시각` 버튼 표출.
  - 클릭 시 `setSelectedHour(nowHour)`를 실행하여 실시간 현재 시각으로 즉시 재설정 가능하도록 편의성 강화.
- [x] **[UI-05] 모바일 환경 경로 추천 크래시 핫픽스, 지도 가림 최적화 및 기업용 관제 탭 복구 (완료 · 2026-10-29 · 이슈 #62)**:
  - `AppM.tsx` 내 `MultimodalRoutePanel` 누락 import 추가로 런타임 `ReferenceError` 및 백지 현상 원천 해결.
  - 모바일 세로 1열 반응형 레이아웃(`maxWidth: 640px`, `padding: 16px 16px 80px`, `display: flex`, `flexDirection: column`)으로 전면 재구성.
  - MapLibre GL JS `circle-stroke-color` WebGL paint CSS 변수(`var(--color-surface)`) 에러를 테마 감지 실측 색상으로 치환.
  - 모바일 지도 뷰포트 오버레이 슬림화 (상단 날씨 1줄 알약화, 하단 긴 배지 숨김, 우측 하단 범례 `ℹ️` 토글화로 지도 가림 90% 이상 제거).
  - 모바일 뷰에 `🏢 기업용 관제`(`enterprise`) 탭 및 `EnterpriseView` 연결 복구.
  - 모바일 날씨 현황 상단 초단기실황 배너 내 중복 4수치 제거 및 메인 3개 카드 세로 1열 적층으로 글자 세로 깨짐 원천 해결.
  - 날씨 현황 중복 상단 관측 바 제거 및 하단 완성형 대형 날씨 패널로 일원화 통합 완료 (`App.tsx`, `AppM.tsx`).
  - 동별 거점 혼잡도 및 시계열 AI 예측 상세 콘솔 로거(`apiLogger.ts`) 신설 및 모바일 헤더 GitHub 버튼 복구 완료.
---

### 🛡️ 0-0. 운영 안정성 및 관제 신뢰도 고도화 (완료 · 2026-10-29 · 이슈 #57)
- [x] **[STAB-01] 서울시 버스 API NoneType 응답 방어 및 서킷 브레이커 안정화 (완료 · 2026-10-29 · 이슈 #57)**:
  - 서울시 저상버스 도착 API(`getLowArrInfoByStId`) 응답에서 `msgBody` 또는 `itemList`가 `null`일 때 `TypeError: 'NoneType' object is not subscriptable` 에러 발생 및 서킷 차단 버그 수정.
  - `items = msg_body.get("itemList") or []` 및 타입 검증 보강, 운행 대기/0건 수신 시 서킷 정상(`record_success()`) 유지 처리 완료.
- [x] **[STAB-02] 인메모리 로그 핸들러(`InMemoryLogHandler`) 중복 기록 원천 해소 (완료 · 2026-10-29 · 이슈 #57)**:
  - 루트 로거와 자식 로거 동시 등록으로 인한 `propagate=True` 중복 호출을 루트 단일 등록 구조로 개편.
  - 직전 시그니처(`timestamp, logger, message`) 기반 중복 필터링 안전장치 탑재로 `/health/dashboard` 관제 로그 스트리밍 무결성 확보.

---

### 📊 0-1. 데이터 엔지니어링 및 품질/신뢰도 고도화 5대 과제 (Backlog)
- [ ] **[DATA-01 · 품질/신뢰도 · P0] 2025년 `11월 말 ~ 12월` 버스 승차 결측치 원천 재수집**:
  - 2025년 1년 전체 Test 데이터셋 중 `2025-11-28 ~ 2025-12-31` 사이 약 15일간(8,625건, 약 24.59%)의 버스 승차량 원천 결측을 서울 열린데이터광장(`서울시 노선별/정류장별 시간대별 승하차 인원 정보`)에서 재수집하여 보간 행을 실측값으로 대체 및 버스 모델 최종 파인튜닝.
- [ ] **[DATA-02 · 협업/재현성 · P1] 대용량 원천 데이터셋 무결성 메타데이터 및 체크섬 구축**:
  - `data/통합데이터/` (2023, 2024, 2025년 63만 행)가 `.gitignore`로 제외되어 있으므로, 타 환경 재현성을 위해 `data/dataset_checksums.json` 또는 `data/README.md`를 신설하여 연도별 정밀 행/열 수, 결측치 플래그 현황, SHA-256 체크섬 및 다운로드/배치 가이드 제공.
- [ ] **[DATA-03 · 일반화/안정성 · P1] 극한 기상(악천후) 인공 합성 데이터 증강 (Synthetic Augmentation)**:
  - 시간당 30mm 이상 집중호우, 대설, 영하 15도 이하 혹한 등 희귀 기상 상황(0.5% 미만)의 외삽 리스크를 방지하기 위해, 물리 기반 모달 시프트 특성을 반영한 합성 증강 데이터를 추가하여 B2B 시뮬레이션 안정성 확보.
- [ ] **[DATA-04 · 시계열 정밀도 · P2] 연도별 자치구 공간 인프라 통계 분리 (`main.py::DISTRICT_INFRA`)**:
  - 현재 2025년 기준 고정 상수인 자치구 4대 인프라(지하철역 수, 버스정류소 수, 따릉이 거치대 수, 상업밀도)를 연도별(2023, 2024, 2025) 실제 개통/증설 연혁을 반영한 시계열 인프라 딕셔너리로 세분화.
- [x] **[DATA-05 · 실시간 서빙 · P2] 실시간 공공 API 장애 대비 폴백 데이터 품질 고도화 및 UI 배지 연동 (완료 · 2026-10-29 · 이슈 #29)**:
  - 기상청/서울시 OpenAPI 장애 시 서킷 브레이커가 반환하는 내부 폴백 추정치가 최신 v2.1 32차원 모델의 통계 분포와 완벽히 정합하도록 조율하고, 프론트엔드에 `⚠️ 실시간 API 점검 중 · 추정치 표시` 배지를 명확히 구분 표출.

---

### 🧭 0-2. 멀티모달 경로 탐색 물리/실시간 정밀화 4대 과제 (Backlog · 2차 고도화)

> **문서 일원화 안내**: 기존 `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`에 기록되었던 잔여 경로 탐색 정밀화 과제를 본 섹션으로 공식 이관·통합하였습니다. 경로 탐색의 정확도 및 체감 품질을 극대화하기 위한 4대 과제와 가성비(Impact vs Effort)는 아래와 같습니다.

- [x] **[ROUTING-01 · P1 · Quick Win · 가성비 1위] 환승역별 실제 환승통로 도보 거리 및 소요시간 반영 (완료 · 2026-10-29 · 이슈 #47)**:
  - **현황**: `multimodal_router.py`, `subwayGraph.ts`에서 모든 환승역의 도보 환승시간을 일괄 `2.0분`으로 고정하여, 김포공항·복정 등 개념환승(`0.5~1.0분`)과 고속터미널·노원·종로3가 등 장거리 환승(`5.0~8.0분`) 간의 큰 편차가 무시됨.
  - **개선 방안**: 서울교통공사 실측 공공데이터(서울 열린데이터광장 `OA-13290`, 공공데이터포털 `15044419`, 기준속도 1.2m/s)를 기반으로 93개 호선별 환승 쌍(`models/station_transfer_times.json`, `stationTransferTimes.json`)을 구축하고, `(역명, 출발호선, 도착호선)` 튜플 기준으로 실제 도보시간(`0.5~8.0분`) 및 환승 거리(m)를 다익스트라 가중치(`trWalkPenalty = walkMinutes * 1.5`) 및 프론트엔드 세그먼트 상세 안내에 반영. (상세 규격: `docs/CURRENT_DATA_SPEC.md` §7 참조)
  - **기대 효과**: 환승 시간 왜곡을 해소하고 '막장 환승역'(노원 6.2분, 고속터미널 4.5분 등)을 자동 회피하며 '개념 환승역'(김포공항 0.5분 등)을 우선 선택하도록 최적화 완료.

- [x] **[ROUTING-02 · P1 · Core · 핵심 기능] 버스+지하철 복합경로 실노선/환승 API 연동 (`getPathInfoByBusNSub`) (완료 · 2026-10-29 · 이슈 #50)**:
  - **현황**: `multimodal_router.py`에서 출발역 반경 850m 버스정류소부터 지하철 중간 환승역까지의 구간을 단순 직선거리×1.25 및 평균속도(20.4km/h)로 임의 추정하고, 상위 2개 노선 번호(또는 기본값 '143, 402')를 단순 표출함.
  - **개선 방안**: 서울시 대중교통환승경로 조회 서비스(`getBusSubwayPathList`, 공공데이터포털)를 연동하여, 출발지-중간역 간 실제 운행 버스 노선 번호(`routeNm`), 승하차 정류소 ID(`fid`, `tid`), 실측 소요시간 및 실시간 버스 도착 대기시간(`arrmsg1`)을 세그먼트에 바인딩하고, 신규 엔드포인트 `GET /api/v1/transit/bus/transfer-path` 개설 및 지도 승하차 핀(`route-bus-pickup-pin`, `route-bus-drop-pin`) 시각화 완료. API 실패 또는 비서울 이동 시 인근 버스 정류소 복도(Corridor) 기반 Heuristic Fallback 유지.
  - **기대 효과**: 복합 환승 경로 추천에서 '가짜 버스 노선' 문제를 완전히 해소하고 실시간 버스 도착시간을 결합한 신뢰도 100% 경로 제공.

- [ ] **[ROUTING-03 · P2 · High Impact · 체감 효과] 지하철 급행(Express) 열차 운행 다이어 및 정차역 스킵 분리**:
  - **현황**: 9호선 급행, 1호선 경인/경부선 급행, 공항철도 직통 등이 완행 노선과 분리되지 않아 모든 중간역 정차로 계산됨 (예: 김포공항➔신논현 9호선 급행 탑승 시 실제보다 12~15분 과대 산출).
  - **개선 방안**: 급행 정차역 목록 및 급행 전용 스킵 간선(Skip Edge)을 구축하고, 급행 배차간격(`10~15분`)을 반영하여 다익스트라 탐색 시 일반열차와 급행열차의 효용을 비교 평가해 `🚇 9호선(급행)`으로 분기 추천.
  - **기대 효과**: 9호선·1호선 통근 이용자에게 최대 15분 이상 단축되는 현실적인 최적 급행 경로 추천.

- [ ] **[ROUTING-04 · P2 · Visual Polish · 후순위] 도보 및 따릉이 구간 실도로망(Pedestrian/Bike Street Network) 연동**:
  - **현황**: 도보 및 따릉이 구간을 `Haversine 직선거리 × 1.25`로 산출하고 지도 폴리라인도 단순 직선 선분으로 연결함 (한강 도하, 철도/하천 단절, 오르막 감속 미반영).
  - **개선 방안**: 오픈소스 OSRM(보행자/자전거 프로필) 엔진 또는 외부 보행자 경로 API를 연동하여 실제 자전거길/보행로 GeoJSON 및 실도로 거리·소요시간 반영.
  - **기대 효과**: First/Last-Mile 지도 폴리라인이 실제 도로망을 따라 유려하게 표시되며 단절 지형 우회 반영.

---

### 📱 1. 모바일 UI / UX 반응형 최적화 (Next Sprint / 예정)
- [ ] **모바일 레이아웃 & 뷰포트 대응**:
  - 스마트폰(iOS Safari, Android Chrome) 및 태블릿 세로 모드 해상도 맞춤 반응형 레이아웃 구현
  - 상단 헤더 메뉴의 모바일 최적화 (모바일용 햄버거 메뉴 또는 하단 고정 탭바 `Bottom Navigation Bar`)
- [ ] **지도(Map) 모바일 터치 인터랙션 고도화**:
  - PC용 좌측 사이드패널 대신 모바일 친화적인 **바텀 시트(Bottom Sheet / 드래그 스와이프 제스처)** UI 적용
  - 지도 핀/알약 마커 터치 영역(Touch Target) 최소 44x44px 확보 및 핑거 줌/팬 조작감 개선
- [ ] **경로 추천 및 검색 UI 모바일 최적화**:
  - 모바일 가상 키보드 오픈 시 검색 결과 리스트가 가려지지 않도록 뷰포트 높이(`dvh`) 동적 계산
  - 역 검색 모바일 풀스크린 모달 또는 하단 시트 검색창 지원
- [ ] **실시간 도착 정보 & 날씨 카드 모바일 뷰**:
  - 작은 모바일 화면에서 열차/버스 도착 시간 및 날씨 정보를 한눈에 볼 수 있도록 컴팩트 카드 뷰 제공

---

### 🌐 2. 글로벌 및 접근성 확장 (Backlog)
- [ ] 외국인 관광객을 위한 다국어(영어/중국어/일본어) 인터페이스 지원
- [ ] 스크린 리더(VoiceOver/TalkBack) 및 웹 접근성(WAI-ARIA) 고도화

---

### 🛡️ 3. 시스템 안정성 및 장애 대응 (Backlog — 2026-10-14 **배포 검증 1건 완료**)
- [x] **(배포 검증 · 최우선) — 완료 (2026-10-14)** 컨테이너 실기동 확인 — `Dockerfile.backend` COPY 누락(`feature_schema.py` → ImportError) 결함을 2026-10-14 수정하고, **Docker Desktop 기동 후 재빌드·실기동 검증까지 완료**
  - **실측**: `docker compose up -d --build` → `backend` **`healthy`**(24초 내 · `8100→8000`) · `frontend` Up(`3100→80`) · 기동 로그 `[schema] 피처 스키마 검증 통과: model_version=v2-전처리_2-32d | 32차원 | 출처=/app/benchmarks/2026-10-14/feature_schema.json` → **ImportError 없음** · 3세션 warmup(`input dim: 25`) 완료
  - **엔드포인트 6종 200**: 직접 `GET /health` · `POST /api/v1/predict/recommendation`(추론 6.6ms · 추천 3건) · `GET /api/v1/districts/live-congestion`(7.8ms) / Nginx 경유 `:3100/health`·`:3100/api/v1/predict/recommendation` / SPA `:3100/`(text/html) · 백엔드 로그 ERROR·Traceback 0건
  - **주의(당시 상태 · 이후 해소)**: 위 검증 시점의 `/health.feature_schema.status` 는 **`legacy-subset-25d`**(배포 모델 25차원 + 스키마 32차원 = 레거시 서브셋 정렬 정상)였습니다 → **2026-10-14 `models/` 전면 32차원 교체로 `verified` 로 승격**(§4 · `tests/test_feature_schema.py` Test 7 기대값도 `verified`/dims `{32}` 로 갱신)
  - 재검증 절차: `docker compose up -d --build` → `docker compose ps`(`backend` = `healthy`) → `GET /health`(스키마·차원 확인) → `docker compose logs backend`(`[schema]` 라인) → `python tests/test_feature_schema.py` · `python tests/test_inference.py` · `python tests/test_api.py`
  - 실패 시 확인 지점: `main.py` import 목록 ↔ `Dockerfile.backend` COPY 목록 · 스키마 탐색 경로(`--schema`/`FEATURE_SCHEMA_PATH` → `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json`)
  - 참고: `docs/DOCKER_CONTAINERIZATION_PLAN.md` §5 Phase 4-5·4-6 · `docs/CHANGELOG.md` [2026-10-14] §3
- [x] **백엔드 독립형 실시간 로그 확인 및 헬스체크 모니터링 대시보드 (`/health/dashboard`) 구축 (완료 · 2026-10-29 · 이슈 #53)**:
  - 일반 사용자 화면과 완전 격리된 단독 웹 대시보드(`http://localhost:3100/health/dashboard`) 제공.
  - 외부 공공 API 4종(기상청, 버스, 지하철, 따릉이) 헬스 및 서킷 브레이커 실시간 관제.
  - 최근 `2,000건`의 실시간 서버 로그를 비차단 스레드 안전(`RLock`) 순환 버퍼에 캡처하여 1.5초 주기 실시간 터미널 스트리밍, 다차원 필터링 및 원클릭 캐시 비우기 지원.
- [ ] 공공 API 서버 장애 시 자동 Fallback 서킷 브레이커 고도화
- [ ] Redis 기반 분산 캐시 레이어 도입 (대규모 트래픽 대비)

---

### 🤖 4. 32차원 실피처 모델 신규 학습 및 검증 (**전면 32차원 교체 실행·검증 완료** · 2026-10-14)

> **배경**: 2026-10-13 파이프라인 v2 개정으로 학습·평가 기준이 **실제 32차원 실피처(8/8/5/11)** 로 확정되었고, **2026-10-14 Colab 실행으로 32차원 모델 3종 학습이 완료되어 `benchmarks/2026-10-14/` 에 반입되었습니다.** (커밋 `07292b4`)
> - **반입 자산**: `lgb_{bike,bus,subway}_demand.onnx`(ONNX 입력 `[None, 32]`, 이름 `float_input`) + `feature_schema.json`(`model_version: v2-전처리_2-32d`)
> - **선행 검증(완료)**: `feature_schema.json.feature_cols`(32개) == `benchmarks/evaluate_models.py::FEATURE_COLS_32` == `main.py::build_feature_vector` 인덱스 0~31 → **순서 완전 일치**. 공휴일 캘린더 **19일** 일치(`main.py::KR_HOLIDAYS`)
> - **노트북 기록 Test 지표**(`2025-11-16 ~ 2025-12-31`, n=26,450) — 평가 스크립트 교차검증 **통과**(재현성 확인): bike R² 0.98729 / bus 0.99006 / subway 0.99515
> - `benchmarks/2026-10-12/tuned_real/` 은 **안내 README 만 남은 종료된 배치 위치**입니다(신규 산출물은 `2026-10-14/`).
> **관련 문서**: [데이터 전처리 인수인계서](./DATA_PREPROCESSING_HANDOFF.md) · [모델 성능 비교 보고서](./MODEL_PERFORMANCE_REPORT.md) §0 · `benchmarks/README.md` §4.2 · [`benchmarks/2026-10-14/README.md`](../benchmarks/2026-10-14/README.md)

- [x] **학습 실행 (Colab / RunPod)** — `benchmarks/CastTransit.ipynb` [Cell 1] → [Cell 7] 순차 실행 (2026-10-14 완료)
  - [Cell 6-1] Optuna 튜닝(30 trials) + [Cell 7] ONNX export + `feature_schema.json` 생성
  - 결과: `best_iteration` bike 834 / bus 1,390 / subway 865 · 튜닝 파라미터는 `feature_schema.json::metrics.*.tuned.best_params` 참조
- [x] **산출물 배치** — `lgb_{bike,bus,subway}_demand.onnx` + `feature_schema.json` → `benchmarks/2026-10-14/` (2026-10-14)
- [x] **평가 재실행 (즉시 · P0)** — `python benchmarks/evaluate_models.py` (2026-10-14 완료 → `benchmarks/results/comparison_20261014_184621.{json,md}`)
  - `evaluate_models.py::MODEL_SETS` 의 `tuned_32d_real` 기본 경로를 `benchmarks/2026-10-14/` 로 갱신 완료 → `--model` 없이 실행하면 신규 32차원 모델이 자동 포함됩니다
  - 확인 항목: 피처 결측 0 / 공휴일 10,925행(5.21%) / test 26,450행 / 32차원 레이아웃(8/8/5/11) 일치
  - **교차검증(Gate) — 통과 (2026-10-14)**: 노트북 기록치와 **소수점 수준 일치**(bike R² 0.98729→0.9873 / bus 0.99006→0.9901 / subway 0.99515→0.9951, RMSE 오차 ≤0.006) → 파이프라인 재현성 확인
  - 결과: `benchmarks/results/comparison_20261014_184621.{json,md}` 에 `tuned_32d_real` 3행 추가

| 수단 | 배포본 25차원 (R²/RMSE/MAE) | 후보 32차원 (R²/RMSE/MAE) | MAPE(≠0) 배포→후보 | 판정 |
| :---: | ---: | ---: | ---: | :--- |
| 🚲 bike | 0.9887 / 16.372 / 9.815 | 0.9873 / 17.382 / 9.669 | 16.74% → 16.37% | ⚠️ R²·RMSE 열세 |
| 🚌 bus | 0.9897 / 571.741 / 369.300 | 0.9901 / 561.358 / 370.444 | 14.53% → 18.09% | ⚠️ MAPE 열세 |
| 🚇 subway | 0.9924 / 826.324 / 369.732 | 0.9951 / 662.095 / 277.633 | 5.51% → 4.24% | ✅ 전 지표 우세 |
- [x] **성능 보고서 갱신** — `docs/MODEL_PERFORMANCE_REPORT.md` §0.2·§7 에 32차원 실측 수치 반영 완료(2026-10-14)
  - v1 결론("개선은 전부 Optuna 튜닝 효과, 차원 증가 효과는 없음")은 v2 실피처에서 **부분 수정됨** — 지하철은 전 지표 개선(MAE −24.9%), 따릉이는 R²·RMSE 열세, 버스는 MAPE 열세. 즉 "차원 증가 = 무의미"는 실피처 32차원에서 더 이상 일반화되지 않습니다(단, 교란 3중으로 인과 귀속은 불가)
  - **해석 주의(교란 3중)**: 신규 후보는 ① 32차원 ② Optuna 튜닝 ③ 신규 원천(`전처리_2`)이 **동시에** 바뀐 모델이고, 배포본은 구 원천·25차원입니다. 순수 "차원 증가 효과"는 아래 25차원 재학습으로만 분리됩니다
- [x] **배포 판단 (Gate) — 전면 교체 보류 (2026-10-14)** — 3수단 전부 유의 우세 조건 **미충족**(bike R²·RMSE 열세 / bus MAPE 열세 / subway 우세) → 당시 **`models/` 는 25차원 유지** → ⚠️ **후속: §4 상단의 전면 32차원 교체로 확정(2026-10-14)**
  - 다음 단계: **수단별 교체 검토**(지하철 우선) 또는 **25차원 재학습 결과와 비교** 후 확정
- [x] **전 세대(3종) 동시 비교 실행 (2026-10-14)** — 평가 스크립트에 **라벨별 피처 배치**(`MODEL_LAYOUTS` + `--layout LABEL=v1|v2`)를 도입해 구 후보(v1 배치)까지 **자기 배치로** 비교 → `benchmarks/results/comparison_20261014_192204.{json,md}` (4-way 확장, 구 `190055` 대체)
  - v1 배치 행렬은 **25차원 서브셋 + 상수 0 더미 7** 로 재현(구 스크립트 `ef1d03d` 의 `FEATURE_COLS` + `infra_dummy_0..6` 정의와 일치 확인) · 레거시 자산은 `is_holiday = 0` 참고치 병기
  - **교차검증 통과**: 구 v1 프레임 보고치 재현 — bike R² **0.9893** / subway R² **0.9940** 동일, subway MAE 개선폭 **−19.2%** 동일 → v1 배치 재구성 정확. (bus 만 프레임 차이로 이동: R² 0.9908→0.9923 — 배포본도 0.9882→0.9897 로 같은 방향)
  - **결과**: v1 이 **12개 지표 전부 배포본보다 우세**(MAE bike −4.4% / bus −15.4% / subway −19.2%) · **동일 프레임 v1 vs v2 직접 비교 시 bike·bus 는 v1, subway 는 v2 우세**
  - ⇒ **우선순위 변경**: ① **25차원 재학습(v2 파라미터) 최우선**(v1 = 그 서빙 가능 버전의 기대치) → **2026-10-14 실행 완료**(아래 항목), ② 수단별 교체는 **지하철 단독**만 근거 있음
  - 리포트에 **배포본 대비 델타 표**·**SHA256 자산 무결성** 절 자동 생성(`models/` ≡ `benchmarks/original/` **동일 자산** 검출)
  - ⚠️ v1 은 **서빙 불가**(32차원 모델에 32차원 실피처 벡터가 그대로 들어가면 인덱스 17 이후 어긋남) → **판단 보조 지표**로만 사용
  - 교체 확정 시: `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 의 "25차원 부분집합" 서술 정리
  - 교체 후 검증: `python tests/test_inference.py`(32차원 정합성·레이턴시 SLA) · `python tests/test_api.py`
- [ ] **해석 주의 (P0-1 미해결)** — 테스트 구간 `버스_승차` 결측 24.59%(8,625행 보간) 영향으로 **버스 수치는 잠정치**. 원천 재수집 또는 평가구간 축소 합의 후 확정
- [x] **차원 vs 튜닝 분리 실험 (2026-10-14 완료)** — 동일 `study.best_params` 고정 + **25차원 서빙 서브셋** 재학습 → 4-way 재비교 (`benchmarks/results/comparison_20261014_192204.{json,md}`)
  - 도구: `benchmarks/retrain_25d.py` (스키마 SSoT 의 `metrics.*.tuned.best_params` 소비, `--export` 로 ONNX·25차원 스키마 반출) → 산출물 `benchmarks/2026-10-14/tuned_25d/`
  - **결과**: 튜닝 파라미터를 고정하고 25차원으로 줄여도 배포본을 상회 — bus MAE −26.6 / subway MAE −38.9 / bike MAE −0.138·MAPE −0.54%p → **개선분의 대부분은 튜닝 효과**(v1 결론과 일치). 32차원 증가의 **순수 효과는 🚇 지하철에서만**(v2 32d 가 25d 재학습 대비 R² +0.0017 · MAE −53.2) 확인
  - ✅ **Colab 재현 편차 0 (2026-10-14 완료)** — Colab 산출물 `tuned_25d_colab/` 과 `best_iteration` bike 680 / bus 1,498 / subway 446 · **12개 지표 Δ = 0**(아래 Colab 항목)
- [x] **`feature_schema.json` SSoT 소비 (2026-10-14 완료)** — 평가 스크립트·서빙이 스키마를 읽어 **차원·순서를 assert** 하도록 전환(피처 불일치 재발 원천 차단)
  - `feature_schema.py` 신설(탐색: `--schema` 인자 → `FEATURE_SCHEMA_PATH` → `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json`) · 서빙 기동 시 **스키마 ↔ `FEATURE_ORDER_32` ↔ ONNX 입력 차원 3중 대조**(`/health.feature_schema`, 불일치 시 기동 중단) · 평가는 `verify_feature_schema` 로 순서·타깃·분할 경계 assert 후 리포트에 기록
  - `tests/test_feature_schema.py` **8종 통과**(규격·3자 순서 일치·25차원 서브셋·ONNX 자산 차원·타깃/분할/공휴일·네거티브 가드·`/health` 노출·컨테이너 배포 파일 목록)
- [x] **`models/` 교체 판단 — 전면 32차원(사양서 배치) 반입·실행·검증 완료 (2026-10-14)** — `benchmarks/2026-10-14/lgb_{bike,bus,subway}_demand.onnx` → `models/` **파일 단위 반입**(SHA256 `A6854BC6…`/`983A069B…`/`264E822F…` · 7,020,769 / 13,596,760 / 7,345,447 byte). **스키마는 반입하지 않음** — 현행 32차원 SSoT(`benchmarks/2026-10-14/feature_schema.json`)가 그대로 사용되어 `/health.feature_schema.status` 가 **`verified` 로 자연 승격**
  - **검증(2026-10-14)**: 회귀 테스트 6종 전부 통과(`test_feature_schema` 8종 · `test_inference` 추론 SLA **1.91ms** < 15ms · `test_api` · `test_mcda_calibration` · `test_timeseries_cache` · `test_station_pipeline`) · `docker compose up -d --build` → backend **`healthy`**(`8100→8000`) · 기동 로그 `[schema] {bike,bus,subway}: 입력 32차원 — 스키마 정렬 OK` + 3세션 warmup(`input dim: 32`) · **레거시 서브셋 경고 소멸** · ERROR·Traceback 0건 · 엔드포인트 6종 200(`/health` = `verified`·dims `{32,32,32}` · 추천 10.83ms · live-congestion 14.67ms · Nginx 경유 2종 · SPA)
  - **감수한 트레이드오프(명시)**: 배포본 25d 대비 🚇 subway 전 지표 우세(MAE −24.9% / RMSE −19.9%) ↔ 🚲 bike R² −0.0014 · RMSE +6.2% / 🚌 bus MAPE +24.5% 상대(P0-1 결측 보간으로 **잠정치**) → **지하철 정확도·규격 정합성·배치 단일화 우선**으로 결정
  - **롤백**: `Copy-Item benchmarks\original\lgb_{bike,bus,subway}_demand.onnx models\ -Force`(25차원 원복) → `status=legacy-subset-25d` 복귀 + `tests/test_feature_schema.py` Test 3·4·7 기대값 원복(주석에 절차 명시)
  - (판단 재료 이력) 4-way/5-way 리포트 — bus·subway 는 전 지표 개선 / bike 는 R²·RMSE 소폭 열세(MAE·MAPE 우세) → **수단별 교체(지하철·버스 우선)** 또는 bike 제외 논의 · Colab 재현본 `tuned_25d_colab/` 은 `tuned_25d` 와 **지표 완전 동일**이라 판단에 영향 없음
  - 교체 규약: `models/lgb_{bike,bus,subway}_demand.onnx` **만** 반입(파일 단위 수단별 교체 가능) → 32차원 자산을 넣으면 `status=verified`, 25차원 자산을 넣으면 `legacy-subset-25d`(스키마는 32차원 SSoT 유지) · 교체 후 `python tests/test_feature_schema.py` · `python tests/test_inference.py` · `python tests/test_api.py`
  - ⚠️ **`models/feature_schema.json` 슬롯에 25차원 스키마를 넣지 마세요** — `feature_schema.py::validate_expected_order` 가 스키마 == `main.py::FEATURE_ORDER_32`(**32차원 완전 일치**)를 요구하므로, 25차원 스키마(`tuned_25d/feature_schema.json` = `v2-전처리_2-25d-retrain`)를 배포 슬롯에 두면 **기동이 중단**됩니다(2026-10-14 실측: `validate_expected_order → FAIL`). `verified` 는 **32차원 자산 + 32차원 스키마**일 때만 나옵니다.
  - 교체 확정 시 문서 정리: `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 의 "25차원 = 32차원 − 7" 서술 기준 모델 갱신
  - 롤백·대안 자산: `benchmarks/original/`(25차원 배포본 스냅샷) + `benchmarks/2026-10-14/tuned_25d/`(25차원 재학습 — bus·subway 우세, 수단별 대안) · 배포 슬롯 `models/` 는 이제 `benchmarks/2026-10-14/` 와 SHA256 동일(구 배포본과는 상이)
- [x] **교체 승인 기준(Gate) 확정 (2026-10-14)** — **전면 32차원(사양서 배치) 교체**로 확정(전면 보류·수단별 기준안 폐기). 승인 사유: ① 규격 정합(`verified`)·배치 단일화 ② 🚇 지하철 전 지표 우세 ③ 서빙 경로 실검증(테스트 목적). 🚲 RMSE +6.2% · 🚌 MAPE +24.5%(잠정) 열세는 **명시적 트레이드오프로 수용**. 재판정 트리거: P0-1(버스 결측 24.59%) 해소 후 버스 재학습·재평가 · 배포 직후 콜드 캐시(≤7일) 구간 실사용 지표 확인
  - 근거: `docs/MODEL_PERFORMANCE_REPORT.md` §0.3·§0.4 · `benchmarks/results/comparison_20261014_192204.{json,md}`
- [x] **Colab 재현 — 완료 (2026-10-14)** — 동일 실험 스펙을 Colab 에서 재실행해 `best_iteration`·지표 편차(플랫폼 차이) 확인 (로컬 lightgbm 4.7.0 기준값)
  - **도구: `benchmarks/retrain_25d_colab.ipynb` 신설** — Colab 이 `.py` 파일 업로드/모듈 import 를 지원하지 않는 제약 때문에 **노트북 1개만 업로드**하면 끝나도록 설계: 레포의 `benchmarks/CastTransit.ipynb` 에서 전처리 셀 4개(`[Cell 3]`/`[Cell 4-A]`/`[Cell 4-B]`/`[Cell 5]`)를 **태그로 찾아 그대로 exec**(피처 드리프트 0) → `[Cell 6-1]` Optuna(seed 없음)는 **건너뛰고** 스키마 SSoT 의 v2 `best_params` 를 고정 주입(비교 가능성 유지·약 20분 절약)
  - 실행: `[Step 0]` 패키지/버전 기록 → `[Step 1]` Drive 마운트·레포 확인 → `[Step 2]` 원본 셀 exec → `[Step 3]` 25차원 재학습 → `[Step 4]` ONNX 3종 + 25차원 스키마 반출(`benchmarks/2026-10-14/tuned_25d_colab/`, **로컬 `tuned_25d/` 덮어쓰기 금지**) → `[Step 5]` 대조 표
  - 평가(5-way, 2026-10-14 실행 완료): `python benchmarks/evaluate_models.py --model tuned_25d_colab=benchmarks/2026-10-14/tuned_25d_colab --model tuned_25d=benchmarks/2026-10-14/tuned_25d`
  - **로컬 선검증(2026-10-14)**: 노트북 셀 로직을 로컬에서 exec 해 지표·`best_iteration` 이 `retrain_25d.py` 값과 완전 일치(bike 680 / bus 1,498 / subway 446, ΔR² 0.0000) · 반출 ONNX 는 하네스가 `dim=25`·`layout=25d-subset` 으로 자동 판별 → 남은 리스크는 플랫폼 편차뿐이었음
  - ✅ **Colab 실실행·반입 검증 완료(2026-10-14)** — 반출 파일 4개를 `benchmarks/2026-10-14/tuned_25d_colab/` 에 반입 → 5-way 리포트 `benchmarks/results/comparison_20261014_214856.{json,md}`
    - **플랫폼 편차 0**: R²·RMSE·MAE·MAPE·`best_iteration` **12개 지표 전부 Δ = 0.000000** + `best_params`·25차원 피처 순서 일치 · ONNX **파일 크기 3종 동일**(5,709,941 / 14,574,454 / 3,713,077 · 직렬화 메타 차이로 SHA256 만 상이)
    - Colab 환경(스키마 `env` 자동 기록): python 3.13.16 · **lightgbm 4.7.0(로컬과 동일)** · numpy 2.1.3 · pandas 2.2.3
    - ⇒ `tuned_25d` ≡ `tuned_25d_colab` **동일 모델** → `models/` 교체 판단 근거 변동 없음(잔여: P0-1 버스 잠정치 · 교체 Gate 확정)
- [ ] **(데이터팀 회신 대기)** P1-1 파생 피처 7종 CSV 포함 시 노트북 하드코딩 재구성 로직 제거
- [ ] **(데이터팀 회신 대기)** P1-3 결측 대체 정책 확정 시 노트북 대체 규칙 1:1 일치화
---

### 🧠 5. LangGraph 및 FactChat LLM 기반 멀티모달(지하철+버스+따릉이) 통합 경로 탐색 엔진 구축 (이슈 #18 — **구현·검증 완료** · 2026-10-28)

> **배경**: 현재 프론트엔드의 경로 탐색 기능은 `subwayGraph.ts` 기반 단일 지하철 역-역 경로만 지원하고 있으나, 실제 도심 이동은 "출발지 ➔ (따릉이/도보) ➔ 지하철 ➔ (환승) ➔ 버스 ➔ 목적지"의 First/Last-Mile 복합 이동이 필수적임. 특히 날씨 실황과 AI 예측 혼잡도를 고려하여 우천 시 따릉이를 자동 배제하고 지하철 최소 환승 경로를 유도하는 지능형 오케스트레이션 엔진 구축 필요.

- [x] **백엔드 LangGraph & 외부 LLM(FactChat API) 파이프라인 구축 (2026-10-28 완료)**:
  - `langgraph`, `langchain-core` 의존성 추가 및 OpenAI 호환 Gateway(`FACTCHAT_API_BASE_URL`, `FACTCHAT_API_KEY`) 연동
  - 멀티모달 상태 그래프(`StateGraph`) 정의 및 우천 시 따릉이 자동 배제 조건부 분기(Conditional Edge) 설계
  - 에이전트 전용 4대 도구(Tools) 구현: 지하철 경로 도구, 실시간 버스 도착 도구, 따릉이 잔여 대여소 도구, 32차원 AI 혼잡도 예측 도구
- [x] **통합 멀티모달 경로 탐색 API 엔드포인트 신설 (2026-10-28 완료)**:
  - `POST /api/v1/routes/multimodal-search`: 출발지/도착지 좌표 기반 수단별 이동 세그먼트, GeoJSON 폴리라인 및 FactChat LLM 맞춤형 환승 브리핑 반환
- [x] **다목적 효용 함수(Multi-Objective Utility Score) 및 물리·배차 정밀 검증 (2026-10-28 완료)**:
  - 무조건 따릉이를 1순위로 고정하던 문제를 해결하고 소요시간·환승·요금·혼잡도·기상을 종합한 효용 점수로 1순위 후보 동적 선정
  - 수도권 19개 노선별 주행 표정속도·역 정차시간(`LINE_OPERATING_SPECS`) 및 첨두/평시/심야 배차간격(`get_line_headway`) 반영, 서울 열린데이터광장 실시간 열차 도착 API(`get_subway_arrival`) 대기시간 주입
  - 정거장 수 off-by-one(`len(steps) - 1`) 교정 및 구간 소요시간 합계 == 총 소요시간(`total_minutes`) 100% 일치 보장
  - 서울특별시 행정구역(`is_in_seoul`) 경계 검증으로 부천(송내·중동)·인천(부평)·경기(수원·판교) 출발 시 서울시 전용 따릉이 추천 원천 차단 및 반경 850m 이내 거점만 매칭
- [x] **프론트엔드 복합 경로 추천 UI, 로컬 캐싱 및 지도 시각화 연동 (2026-10-28 완료)**:
  - `App.tsx`, `AppM.tsx`, `MultimodalRoutePanel.tsx` 경로 추천 탭 개편 (도보 ➔ 따릉이 ➔ 지하철 ➔ 버스 복합 타임라인 카드 및 F12 콘솔 5단계 트레이스 출력)
  - 인메모리 + `localStorage`(`weather_transit_multimodal_cache_v3`) 이중 캐싱으로 `지도` ↔ `경로 추천` 탭 전환 시 재로딩 없이 0ms 즉시 복원
  - `TransitMap.tsx` 지도 상 복합 이동 수단별 색상 구분 폴리라인 및 출발/도착 알약 마커 중복 노출 제거
- [x] **문서화 및 환경 설정 (2026-10-28 완료)**:
  - `.env.example` FactChat 설정 추가 및 `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/TODO_MOCK_AND_UNVERIFIED_DATA.md` 갱신

---

### 🔍 6. 코드베이스 내 잔존 하드코딩·미검증 근사치·정적 폴백 데이터 전수 조사 및 수정 방안 (Audit & Remediation Roadmap)

> **전수 조사 기준일**: 2026-10-28  
> 상세 내역은 [`docs/TODO_MOCK_AND_UNVERIFIED_DATA.md`](./TODO_MOCK_AND_UNVERIFIED_DATA.md) §6에도 동기화되어 있습니다. 현재 서비스 내에 남아 있는 **하드코딩 상수**, **물리·기하학적 근사 산식(미검증 추정치)**, **API 장애 대비 시뮬레이션 폴백 데이터**와 각각의 **구체적 수정 방안**은 아래와 같습니다.

#### 6.1 멀티모달 경로 탐색 엔진 (`multimodal_router.py`, `subwayGraph.ts`) 내 근사 산식 및 하드코딩 요소

- [ ] **[P1 · 버스+지하철 복합 경로(`route-bus-subway-hybrid`) 실노선/환승 API 미연동]**
  - **현황 (`multimodal_router.py` L1315~L1375)**:
    - 출발역 반경 850m 이내 버스정류소(`models/transit_network.json` 등록 25개 거점 또는 미매칭 시 합성 정류소 `{출발역}환승정류소`)에서 지하철 경로의 약 1/3 지점 중간 환승역(`mid_idx`)까지 **직선거리×1.25 및 평균 버스 표정속도(20.4km/h)**로 이동시간을 추산함.
    - 버스 노선 번호 역시 실제 해당 정류소에서 중간 환승역까지 운행하는 노선인지 검증하지 않고 정류소 메타데이터(`lines`)의 상위 2개 번호(또는 기본값 `'143, 402'`)를 표출함.
  - **수정 방안**:
    1. 공공데이터포털 **서울특별시 대중교통환승경로 조회 서비스(`getBusSubwayPathList`, `15000414`)** 또는 국토교통부 TAGO / ODsay 대중교통 API를 `multimodal_router.py`의 `clear_multimodal_tools_node` 및 `rain_safe_tools_node`에 직접 연동.
    2. 출발지 좌표(`fx, fy`)와 중간/목적지 좌표(`tx, ty`) 간 실제 운행 중인 버스 노선 번호(`routeNm`), 탑승/하차 정류소 고유 ID(`fid`, `tid`), 실측 소요시간(`time`) 및 정류장 수(`busStationCount`)를 수신하여 세그먼트 구성.
    3. 탑승 정류소의 `stId`로 `get_bus_arrival(stId)`를 호출하여 지하철과 동일하게 **실시간 버스 도착 대기시간(`arrmsg1`)**을 첫 구간에 반영.

- [ ] **[P1 · 환승역별 실제 환승통로 도보 거리 및 소요시간 편차 미반영 (일괄 2분 고정)]**
  - **현황 (`multimodal_router.py` L695, `subwayGraph.ts` L135)**:
    - 노선 환승 시 역 구조와 무관하게 **환승통로 도보 이동시간을 일괄 `2.0분`**(+ 환승 노선 평균 대기시간 `headway / 2`)으로 고정 계산 중.
    - 실제로는 김포공항역·금정역·복정역 같은 평면 개념환승(`약 0.5~1.0분`)과 노원역·고속터미널역·홍대입구역·종로3가역·서울역(공항철도↔1/4호선) 같은 장거리 환승(`약 5.0~8.0분`) 간 편차가 큼.
  - **수정 방안**:
    1. 서울교통공사 및 한국철도공사의 **환승역 환승거리 및 소요시간 공공데이터(`서울교통공사_환승역 환승거리 및 소요시간 정보`)**를 `models/station_transfer_times.json`으로 반입.
    2. `(역명, 출발호선, 도착호선)` 튜플 키로 실제 환승 도보 분(`transfer_walk_min`)을 조회하여 다익스트라 간선 가중치(`transferPenalty`)와 세그먼트 상세 안내에 반영.

- [ ] **[P1 · 지하철 급행(Express) 열차 운행 다이어 및 정차역 스킵 미분리]**
  - **현황 (`multimodal_router.py` L660~L730, `subwayData.ts`)**:
    - 9호선 급행, 1호선(경인·경부선 급행), 공항철도 직통열차, 경의중앙선·수인분당선 급행 노선이 일반(완행) 열차 그래프와 분리되어 있지 않아 모든 중간역에 정차하는 것으로 정거장 수와 소요시간을 산출함 (예: 김포공항➔신논현 9호선 급행 탑승 시 실제보다 약 12~15분 길게 산출).
  - **수정 방안**:
    1. `subwayData.ts` 및 `models/transit_network.json`에 급행 정차역 리스트(`EXPRESS_STOPS_BY_LINE`: 9호선 급행, 1호선 급행, 신분당선 등)와 급행 전용 스킵 간선(Skip Edge)을 추가.
    2. 다익스트라 탐색 시 일반열차 경로와 급행열차 경로(급행 배차간격 `10~15분` 반영)를 모두 평가하여 급행이 유리할 경우 `🚇 9호선(급행)` 세그먼트로 안내.

- [ ] **[P2 · 도보 및 따릉이 구간 실도로망(Pedestrian/Bike Street Network) 미적용]**
  - **현황 (`multimodal_router.py` L572~L595, L1115~L1195)**:
    - 도보(Walk) 및 따릉이(Bike) 구간의 이동 거리를 `Haversine 직선거리 × 우회계수(1.22~1.28)`로 산출하고, 지도 폴리라인(`coords`)도 `[출발역, 대여소, 반납역]` 간 직선 선분으로 연결함.
    - 한강 교량 도하 구간이나 철도/하천 단절 지형에서 실제 자전거도로 우회 경로 및 경사도(오르막 감속)가 반영되지 않음.
  - **수정 방안**:
    1. 오픈소스 라우팅 엔진 **OSRM (`foot` / `bike` 프로필)** 또는 **Valhalla / 카카오모빌리티·TMAP 보행자/자전거 경로 API**를 백엔드에 연동.
    2. 실제 보행자/자전거 도로망 Geometry(GeoJSON LineString)와 실측 도로 거리·예상 소요시간을 받아 지도 폴리라인 및 세그먼트 시간에 바인딩.

#### 6.2 프론트엔드 초기 렌더링 상수 및 정적 메타데이터 (`App.tsx`, `AppM.tsx`, `TransitMap.tsx`)

- [x] **[P2 · `App.tsx` / `AppM.tsx` 초기 렌더링용 정적 상수 배열 분리 및 스켈레톤 UI 전환] (완료 · 2026-10-29 · 이슈 #29)**
  - **현황 (`Weather-Transport Recommendation UI/src/App.tsx` L156~L205)**:
    - `CORRELATION_DATA` (강수량 `0~5mm`별 수단 이용률 상수 배열 6건), `DEFAULT_24H_DATA` (API 응답 전 초기 차트 렌더링용 24시간 배열), `DISTRICT_DATA` (초기 8대 거점 기본 혼잡도 배열), `TRANSPORT_SCORES` (초기 기본 점수 배열)가 소스코드 상단에 하드코딩되어 있음.
    - 마운트 직후 백엔드 API(`/api/v1/transit/hourly-forecast`, `/api/v1/districts/live-congestion`, `/api/v1/predict/recommendation`) 응답으로 덮어써지지만, 네트워크 지연 시 초기 0.1~0.5초 동안 정적 기본값이 노출될 수 있음.
  - **수정 방안**:
    1. `DEFAULT_24H_DATA`, `DISTRICT_DATA`, `TRANSPORT_SCORES`를 하드코딩된 숫자 대신 **로딩 스켈레톤(Skeleton Shimmer UI)** 상태로 초기 렌더링하도록 변경하고, 정적 폴백 상수는 `src/constants/fallbackData.ts`로 격리하여 오프라인/에러 시에만 명시적 `Fallback 배지`와 함께 표시.
    2. `CORRELATION_DATA`는 백엔드에 `GET /api/v1/analytics/rain-correlation` 엔드포인트를 신설하여 20.9만 건 실측 데이터셋(또는 자치구별 회귀 계수)에서 동적으로 내려받도록 전환.

- [x] **[P2 · `TransitMap.tsx` 및 `bikeStopData.ts` / `busStopData.ts` 내 정적 대여소·정류소 ID 전수 검증] (완료 · 2026-10-29 · 이슈 #29)**
  - **현황 (`TransitMap.tsx` L120~L155, `bikeStopData.ts`, `busStopData.ts`)**:
    - `bikeStopData.ts`의 52개 거점 대여소 중 일부 `stationNo`가 서울시설공단 실시간 `bikeList` API의 최신 대여소 번호와 불일치할 수 있음 (현재 `TransitMap.tsx`에서 250m 거리 검증 후 `/api/v1/transit/bike/stations/nearby`로 동적 폴백 중).
    - `TransitMap.tsx` 내 버스 도착 조회 시 `stId`가 누락된 정류소에 대해 기본 폴백 ID(`'111000299'`) 또는 기본 노선(`'140'`, `'472'`)을 사용하는 방어 코드가 존재함.
  - **수정 방안**:
    1. `scripts/verify_stop_ids.py` 스크립트를 작성하여 서울시 `bikeList` 전체 대여소(약 2,700개) 및 서울시 버스정류소 마스터 데이터와 `bikeStopData.ts`·`busStopData.ts`·`models/transit_network.json`의 `stationNo`/`stId`/`arsId`를 전수 대조·자동 갱신.
    2. `stId` 미보유 정류소 클릭 시 하드코딩된 `'111000299'`로 폴백하지 않고, 정류소 위경도(`coords`) 기준 `/api/v1/transit/bus/stops/nearby`를 호출해 실제 최근접 정류소 `stId`를 동적 해석하도록 개선.

#### 6.3 백엔드 공공 API 장애 폴백 생성기 (`main.py`, `kma_forecast.py`) 및 데이터 파이프라인

- [x] **[P2 · 백엔드 시뮬레이션 폴백 응답(`generate_intelligent_*_fallback`)의 UI 배지 명확화] (완료 · 2026-10-29 · 이슈 #29)**
  - **현황 (`main.py` L910~L1035, L1490~L1530)**:
    - 공공 API 인증키 미설정, 일일 트래픽 초과 또는 외부 서버 장애 시 서비스 중단을 막기 위해 `generate_intelligent_subway_fallback()`, `generate_intelligent_bus_fallback()`, `_generate_fallback_bike_snapshot()`이 결정론적 해시(`hashlib.md5`) 기반 추정치를 반환함.
    - 응답 JSON에 `source: "SIMULATION_FALLBACK"`이 포함되어 있으나, 일부 프론트엔드 팝업/카드에서 실시간 공공 API 데이터와 동일한 디자인으로 표시될 수 있음.
  - **수정 방안**:
    1. 프론트엔드 도착 정보 팝업, 따릉이 팝업, 멀티모달 타임라인에서 `source`가 `SIMULATION_FALLBACK` 또는 `SCHEDULE_ESTIMATE`일 경우 `⚠️ 실시간 API 지연 · 시간표 기반 추정치` 배지를 명확히 구분 표출.

- [ ] **[P0-1 · 학습/평가 데이터셋 버스 승차 결측 구간(`2025-11-28 ~ 2025-12-31`) 원천 보완]**
  - **현황 (`docs/DATA_PREPROCESSING_HANDOFF.md`)**:
    - 테스트 구간(`2025-11-16 ~ 2025-12-31`) 중 11-28 이후 `버스_승차` 원천 결측(24.59%, 8,625행 시계열 보간)으로 인해 버스 ONNX 모델의 테스트 MAPE가 잠정치 상태임.
  - **수정 방안**:
    1. 서울 열린데이터광장 `서울시 노선별/정류장별 시간대별 승하차 인원 정보` 원천 API에서 2025년 `11월 말 ~ 12월` 구간을 재수집하여 보간 행을 실측치로 교체 후 `lgb_bus_demand.onnx` 재학습·재검증.


