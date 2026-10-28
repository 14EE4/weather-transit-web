# 📋 Frontend Changelog (프론트엔드 변경 이력)

> **상위 프로젝트**: [Weather & Transit Web](../../README.md)  
> **프론트엔드 가이드**: [Frontend README](../README.md)  
> **요구사항 명세서**: [REQUIREMENTS.md](../../docs/REQUIREMENTS.md)

---

## [2026-10-28]

### 📚 README 잔존 시뮬레이터 정비, API 테스트 문서 분리 및 docs 색인 체계화 (이슈 #21)
- **배경**:
  - 과거 코드에서 제거되었으나 문서 및 아키텍처 다이어그램에 남아있던 '가상 날씨 시뮬레이터(슬라이더 조작)' 잔존 문구를 실제 실시간 API 연동 체제에 맞춰 정비.
  - `README.md`에 길게 포함되어 가독성을 저해하던 공공 API 연동 테스트 출력 로그를 별도 전문 문서로 분리.
  - `docs/` 디렉토리에 분산된 핵심 기술 문서들을 일목요연하게 파악할 수 있는 공식 문서 색인(Documentation Index) 구축.
- **주요 조치**:
  1. **잔존 시뮬레이터 문구 및 다이어그램 정비 (`README.md`, `docs/SYSTEM_ARCHITECTURE.md`)**:
     - `README.md` 주요 기능 및 플로우차트 내 `UI3` 노드를 '실시간 기상 및 AI 추천 브리핑'으로 정비.
     - `docs/SYSTEM_ARCHITECTURE.md` 내 컨텍스트 다이어그램, 계층 다이어그램 및 §5.2 시퀀스를 '백엔드 가상 기상 배치 시뮬레이션 API'로 명확히 정비.
  2. **API 테스트 가이드 분리 (`docs/API_TEST_GUIDE.md` 신설)**:
     - 기상청, 서울 버스, 서울 지하철 실시간 OpenAPI 테스트(`test_api.py`) 및 AI 추론 통합 테스트(`test_inference.py`) 실행 방법, 실측 터미널 출력 결과, 장애 해결(트러블슈팅) 표를 수록한 전용 가이드 신설.
     - `README.md`의 테스트 섹션을 간결화하고 해당 가이드로의 바로가기 링크 제공.
  3. **README 내 핵심 기술 문서 색인(Index) 표 수록 (`README.md`)**:
     - 아키텍처, AI 모델 사양서, 성능 보고서, 백엔드 서버, API 테스트, 데이터 전처리, Docker 배포, 변경 이력, 프론트엔드 등 총 10개 핵심 문서에 대한 일람표(문서명, 핵심 내용, 바로가기 링크) 수록.
- **산출물**:
  - `README.md`
  - `docs/SYSTEM_ARCHITECTURE.md`
  - `docs/API_TEST_GUIDE.md` (신규)
  - `docs/CHANGELOG.md`

### 🔗 웹페이지 GitHub 링크 추가 및 README 작품 개요 수록 (이슈 #15)
- **배경**:
  - 사용자 및 평가자가 웹 대시보드에서 프로젝트 소스 코드 및 문서 저장소로 즉시 이동할 수 있도록 상단 네비게이션 헤더에 GitHub 바로가기 링크 추가 필요.
  - 팀 선견지명의 모빌리티 다양화, 기상 민감도, 지역별 수급 불균형 문제 해결 배경을 담은 작품 개요(선정 동기, 개발 목적, B2B/B2C 기대 효과)를 `README.md`에 공식 수록.
- **주요 조치**:
  1. **프론트엔드 GitHub 바로가기 (`App.tsx`)**:
     - 상단 헤더 우측 유틸리티 영역에 GitHub SVG 공식 아이콘과 저장소 링크(`https://github.com/14EE4/weather-transit-web`, `target="_blank"`, `rel="noopener noreferrer"`) 버튼 추가. 호버 인터랙션 적용.
  2. **README.md 작품 개요 수록 (`README.md`)**:
     - 팀 선견지명의 선정 동기(PM 기상 민감도 및 모달 시프트, 수급 불균형), 개발 목적(AI 예측 모델 + 20.9만 건 교통·기상 빅데이터), 필요성 및 기대 효과(B2B 기기 사전 재배치/자원 낭비 최소화, B2C 안전·쾌적 이동) 명시.
- **산출물**:
  - `Weather-Transport Recommendation UI/src/App.tsx`
  - `README.md`
  - `docs/CHANGELOG.md`

### 📊 AI 학습 파라미터, 11월 클린 테스트 바운더리 및 전체 시스템 플로우차트 문서화 (이슈 #16)
- **배경**:
  - 모델 재학습 및 최적화(Cell 6-1)를 통해 확정된 수단별 Optuna 최적 하이퍼파라미터와 최종 학습 설정(조기종료, 트리 수) 및 평가 지표를 공식 사양서 및 성능 보고서에 동기화할 필요성 대두.
  - 11월 말~12월 원천 버스 승차량 데이터의 결측(15일, 8,625건 보간값)으로 인한 테스트 왜곡을 투명하게 규명하고, 100% 실측치 기반의 무결성 평가 기준(안 2)을 수립.
  - 데이터 엔지니어링부터 AI 모델링, ONNX 경량화, 백엔드 서빙, 프론트엔드 시각화까지 전체 아키텍처 흐름을 한눈에 파악할 수 있는 엔드투엔드 Mermaid 플로우차트 문서화 필요.
- **주요 조치**:
  1. **타깃별 Optuna 최적 파라미터 및 학습 설정 문서화 (`docs/AI_MODEL_SPEC.md`, `docs/MODEL_PERFORMANCE_REPORT.md`)**:
     - 노트북(Cell 6-1) 실행 결과에서 도출된 수단별(따릉이/버스/지하철) Best Hyperparameters(`learning_rate`, `num_leaves`, `max_depth`, `subsample`, `colsample_bytree`, `reg_alpha`, `reg_lambda`) 표 수록.
     - 공통 기본 설정(`n_estimators: 1500`, `early_stopping: 50` 등) 및 조기 종료 후 최종 트리 수(`best_iteration`: BIKE 834 / BUS 1390 / SUBWAY 865) 정리.
     - 최종 테스트 성능($R^2$, RMSE, MAE) 공식 수치 수록 (따릉이 0.9873, 버스 0.9901, 지하철 0.9951).
  2. **11~12월 버스 결측치 대응 및 클린 테스트 가이드 수립 (안 2 채택)**:
     - 11월 말~12월 버스 승차량 결측(26일 중 15일, 8,625건, 테스트셋의 24.59%~32.61% 보간값)과 10월 무결 구간(0% 결측) 특성을 명시.
     - 보간값 왜곡 없이 100% 순수 실측치로 버스 모델의 일반화 SLA를 공정하게 검증할 수 있는 **12월 결측 배제 클린 테스트 구간(`11-01 ~ 11-27`) 평가 가이드** 명시.
  3. **전체 시스템 및 E2E 파이프라인 플로우차트 추가 (`docs/SYSTEM_ARCHITECTURE.md`, `README.md`)**:
     - [1. 데이터 수집/전처리] ➔ [2. 32D 특성 공학/분할] ➔ [3. LightGBM 모델링 & Optuna 튜닝] ➔ [4. ONNX 경량화 & FastAPI 서빙] ➔ [5. 외부 실시간 API 연동] ➔ [6. React & MapLibre UI 시각화] 전 과정을 포괄하는 표준 Mermaid 다이어그램 수록.
- **산출물**:
  - `docs/AI_MODEL_SPEC.md`
  - `docs/MODEL_PERFORMANCE_REPORT.md`
  - `docs/SYSTEM_ARCHITECTURE.md`
  - `README.md`
  - `docs/CHANGELOG.md`

---

## [2026-10-26]

### 🚲 서울시 따릉이 실시간 대여소 연동 (이슈 #13)
- **배경**: 따릉이는 `bikeStopData.ts` 하드코딩 약 52개 대여소와 시뮬레이션 값으로 표시되어 실제 잔여 자전거 수와 달랐음.
- **조치**:
  1. **백엔드 (`main.py`)**: 서울 열린데이터광장 `bikeList` 연동 (1000건씩 페이지 병합), 60초 스냅샷 캐시, `SEOUL_BIKE` 서킷브레이커, last-good 스냅샷 fallback, `/api/v1/system/circuit-breakers`에 bike 추가.
  2. **엔드포인트**: `GET /api/v1/transit/bike/stations/nearby`, `/search`, `/by-number/{station_no}`, `/{station_id}`.
  3. **프론트엔드 (`TransitMap.tsx`)**: 따릉이 필터에서 줌 14.5 이상일 때 지도 주변 실제 대여소(약 2,700곳 중 화면 내)를 기존 거점 마커(52개)와 **동일한 마커·팝업 파이프라인으로 통합**. 모든 대여소가 같은 UI(혼잡도 알약/점 마커, 기상·AI 모델 추론, 실시간 잔여 자전거 수)를 사용하며, 거점(모델 파라미터 보유)은 기존 데이터를 유지하고 그 외 대여소는 기본 수요도(45)+평균 강수 민감도를 적용. 잔여 수는 대여소 번호 `by-number` 조회 → 200m 이내 최근접 → 기존 추정값("추정" 표기) 순. 팝업이 열려 있는 동안에는 마커 재생성을 보류. `new URL()` 미사용.
  4. **API 검증 로그 (`apiLogger.ts`)**: 브라우저 콘솔에 `🚲 [서울 열린데이터광장] 따릉이 실시간 대여정보(bikeList)`(대여소별 조회 방식·엔드포인트·응답·원천 JSON)와 `🚲 따릉이 주변 대여소 조회`(지도 이동 시 일괄 조회 결과) 그룹 로그 추가. 실시간 조회 실패 시 "추정값" 사용 사실도 표시. 대여소 번호 매칭 결과가 거점 좌표와 250m 이상 어긋나면(하드코딩 번호 오류, 예: #108 홍대입구역 8번출구 ↔ 서교동 사거리) 번호 매칭을 폐기하고 최근접 대여소로 대체하며 콘솔에 경고 출력.
  5. **설정**: `SEOUL_BIKE_API_KEY`(선택) 추가, 미설정 시 `SEOUL_DATA_API_KEY` 재사용.
- **산출물**: `main.py`, `Weather-Transport Recommendation UI/src/TransitMap.tsx`, `.env.example`, `docs/CHANGELOG.md`

---
## [2026-10-19]

### 🐳 dev 브랜치 머지 후 Docker 동기화 결함 수정 및 런타임 캐시 관리 개선
- **배경**:
  - `dev` 브랜치 머지 후 Docker 이미지 빌드 시 신규 코드 및 신규 파일(`feature_schema.py`, `feature_schema.json`, 32차원 ONNX 모델)이 컨테이너 내부에 온전히 반영되지 않거나 이전 레이어 캐시로 인해 동기화되지 않는 현상 발생.
  - 로컬 SQLite 런타임 캐시 파일인 `data/timeseries_cache.db`가 Git 인덱스에 추적(tracked)되어 불필요한 변경사항으로 감지되고, 도커 빌드 시 호스트의 로컬 DB가 컨테이너 이미지 레이어로 덮어씌워질 위험 존재.
- **조치**:
  1. **Git 형상 관리 정비 (`.gitignore`)**:
     - `.gitignore`에 `timeseries_cache.db`, `data/timeseries_cache.db`, `*.db-shm`, `*.db-wal`을 등록하여 SQLite 런타임 캐시 및 임시 저널 파일을 Git 추적 대상에서 영구 제외.
     - Git 인덱스에 기존 추적 중이던 `data/timeseries_cache.db`를 `git rm --cached data/timeseries_cache.db`로 인덱스에서 안전하게 언트랙(untrack) 처리.
  2. **Docker 빌드 및 무시 목록 정비 (`.dockerignore`, `Dockerfile.backend`)**:
     - `.dockerignore`에 `timeseries_cache.db`, `data/timeseries_cache.db`, `**/timeseries_cache.db`, `*.db-shm`, `*.db-wal`을 추가하여 이미지 빌드 시 호스트 로컬 DB가 이미지 내부로 복사되는 것을 방지.
     - `Dockerfile.backend`의 복사 지시문을 `COPY *.py ./`로 개선하여 `main.py`, `timeseries_cache.py`, `feature_schema.py` 및 신규 파이썬 스크립트가 누락 없이 온전히 복사되도록 보장.
     - `models/feature_schema.json`을 명시적으로 배치하고, `COPY benchmarks/2026-10-14/feature_schema.json ./models/feature_schema.json` 복사를 추가하여 컨테이너 내 `/app/models/`에 스키마 파일이 확실히 존재하도록 보장.
  3. **Docker Compose 볼륨 마운트 구조 점검**:
     - `docker-compose.yml`의 `volumes: - ./data:/app/data` 설정을 점검하여 런타임 데이터 및 캐시는 호스트-컨테이너 간에 안전하게 동기화되고, 애플리케이션 코드 및 ONNX 모델 자산은 이미지 빌드 시 온전히 패키징되어 독립 구동됨을 확인.
- **검증 결과**:
  1. **무캐시 재빌드 및 컨테이너 강제 재생성**:
     - `docker compose build --no-cache` 및 `docker compose up -d --force-recreate` 정상 완료.
     - backend 컨테이너가 15초 내 헬스체크 통과(`healthy`) 및 frontend 정상 기동.
  2. **컨테이너 내부 모델 자산 검증 (`docker compose exec backend ls -la models/`)**:
     - 신규 32차원 ONNX 3종(`lgb_bike_demand.onnx` 7.02MB, `lgb_bus_demand.onnx` 13.60MB, `lgb_subway_demand.onnx` 7.35MB) 및 피처 스키마(`feature_schema.json` 3.42KB) 정상 존재 확인.
  3. **백엔드 헬스체크 및 32차원 모델 상태 검증 (`GET /health`)**:
     - 3개 수단(bike, bus, subway) 32차원 모델 웜업 완료(`model_input_dims: {bike: 32, bus: 32, subway: 32}`).
     - `feature_schema.status = verified` (경로: `models/feature_schema.json`, 버전: `v2-전처리_2-32d`, 차원: 32) 확인.
- **산출물**: `.gitignore`, `.dockerignore`, `Dockerfile.backend`, `models/feature_schema.json`, `docs/CHANGELOG.md`

### 🧭 지도 카메라 탑뷰 복원 및 실시간 버스 API 상대 경로 URL 파싱 결함 수정
- **배경**:
  - `dev` 브랜치 분기 시점 차이로 인해 PR #4(지도 탑뷰 pitch 0° 및 새로고침 시 초기화)가 누락되어 지도가 30° 틸트 상태로 복원되던 현상 발생.
  - `dev` 병합 후 도커 Nginx 프록시 환경(`VITE_API_BASE_URL=""`)에서 지도 이동 시 `주변 버스정류장 조회 실패: TypeError: Failed to construct 'URL': Invalid URL` 에러가 발생하여 주변 정류장이 지도에 표시되지 않는 결함 발생.
  - 버스 노선 뷰(`TransitMap.tsx`)에서 차량/정류장 클릭 시 `pitch: 30`으로 다시 틸트되는 잔여 하드코딩 존재.
  - 공공데이터포털(data.go.kr)의 정류소·노선·버스위치 정보 오픈API 활용신청 권한 부재로 인한 401(등록되지 않은 서비스키) 에러 발생.
- **조치**:
  1. **`dev` 브랜치 병합 (`git merge dev`)**:
     - PR #4(지도 시야각 0° 탑뷰 및 새로고침 시 pitch/bearing 무조건 초기화)와 최신 기능(모바일 UI, 서울 버스 실시간 API)을 현재 브랜치로 완전 병합.
  2. **지도 카메라 탑뷰 완전 통일 (`TransitMap.tsx`)**:
     - 버스 실시간 차량 클릭 및 경유 정류장 클릭 `flyTo` 핸들러 2곳의 `pitch: 30`을 `DEFAULT_MAP_PITCH`(0°) 상수로 통일(`commit f4265db`).
  3. **상대 경로 `new URL()` 파싱 예외 수정 (`TransitMap.tsx`)**:
     - 도커 리버스 프록시 환경에서 `API_BASE_URL`이 빈 문자열(`""`)일 때 `new URL("/api/...")` 호출 시 브라우저 표준 예외(`Invalid URL`)가 발생하던 문제를 `URLSearchParams`와 템플릿 문자열 결합 방식으로 수정(`commit 1b3bc4a`).
  4. **공공데이터포털 서울시 버스 오픈API 4종 연동 정상화**:
     - 서울특별시_정류소정보조회, 서울특별시_노선정보조회, 서울특별시_버스위치정보조회, 서울특별시_버스도착정보조회 서비스 권한 활성화를 통해 지도 위 정류소 마커, 노선 경로선, 실시간 버스 위치(🚌 첫차/다음차) 정상 출력 확인.
- **검증 결과**:
  - 프론트엔드 컨테이너 무캐시 재빌드(`docker compose build frontend && docker compose up -d frontend`) 배포 완료.
  - 브라우저 개발자 도구 콘솔의 `Invalid URL` 에러 소멸 확인.
  - 지도 이동 시 500m 반경 주변 버스정류소 마커 및 실시간 버스 위치 정상 렌더링 확인.
  - 나침반 회전/틸트 조작 후 새로고침(`F5`) 시 항상 탑뷰(0°) 및 정북(0°)으로 정상 초기화 확인.
- **산출물**: `Weather-Transport Recommendation UI/src/TransitMap.tsx`, `docs/CHANGELOG.md`

### 📚 문서 갱신 (Docs) 및 브랜치 동기화 가이드 보강
- **배경**:
  - GitHub Web에서 이슈 기반 브랜치를 자동 생성할 때 기본 분기 기준 브랜치가 과거 커밋이거나 다른 브랜치로 설정되어 최신 `dev` 브랜치 변경 사항이 누락된 채 분기되는 위험 발견.
  - 서울시 실시간 버스 기능(주변 정류장, 노선 궤적, 실시간 차량 위치, 환승 정보)을 완벽하게 구동하기 위해 공공데이터포털(data.go.kr)에서 동일한 계정으로 신청해야 하는 5종의 필수 오픈API 정보가 프로젝트 설정 안내에 부족했던 문제 개선 필요.
- **조치**:
  1. **브랜치 분기 및 최신화 가이드 추가 (`README.md`)**:
     - GitHub 이슈에서 브랜치 생성 시 `Change source branch`를 통해 반드시 `dev`를 베이스로 선택하도록 명시.
     - 로컬에서 작업 시작 전 `git checkout dev`, `git pull origin dev`, `git checkout <이슈-브랜치명>`, `git merge dev`로 최신 상태를 동기화하는 가이드 절차 추가.
  2. **실시간 버스 필수 오픈API 5종 안내 추가 (`README.md`, `.env.example`)**:
     - 공공데이터포털 내 필요한 5개 서비스(정류소정보조회, 노선정보조회, 버스도착정보조회, 버스위치정보조회, 환승동선조회)의 공식 URL과 발급 안내(`BUS_API_KEY`)를 문서 및 환경변수 템플릿에 명시.
- **산출물**: `README.md`, `.env.example`, `docs/CHANGELOG.md`

---

## [2026-10-14]

### 0. 🤖 v2 실제 32차원 실피처 모델 3종 학습·반입 및 모델 자산 위치 확정
- **배경**:
  - 2026-10-13 파이프라인 v2 개정으로 학습·평가 기준이 **실제 32차원 실피처(8/8/5/11)** 로 확정되었으나 32차원 모델 산출물은 아직 없었고, `benchmarks/2026-10-12/tuned_real/` 은 안내 README 만 있는 **빈 배치 위치**였음.
- **조치**:
  1. **학습·반입**: `benchmarks/CastTransit.ipynb`(v2)를 Colab에서 실행([Cell 1]→[Cell 7], Optuna 30 trials 포함)해 32차원 ONNX 3종 + `feature_schema.json` 을 `benchmarks/2026-10-14/` 에 배치(커밋 `07292b4`).
     - `best_iteration` bike 834 / bus 1,390 / subway 865 · ONNX 입력 `[None, 32]`(이름 `float_input`)
  2. **사전 검증**: `feature_schema.json.feature_cols`(32) == `benchmarks/evaluate_models.py::FEATURE_COLS_32` == `main.py::build_feature_vector` 인덱스 0~31 **순서 완전 일치** · 공휴일 캘린더 **19일** 일치(`main.py::KR_HOLIDAYS`).
  3. **자산 위치 확정**: 신규 후보 경로를 `benchmarks/2026-10-14/` 로 확정하고, `2026-10-12/tuned_real/` 은 안내 README 만 남긴 **종료 폴더**로 전환. `evaluate_models.py::MODEL_SETS` 의 `tuned_32d_real` 기본 경로도 `2026-10-14/` 로 갱신(기존 경로는 빈 폴더라 `[skip]` 되었음).
  4. **문서 동기화**: `benchmarks/README.md`(§1 트리 · §2 자산표 · §3 규격표 · §4.1~4.2 · §5 이력), `docs/TODO.md` §4, `docs/MODEL_PERFORMANCE_REPORT.md` §0.2·§7 후속과제, `docs/AI_MODEL_SPEC.md` §7, `docs/BACKEND_INFERENCE_SERVER.md` §4, `docs/SYSTEM_ARCHITECTURE.md` §6.2.
- **검증 결과 (2026-10-14 · `benchmarks/results/comparison_20261014_184621.{json,md}`)**:
  - **교차검증 통과** — `python benchmarks/evaluate_models.py` 실측값이 노트북 기록 Test 지표와 **소수점 수준 일치**(bike R² 0.98729→0.9873 · bus 0.99006→0.9901 · subway 0.99515→0.9951, RMSE 오차 ≤0.006) → **파이프라인 재현성 확인**.
  - 배포본(25차원) 대비 순위: 🚇 **subway 전 지표 우세**(R² 0.9924→0.9951 · RMSE 826.324→662.095 · MAE 369.732→277.633, **MAE −24.9%**) / 🚲 **bike R²·RMSE 열세**(0.9887→0.9873 · 16.372→17.382, MAE·MAPE 는 우세) / 🚌 **bus R²·RMSE·MAE 우세하나 MAPE 열세**(14.53%→18.09%).
  - **배포 판단(Gate): 전면 교체 보류** — 3수단 전부 유의 우세 조건 미충족 → **`models/` 는 25차원 유지**(수단별 교체 검토 또는 25차원 재학습 비교 후 확정). → ⚠️ **후속 §6 에서 전면 32차원 교체로 확정·실행(2026-10-14)**.
- **미해결 / 다음 단계**:
  - 버스 수치는 P0-1(테스트 구간 `버스_승차` 결측 24.59% 보간)로 **잠정치**.
  - 동일 `study.best_params` + 25차원 서브셋 재학습으로 "차원 vs 튜닝" 효과 분리 · `feature_schema.json` 을 평가·서빙 코드가 소비하도록 전환(SSoT 자동 검증).
  - 수단별 교체 확정 시 `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 의 "25차원 부분집합" 서술 정리 + `tests/test_inference.py`·`tests/test_api.py` 재검증.
- **산출물**: `benchmarks/2026-10-14/{lgb_bike,lgb_bus,lgb_subway}_demand.onnx`, `benchmarks/2026-10-14/feature_schema.json`, `benchmarks/2026-10-14/README.md`, `benchmarks/2026-10-12/tuned_real/README.md`, `benchmarks/results/comparison_20261014_184621.{json,md}`, `benchmarks/evaluate_models.py`, `benchmarks/README.md`, `docs/TODO.md`, `docs/MODEL_PERFORMANCE_REPORT.md`, `docs/AI_MODEL_SPEC.md`, `docs/BACKEND_INFERENCE_SERVER.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/CHANGELOG.md`

### 1. 🤖 전 세대 모델 3종 동시 비교 지원 — 평가 스크립트 **피처 배치(layout)** 도입
- **배경**:
  - 평가 스크립트가 v1 자산(`benchmarks/2026-10-12/tuned/`, 25차원 + 상수 0 더미 7)을 **피처 배치 비호환**을 이유로 비교 대상에서 제외하고 있어 **"전 모델 비교"가 불가능**했음.
- **조치**:
  1. **`benchmarks/evaluate_models.py` — 라벨별 피처 배치 도입**: `MODEL_LAYOUTS`(미지정 라벨 = `v2`) + CLI `--layout LABEL=v1|v2`.
     - 배치 3종: `v2-32d-real`(사양서 §3.2 · 8/8/5/11 실피처) / `v1-32d-dummy7`(25차원 `8/8/1/3/3/2` + 상수 0 더미 7 — **25차원 서브셋 + 0 열 7개**로 재현) / `25d-subset`(배포본).
     - v1 정의는 구 스크립트(`ef1d03d:benchmarks/evaluate_models.py`)의 `FEATURE_COLS` + `infra_dummy_0..6` 과 동일함을 git 이력으로 확인.
     - `is_holiday = 0` 참고치(`reference_ih0`)를 **배치 기준**으로 산출(25차원 배포본 · v1 32차원).
  2. **기본 비교 3종 확대**: `production_25d`(=`original/`) · `tuned_32d_v1`(=`2026-10-12/tuned/`) · `tuned_32d_real`(=`2026-10-14/`).
  3. **리포트 확장**: `피처 배치` 열 · 배포본 대비 **델타 표** · **SHA256 자산 무결성** 절(배포 슬롯 `models/` ≡ `benchmarks/original/` **동일 자산 자동 검출** — 12개 스캔 중 동일 3건).
  4. **자산 문서**: `benchmarks/2026-10-12/tuned/README.md` 신설(배치 정의·평가법·교차검증 기준) · `benchmarks/README.md` §1(트리)·§2·§3·§4.1·§5·§6 갱신.
- **검증 (교차검증 통과)**: 구 v1 프레임 보고치 재현 — bike R² **0.9893** / subway R² **0.9940** / subway MAE 개선폭 **−19.2%** 동일 → v1 배치 재구성 정확. (bus 만 프레임 차이로 R² 0.9908→0.9923 — 배포본도 0.9882→0.9897 로 동일 방향)
- **결과 (`benchmarks/results/comparison_20261014_192204.{json,md}` · Test 2025-11-16~12-31, n=26,450 · 구 `190055` 대체)**:
  - `tuned_32d_v1` 이 **12개 지표 전부 배포본보다 우세**(MAE 개선폭 bike −4.4% / bus −15.4% / subway −19.2%) — "25차원 정보량 + Optuna 튜닝"만으로 배포본을 상회.
  - **동일 프레임 v1 vs v2 직접 비교**: 🚲·🚌 은 **v1 우세**(8개 지표), 🚇 만 **v2 우세**(4개 지표 · MAE −24.9%).
  - ⇒ **배포 판단 변화 없음**(당시 `models/` 25차원 유지 → ⚠️ **§6 에서 전면 32차원 교체로 확정**). 단 **25차원 재학습(v2 파라미터)이 최우선 후속 과제**로 승격되고, 수단별 교체는 **지하철 단독**만 근거가 있음.
- **미해결 / 다음 단계**:
  - v1 은 **서빙 불가**(32차원 모델에 32차원 실피처 벡터가 들어가면 인덱스 17 이후 어긋남) → **판단 보조 지표**로만 사용.
  - 버스 수치는 P0-1(테스트 구간 결측 24.59% 보간)로 **잠정치** · `feature_schema.json` SSoT 소비 전환은 미완(→ 아래 §2 에서 완료).
- **산출물**: `benchmarks/evaluate_models.py`, `benchmarks/results/comparison_20261014_192204.{json,md}`, `benchmarks/2026-10-12/tuned/README.md`, `benchmarks/README.md`, `docs/MODEL_PERFORMANCE_REPORT.md` §0.3·§7, `docs/TODO.md` §4, `docs/AI_MODEL_SPEC.md` §7, `docs/BACKEND_INFERENCE_SERVER.md` §4, `docs/SYSTEM_ARCHITECTURE.md` §6.2, `docs/CHANGELOG.md`

### 2. 🧩 피처 스키마 SSoT 소비 전환 + 25차원 재학습(차원 vs 튜닝 분리) 실험
- **배경**:
  - 학습(Colab)·평가(`evaluate_models.py`)·서빙(`main.py`)이 피처 순서를 각자 하드코딩 → v1 32차원 자산을 v2 배치로 추론하면 **조용히 예측이 붕괴**(R² −0.59 / −0.93 / 0.19 실측)하는 사고가 재현됐음.
  - 배포본(25차원) vs v2 후보(32차원)의 차이는 ①차원 ②Optuna 튜닝 ③신규 원천(`전처리_2`)이 **동시에** 바뀐 교란 3중 → 순수 차원 효과를 알 수 없었음.
- **조치**:
  1. **`feature_schema.py` 신설(SSoT 모듈)** — 탐색 우선순위(`--schema` 인자 → `FEATURE_SCHEMA_PATH` → `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json`) · 검증 함수(`schema_feature_cols` / `validate_expected_order` / `validate_targets` / `validate_split_bounds` / `legacy_25d_cols`) · 불일치 시 `FeatureSchemaError`(첫 어긋난 인덱스 진단).
  2. **서빙 `main.py`** — `FEATURE_ORDER_32` 상수 신설 + `build_feature_vector` 차원 assert · 기동 시 `load_feature_schema()` → `validate_model_dimensions()` 로 **스키마 ↔ 코드 순서 ↔ 실제 ONNX 입력 차원 3중 대조**(알 수 없는 차원이면 기동 중단) · `GET /health` 에 `feature_schema` 블록 추가 · 25차원 서브셋 인덱스 정의를 SSoT 한 곳으로 통일.
  3. **평가 `evaluate_models.py`** — `--schema PATH` 추가 + `verify_feature_schema()`(순서·타깃·분할 경계 assert, **32차원/25차원 스키마 모두 지원**) · 리포트 헤더·JSON `feature_spec.schema` 에 검증 결과 기록 · `reference_ih0` 참고치를 **레거시 라벨 한정**(신규 25차원 자산 오표기 방지).
  4. **`benchmarks/retrain_25d.py` 신설** — 스키마의 v2 `best_params` **고정** + 피처만 25차원 서빙 서브셋으로 줄여 재학습(`--export` 시 ONNX 3종 + 25차원 스키마 반출). 전처리·지표·분할은 `evaluate_models.py` 를 import 해 재사용.
  5. **`tests/test_feature_schema.py` 신설** — 규격 / 3자 순서 일치 / 25차원 서브셋 / ONNX 자산 차원 / 타깃·분할·공휴일 / 네거티브 가드 5종 / `/health` 노출 / 컨테이너 배포 파일 목록 = **8종 전부 통과**.
- **결과 (`benchmarks/results/comparison_20261014_192204.{json,md}` 4-way · Test 2025-11-16~12-31, n=26,450 · R²/RMSE/MAE)**:

| 수단 | 배포본 25d | v1 32d | v2 32d | **재학습 25d (동일 v2 파라미터)** |
| :---: | ---: | ---: | ---: | ---: |
| 🚲 bike | 0.9887 / 16.372 / 9.815 | 0.9893 / 15.912 / 9.387 | 0.9873 / 17.382 / 9.669 | 0.9883 / 16.666 / 9.677 |
| 🚌 bus | 0.9897 / 571.741 / 369.300 | 0.9923 / 495.648 / 312.571 | 0.9901 / 561.358 / 370.444 | **0.9912 / 528.628 / 342.732** |
| 🚇 subway | 0.9924 / 826.324 / 369.732 | 0.9940 / 736.058 / 298.796 | **0.9951 / 662.095 / 277.633** | 0.9935 / 769.318 / 330.871 |

  - **차원 vs 튜닝 분리**: 튜닝 파라미터 고정 + 25차원으로 축소해도 배포본을 상회(🚌 MAE −26.6 / 🚇 MAE −38.9 / 🚲 MAE −0.138) → **개선의 대부분은 튜닝 효과**. 32차원 증가의 **순수 효과는 🚇 지하철에서만**(v2 32d 가 25d 재학습 대비 R² +0.0017 · MAE −53.2).
  - `tuned_25d` 는 25차원이라 **서빙 정렬이 그대로 맞아**(`prepare_session_input` 서브셋과 배치 동일) `models/` 교체 후보로 등록합니다.
  - ✅ **Colab 재현 편차 0 (2026-10-14 완료 · 아래 §4)** — `best_iteration` bike 680 / bus 1,498 / subway 446 이고 **R²·RMSE·MAE·MAPE 12개 지표 전부 로컬과 Δ = 0** → 플랫폼 차이 없음. 버스는 P0-1(결측 24.59% 보간)로 **잠정치**.
- **미해결 / 다음 단계**:
  - **`models/` 교체 판단(미완)** — 후보: `tuned_25d`(bus·subway 우세, 수단별 교체) / v2 32d(지하철 단독). 교체 시 `tests/test_feature_schema.py`·`test_inference.py`·`test_api.py` 재검증 + `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 서술 갱신.
  - ~~Colab 재현(선택) 편차 확인~~ → **2026-10-14 완료**(아래 §4 · 플랫폼 편차 Δ = 0).
- **산출물**: `feature_schema.py`, `benchmarks/retrain_25d.py`, `benchmarks/evaluate_models.py`, `main.py`, `tests/test_feature_schema.py`, `benchmarks/2026-10-14/tuned_25d/{lgb_bike,lgb_bus,lgb_subway}_demand.onnx` + `tuned_25d/feature_schema.json`, `benchmarks/results/{comparison_20261014_192204,retrain_25d_20261014_192001}.{json,md}`, `benchmarks/README.md`, `benchmarks/2026-10-14/README.md`, `docs/{TODO,MODEL_PERFORMANCE_REPORT,CHANGELOG,AI_MODEL_SPEC,BACKEND_INFERENCE_SERVER,API_STRUCTURE}.md`, `.env.example`

### 3. 🐳 컨테이너 배포 결함 수정 — `feature_schema.py` COPY 누락 (기동 ImportError)
- **배경**: `feature_schema.json` SSoT 소비 전환으로 `main.py` 가 `feature_schema` 모듈을 import 하게 되었는데, `Dockerfile.backend` 의 COPY 목록(`COPY main.py timeseries_cache.py ./`)에 빠져 **컨테이너 기동이 ImportError 로 실패**하는 상태였음(2026-10-14 실제 발생).
- **조치**:
  1. **`Dockerfile.backend`** — `COPY main.py timeseries_cache.py feature_schema.py ./` 로 수정 + `benchmarks/2026-10-14/feature_schema.json` 반입(`models/feature_schema.json` 이 있으면 그 스키마가 우선 → **32차원 자산 교체 시 자연 승격**).
  2. **`tests/test_feature_schema.py`** — **Test 8 컨테이너 배포 파일 목록 검증** 추가(`Dockerfile.backend` COPY 목록에 런타임 모듈·스키마가 포함되는지 정적 검증) → **8종 전부 통과**.
  3. **문서 동기화**: `docs/DOCKER_CONTAINERIZATION_PLAN.md` §3.1 · `docs/API_STRUCTURE.md`.
- **실기동 검증 완료 (2026-10-14 · Docker Desktop)**:
  - ✅ `docker compose up -d --build` → backend·frontend **재빌드·재기동**(backend `healthy` 24초 내 · `8100→8000` / `3100→80`) · 기동 로그 `[schema] 피처 스키마 검증 통과: model_version=v2-전처리_2-32d | 32차원 | 출처=/app/benchmarks/2026-10-14/feature_schema.json` → **ImportError 재발 없음**(COPY 수정 유효) · 3세션 warmup(`input dim: 25`) 완료.
  - ✅ 엔드포인트 6종 **200**: 직접 `GET /health` · `POST /api/v1/predict/recommendation`(추론 6.6ms · 추천 3건) · `GET /api/v1/districts/live-congestion`(7.8ms) / Nginx 경유 `:3100/health`·`:3100/api/v1/predict/recommendation` / SPA `:3100/`(text/html) · 백엔드 로그 ERROR·Traceback 0건.
  - ✅ 회귀 테스트: `tests/test_feature_schema.py`(8종) · `tests/test_inference.py`(추론 SLA 평균 **2.28ms** < 15ms) · `tests/test_api.py`(서킷 브레이커 폴백 포함) 전부 통과.
  - ℹ️ 당시 `/health.feature_schema.status` = **`legacy-subset-25d`**(배포 모델 25차원 + 스키마 32차원 = **정상**) → ⚠️ **§6 교체로 `verified` 승격**(2026-10-14).
- **산출물**: `Dockerfile.backend`, `tests/test_feature_schema.py`, `docs/DOCKER_CONTAINERIZATION_PLAN.md`, `docs/API_STRUCTURE.md`, `docs/TODO.md`, `docs/CHANGELOG.md`

### 4. 🔁 25차원 재학습 **Colab 재현 노트북** 신설 — `.py` 업로드 불가 제약 우회
- **배경**:
  - 로컬 25차원 재학습(`benchmarks/retrain_25d.py`) 결과에 대해 "Colab 재현(선택)" 과제가 남아 있었으나, Colab 은 **`.py` 파일을 열어 실행하는 방식이 아니라** 파일 업로드·모듈 import·저장소 클론이 필요했습니다(`retrain_25d.py` 는 `evaluate_models.py` → `main.py`(fastapi·dotenv·httpx) → `feature_schema.py`·원천 CSV 까지 import 체인이 이어져 **단독 업로드 불가**).
  - 게다가 `retrain_25d.py`·`feature_schema.py` 는 `origin` 에 **미푸시**(로컬 5커밋 앞) 상태라 `git clone` 경로도 사용할 수 없었습니다.
- **조치**:
  1. **`benchmarks/retrain_25d_colab.ipynb` 신설(업로드 파일 1개로 완결)** — 레포의 `benchmarks/CastTransit.ipynb` 에서 전처리 셀 4개(`[Cell 3]`/`[Cell 4-A]`/`[Cell 4-B]`/`[Cell 5]`)를 **첫 줄 태그로 찾아 그대로 `exec`** 하는 방식으로, 학습 코드를 복사하지 않고 재사용 → **학습·평가 간 피처 드리프트 0**(인덱스 하드코딩 금지).
     - `[Cell 6]`(베이스라인)·`[Cell 6-1]`(Optuna 30 trials)·`[Cell 7]`(32차원 export)은 **건너뜀** → `create_study` 에 seed 가 없어 재탐색하면 `best_params` 가 바뀌어 **차원 vs 튜닝 분리 실험의 비교 가능성이 훼손**되므로, 스키마 SSoT(`benchmarks/2026-10-14/feature_schema.json::metrics.*.tuned.best_params`)를 코드에 **고정 주입**(약 20분 절약).
     - 6셀 구성: `[Step 0]` 패키지 핀 + 환경 기록 → `[Step 1]` Drive 마운트·레포/CSV 확인 → `[Step 2]` 원본 셀 4개 exec → `[Step 3]` 25차원 서브셋 재학습(`LEGACY_25D_INDICES = range(17)+[21..26]+[30,31]`, 제외 7개 이름 assert) → `[Step 4]` ONNX 3종 + 25차원 스키마 반출(`benchmarks/2026-10-14/tuned_25d_colab/`, 입력 `[None, 25]` assert · `env` 블록에 런타임·lightgbm 버전 자동 기록) → `[Step 5]` 로컬 기준값 대조 표.
     - 지표 산식은 `evaluate_models.regression_metrics` 와 동일 규칙(MAPE 는 실측 0 제외) · 산출 스키마는 `retrain_25d.py::export_assets` 와 동일 구조 → **정규 하네스가 그대로 소비**.
  2. **로컬 선검증(실행 증거)** — 노트북 셀을 로컬 원천 CSV 로 exec: `[Step 2]`~`[Step 5]` 전부 통과하며 지표·`best_iteration` 이 `retrain_25d.py` 실행값과 **완전 일치**(bike R² 0.9883·16.6664·9.6767·680 / bus 0.9912·528.6187·342.7211·1,498 / subway 0.9935·769.3175·330.8713·446, ΔR² 0.0000).
     - 반출 ONNX 3종은 `evaluate_models.py` 가 **`dim=25`·`layout=25d-subset`** 로 자동 판별해 4-way 표를 생성(반입 후 추가 조치 불필요) · 반출 스키마 `model_version=v2-전처리_2-25d-retrain-colab`.
  3. **문서 동기화**: `benchmarks/README.md` §1 트리·§2 자산표·§5 이력, `benchmarks/2026-10-14/README.md`(`tuned_25d_colab/` 절 — 반입·검증 결과), `benchmarks/2026-10-14/tuned_25d_colab/README.md`(반입·검증 결과), `docs/TODO.md` §4.
   4. **Colab 실행 → 반입 → 5-way 평가 (2026-10-14 완료)** — 사용자가 Colab 에서 노트북을 실행해 반출한 파일 4개를 `benchmarks/2026-10-14/tuned_25d_colab/` 에 반입하고 정규 하네스로 검증.
- **검증 결과 — 플랫폼 편차 0 (`benchmarks/results/comparison_20261014_214856.{json,md}` · 5-way)**:

| 수단 | R² | RMSE | MAE | MAPE≠0 | best_iter | 로컬 `tuned_25d/` 대비 Δ |
| :---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 🚲 bike | 0.9883 | 16.666 | 9.677 | 16.19% | 680 | **0.000000** |
| 🚌 bus | 0.9912 | 528.628 | 342.732 | 14.07% | 1,498 | **0.000000** |
| 🚇 subway | 0.9935 | 769.318 | 330.871 | 4.96% | 446 | **0.000000** |

  - R²·RMSE·MAE·MAPE·`best_iteration` **12개 지표 전부 Δ = 0**(스키마 JSON 값 완전 일치) + `best_params`·25차원 피처 순서 일치 · ONNX **파일 크기 3종 동일**(5,709,941 / 14,574,454 / 3,713,077 · 직렬화 메타 차이로 SHA256 만 상이).
  - Colab 환경(스키마 `env` 자동 기록): python 3.13.16 · **lightgbm 4.7.0(로컬과 동일)** · numpy 2.1.3 · pandas 2.2.3.
  - ⇒ 로컬 실험(lightgbm 4.7.0) 결과가 **Colab 재현성까지 확보**되었고 `tuned_25d` ≡ `tuned_25d_colab` **동일 모델**이므로, `models/` 교체 판단 근거는 변동 없음(잔여 리스크: P0-1 버스 잠정치 · 교체 Gate 미확정).
- **미해결 / 다음 단계**:
  - 로컬 `tuned_25d/` 는 **대조군으로 보존**(반출 폴더명을 `tuned_25d_colab/` 으로 분리) — 두 폴더 지표가 동일하므로 교체 반입 시 어느 쪽을 쓰든 결과는 같습니다.
  - `models/` 교체 판단·수단별 Gate 확정은 `docs/TODO.md` §4 의 별도 대기 항목.
- **산출물**: `benchmarks/retrain_25d_colab.ipynb`, `benchmarks/2026-10-14/tuned_25d_colab/{lgb_bike,lgb_bus,lgb_subway}_demand.onnx` + `tuned_25d_colab/feature_schema.json` + `tuned_25d_colab/README.md`, `benchmarks/results/comparison_20261014_214856.{json,md}`, `benchmarks/README.md`, `benchmarks/2026-10-14/README.md`, `docs/TODO.md`, `docs/CHANGELOG.md`

### 5. ⚠️ `models/` 교체 절차 함정 확인 — 25차원 스키마는 배포 슬롯 반입 금지 (기동 중단)
- **배경**: `docs/TODO.md` §4 의 교체 체크리스트가 "교체 후 `/health.feature_schema.status == verified` 확인"으로 적혀 있었으나, 25차원 재학습 후보(`tuned_25d/`·`tuned_25d_colab/`)에는 **25차원 스키마**가 함께 반출되어 있어, 슬롯 반입 여부에 따라 **기동 실패 위험**이 있었습니다.
- **실측 (2026-10-14 · `feature_schema.py` 직접 호출)**:
  - `benchmarks/2026-10-14/feature_schema.json`(32차원 · `v2-전처리_2-32d`) → `validate_expected_order` **PASS**(기동 OK).
  - `tuned_25d/feature_schema.json` · `tuned_25d_colab/feature_schema.json`(**25차원** · `v2-전처리_2-25d-retrain(-colab)`) → **FAIL** → `FeatureSchemaError` 로 **기동 중단**. `validate_expected_order` 는 스키마 == `main.py::FEATURE_ORDER_32`(32차원) **완전 일치**를 요구합니다.
- **조치(문서 정정)**: 교체 체크리스트 수정 — ① 반입 대상은 `models/lgb_{bike,bus,subway}_demand.onnx` **ONNX 3종만** ② 교체 후 `feature_schema.status` 는 **`legacy-subset-25d` 유지가 정상**(스키마는 32차원 SSoT 유지) ③ `verified` 는 **32차원 자산 + 32차원 스키마**일 때만 ④ `models/feature_schema.json` 슬롯에 25차원 스키마 **반입 금지** 경고를 `docs/TODO.md` §4 · `benchmarks/2026-10-14/README.md` · `tuned_25d_colab/README.md` 에 명시.
- **산출물**: `docs/TODO.md`, `benchmarks/2026-10-14/README.md`, `benchmarks/2026-10-14/tuned_25d_colab/README.md`, `docs/CHANGELOG.md`

---

### 6. 🚀 배포 모델 **전면 32차원 교체**(사양서 배치) + 컨테이너 실기동 재검증
- **배경**: 32차원 실피처 후보(`benchmarks/2026-10-14/`)는 🚇 지하철 전 지표 우세(MAE −24.9%)였으나 🚲 bike R²·RMSE · 🚌 bus MAPE 열세로 **전면 교체가 보류**된 상태였음(§0). 이번에 **사양서 배치(8/8/5/11) 단일화 · 규격 정합(`verified`) 확보 · 서빙 경로 실검증**을 목적으로 **전면 32차원 교체**를 결정·실행(트레이드오프 수치 명시).
- **조치**:
  1. **배포 슬롯 교체(ONNX 3종, 파일 단위)** — `benchmarks/2026-10-14/lgb_{bike,bus,subway}_demand.onnx` → `models/` (SHA256 `A6854BC6…` / `983A069B…` / `264E822F…` · 크기 7,020,769 / 13,596,760 / 7,345,447 byte). 스키마는 **반입하지 않았음** — 현행 32차원 SSoT(`benchmarks/2026-10-14/feature_schema.json`)가 탐색 3순위로 그대로 사용되어 `status=verified` 로 자연 승격(`models/feature_schema.json` 중복 배치 시 드리프트 위험).
  2. **테스트 동기화** — `tests/test_feature_schema.py`: **Test 3** 은 25차원 레거시 서브셋 정렬 검증을 **25차원 자산(`benchmarks/original/`)** 으로 분리 + **32차원 무변환 통과 검증 추가** · **Test 4** 배포 슬롯 기대 차원 25→**32** · **Test 7** `status` 기대값 `legacy-subset-25d`→**`verified`** · `model_input_dims` 25→**32**(부분 교체 시 되돌리는 방법을 주석으로 명시).
  3. **문서 동기화** — `docs/TODO.md` §3·§4 · `docs/MODEL_PERFORMANCE_REPORT.md` §7 · `docs/API_STRUCTURE.md` §3 · `docs/BACKEND_INFERENCE_SERVER.md` §3 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 · `docs/AI_MODEL_SPEC.md` §7 · `docs/DOCKER_CONTAINERIZATION_PLAN.md` §5 · `benchmarks/README.md` §2·§3·§5 · `benchmarks/2026-10-14/README.md`.
- **검증 결과 (2026-10-14)**:
  - ✅ **회귀 테스트 6종 전부 통과** — `test_feature_schema.py`(8종 · `/health.feature_schema.status=verified` · dims `{bike:32,bus:32,subway:32}`) · `test_inference.py`(추론 SLA 평균 **1.91ms** < 15ms · 우천 모달 시프트 통과) · `test_api.py` · `test_mcda_calibration.py` · `test_timeseries_cache.py` · `test_station_pipeline.py`
  - ✅ **컨테이너 재빌드·실기동** — `docker compose up -d --build` → backend **`healthy`**(`8100→8000`) · frontend Up(`3100→80`) · 기동 로그 `[schema] {bike,bus,subway}: 입력 32차원 — 스키마 정렬 OK` · 3세션 warmup(`input dim: 32`) · **레거시 서브셋 경고 소멸** · ERROR·Traceback 0건
  - ✅ **엔드포인트 6종 200** — `GET /health`(`status=ok` · `feature_schema.status=verified` · dims `{32,32,32}`) · `POST /api/v1/predict/recommendation`(10.83ms · bike 87 / subway 80 / bus 67) · `GET /api/v1/districts/live-congestion`(14.67ms · hotspots 5) / Nginx 경유 `:3100/health`·`:3100/api/v1/districts/live-congestion`(200) / SPA `:3100/`(text/html)
- **감수한 트레이드오프(명시)**: 배포본 25d 대비 🚇 subway MAE −24.9% · RMSE −19.9% ↔ 🚲 bike R² −0.0014 · RMSE +1.010(+6.2%) · 🚌 bus MAPE +3.56%p(+24.5% 상대, P0-1 결측 24.59% 보간으로 **잠정치**) → **지하철 정확도·규격 정합성·배치 단일화를 우선**하고 나머지는 수용. 25차원 재학습본(`tuned_25d/`)과 `original/` 스냅샷은 **롤백·대안 자산으로 보존**.
- **롤백**: `Copy-Item benchmarks\original\lgb_{bike,bus,subway}_demand.onnx models\ -Force`(25차원 원복) → `status=legacy-subset-25d` 복귀 + `tests/test_feature_schema.py` Test 3·4·7 기대값 원복.
- **산출물**: `models/lgb_{bike,bus,subway}_demand.onnx`, `tests/test_feature_schema.py`, `docs/TODO.md`, `docs/MODEL_PERFORMANCE_REPORT.md`, `docs/API_STRUCTURE.md`, `docs/BACKEND_INFERENCE_SERVER.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/AI_MODEL_SPEC.md`, `docs/DOCKER_CONTAINERIZATION_PLAN.md`, `benchmarks/README.md`, `benchmarks/2026-10-14/README.md`, `docs/CHANGELOG.md`

---

## [2026-10-13]

### 0. 🎯 학습·평가 파이프라인 v2 — 사양서 분할 확정 · 실제 공휴일 캘린더 · 실피처 32차원 공정 비교
- **배경**:
  - 인수 데이터셋(`data/2025_서울25개구_교통날씨_전처리_2.csv`)의 `분할` 컬럼 경계가 사양서 §6.1과 불일치(감사 P0-2).
  - `is_holiday` 가 학습(상수 0)과 서빙(`= is_weekend`)에서 서로 다르게 정의되어 있었고, **둘 다 실제 공휴일을 반영하지 않음**.
  - 벤치마크 비교가 "25차원 + **상수 0 더미 7**" 로 이루어져 **공정한 32차원 비교가 아니었음**(추가 7차원은 정보량 0, 배치 순서도 사양서와 상이).
- **결정 및 조치**:
  1. **분할 경계 = 사양서 §6.1 공식 확정** (`train ≤ 09-30` / `valid 10-01~11-15` / `test 11-16~12-31`). CSV `분할` 컬럼(valid ~10-31 / test 11-01~)은 **사용하지 않음** → 노트북 `SPLIT_SOURCE = 'spec_dates'` 를 기본값으로 전환.
  2. **`is_holiday` = 2025 대한민국 실제 공휴일 캘린더 19일** (신정 / 설날 연휴+임시공휴일 / 삼일절+대체 / 어린이날·부처님오신날+대체 / 제21대 대통령선거일 / 현충일 / 광복절 / 개천절 / 추석 연휴+대체 / 한글날 / 성탄절).
     - **서빙**: `main.py` 에 `KR_HOLIDAYS` + `is_kr_public_holiday()` 신설, `build_feature_vector` 의 `is_holiday = is_weekend` 복제 로직 제거(주말 지표와 분리).
     - **학습**: `benchmarks/CastTransit.ipynb` [Cell 4-A]에 동일 집합(`KR_HOLIDAYS_2025`) 반영 + 공휴일 비율 `assert` 추가.
     - **근거**: 「공휴일에 관한 법률」 제2·3조(대체공휴일 규정), Office Holidays 2025, 위키백과 「대한민국의 공휴일」. 노동절(05-01)·제헌절(07-17)은 2025년 공휴일이 아니므로 제외.
  3. **`benchmarks/evaluate_models.py` v2 재작성**: 상수 0 더미 폐기 → **실제 32차원 실피처(8/8/5/11)**.
     - 인프라 4 + `same_day_last_week_*` 3을 실측 산출(7일 전 타임스탬프 self-merge, `shift(168)` 금지).
     - `DISTRICT_CODE_MAP` / `DISTRICT_INFRA` / `KR_HOLIDAYS` 를 **`main.py` 에서 직접 import** → 학습·평가·서빙 단일 소스화.
     - 25차원 배포본은 **동일 피처 프레임의 25차원 서브셋**을 받으므로, 두 모델의 차이는 피처 구성 차이만 반영(공정 비교).
     - v1 32차원 자산(`2026-10-12/tuned/`)은 피처 배치가 비호환(인덱스 16 이후 어긋남)이라 **기본 비교 대상에서 제외**.
     - 신규 32차원 산출물 위치 `benchmarks/2026-10-12/tuned_real/` 신설(+`README.md`).
4. **노트북 실행 안정화(Colab)**: 미설치 패키지 **자동 설치 가드** 추가 — `optuna`([Cell 6-1]), `onnxmltools`·`skl2onnx`([Cell 7]) + `importlib.invalidate_caches()`(설치 직후 동일 커널 즉시 import). [Cell 1] 안내 주석도 갱신.
- **정리**: 참조 0건인 Gemini 생성 스크립트 `benchmarks/gemini-code-1791814037657.py` 삭제(Colab 셀 파편 — `trained_models`/`X_test` 등 미정의 전역 참조로 단독 실행 불가, `evaluate_models.py` 가 역할 대체).
- **검증**: `python benchmarks/evaluate_models.py` 실행 성공 — train 156,975 / valid 26,450 / test 26,450 (2025-11-16~12-31), **피처 결측 0**, 공휴일 10,925행(5.21%). 25차원 배포본 R² 0.9887 / 0.9897 / 0.9924.
- **산출물**: `main.py`, `benchmarks/CastTransit.ipynb`, `benchmarks/evaluate_models.py`, `benchmarks/2026-10-12/tuned_real/README.md`, `benchmarks/README.md`, `docs/AI_MODEL_SPEC.md` §3.1·§3.2·§5.2·§6.1·§6.2·§7, `docs/AI_INFERENCE_MODEL_SPEC.md` §3.1·§3.2·§6.2, `docs/MODEL_PERFORMANCE_REPORT.md` §0, `docs/DATA_PREPROCESSING_HANDOFF.md`, `README.md`

---

## [2026-10-12]

### 0. 📦 데이터 전처리 산출물(`전처리_2`) 인수 감사 및 담당자 전달 문서 신설
- **배경**:
  - 신규 원천 `data/2025_서울25개구_교통날씨_전처리_2.csv`(209,875 × 33)가 인수되어, 학습 파이프라인을 해당 파일 기준으로 전환하는 과정에서 **데이터 계약(분할 경계·결측 정책·미포함 파생 피처)** 에 대한 담당자 합의가 필요해짐.
  - 특히 테스트 구간의 라벨 품질 이슈가 발견되어, 이를 구두가 아닌 **문서 기반으로 회신 요청**할 필요가 있었음.
- **감사 결과 (전 컬럼 자동 검증)**:
  - ✅ 완전 그리드(25구 × 365일 × 23시), 중복 0, 시계열 정렬 정상, 캘린더 파생 4종(`월/요일/주말여부/연중일`) 전수 정합, **결측 플래그 ↔ NaN 1:1 완전 일치(9개 컬럼)**.
  - 🔴 **테스트 구간 `버스_승차` 결측 24.59%**: 결측 26일 × 25구 × 23시 = 14,950건이며, 그중 **15일이 테스트(11~12월)** 에 위치 → 테스트 성능이 보간값 대비로 측정되어 SLA 판정 신뢰도 훼손.
  - 🔴 **`분할` 컬럼 경계가 사양서 §6.1과 불일치**: CSV는 valid 10-31 / test 11-01, 사양서는 valid 11-15 / test 11-16.
  - 🟠 파생 피처 7종(인프라 4 + `same_day_last_week` 3)이 CSV에 미포함 → 모델 코드에 하드코딩된 재구성 로직으로 대체 중(원천 변경 시 조용한 어긋남 위험).
  - 🟠 결측 플래그 3종(`AWS_관측행누락` 271 / `지하철_자료범위밖` 45,625 / `풍향0_풍속양수` 21,807)은 명명 예외이며 정의가 문서화되지 않음 → `지하철_자료범위밖`은 실제로 "01~05시 심야 운휴"로 명칭 부적합.
  - 🟠 기상 결측이 특정 구에 편중(`기온` 결측 881건 중 용산구 528건 = 60%), `강수량` 결측 2,242건 중 AWS 관측행 누락은 271건뿐.
- **조치**: 감사 근거·영향·요청을 **P0(2) / P1(5) / P2(3) 우선순위 체크리스트**로 정리한 인수인계 문서 신설.
- **산출물**: `docs/DATA_PREPROCESSING_HANDOFF.md`(신설), `README.md`(문서 목록·디렉터리 트리 등록), `docs/CHANGELOG.md`

### 1. 🧩 ONNX 모델 입력 차원(25 vs 32) 문서 모순 정리 및 벤치마크 자산 통합
- **배경**:
  - 사양서(`docs/AI_INFERENCE_MODEL_SPEC.md` §3.2)와 백엔드 문서는 추론 입력을 **32차원**으로 규정하나, `docs/SYSTEM_ARCHITECTURE.md` §6.2 모델 규격 표는 배포 모델을 **25차원**으로 기재하여 문서 간 표기가 상충.
  - 또한 `benchmarks/2026-10-12/` 하위에 노트북 export 셀 2회 실행으로 **동일 모델(MD5 일치)이 2벌 중복** 저장되어 있었음.
- **조치**:
  1. **중복 모델 자산 통합**: `baseline/`, `hyperparameter/`(MD5 동일 2벌)를 삭제하고 `benchmarks/2026-10-12/tuned/` 단일 폴더로 무손실 통합(해시 검증 통과 후 삭제).
  2. **문서 모순 정리**: `SYSTEM_ARCHITECTURE.md` §4.3·§6.2 및 사양서 §3.2에 “**서빙 입력 계약(32차원) vs 모델 입력 텐서(25차원)**” 두 계층을 명시하고, `25 = 32 − 7`(공간 인프라 4 + `same_day_last_week_*` 3) 매핑 및 `prepare_session_input()` 자동 정렬 로직을 문서화.
  3. **비교 분석 도구 신설(`benchmarks/evaluate_models.py`)**: Temporal Split(Test 2025-11-16 ~ 12-31) 기준으로 배포 모델(25차원)과 튜닝 후보(32차원)를 R²/RMSE/MAE/MAPE + ONNX 레이턴시로 공정 비교. 노트북 [Cell 7-1] 보고 R²(0.9893 / 0.9908 / 0.9940)와 **완전 일치**로 파이프라인 재현을 검증.
  4. **결과 요약**: 후보(튜닝)가 전 수단에서 우세(MAE 기준 subway −19.2%, bus −13.4%, bike −4.0%)하나, 이는 **차원이 아닌 하이퍼파라미터 튜닝 효과**임(더미 7차원은 상수 0으로 정보량이 25차원과 동일).
- **산출물**: `benchmarks/README.md`, `benchmarks/evaluate_models.py`, `benchmarks/results/comparison_*.{json,md}`, `docs/MODEL_PERFORMANCE_REPORT.md`, `docs/AI_INFERENCE_MODEL_SPEC.md` §3.2, `docs/SYSTEM_ARCHITECTURE.md` §4.3·§6.2, `docs/BACKEND_INFERENCE_SERVER.md` §4

### 2. 🧩 AI 모델 사양서(`AI_MODEL_SPEC.md`) 분리 및 상호 링크 정리
- **배경**: `AI_INFERENCE_MODEL_SPEC.md`가 모델 규격과 구축·서빙 가이드를 한 문서에 담고 있어, 모델 스펙만 참조하려는 경우에도 개발 절차·서빙 연동 절을 함께 읽어야 하는 불편이 있었음.
- **조치**: **모델 자체의 규격만** 별도 문서로 분리.
  - 신설: `docs/AI_MODEL_SPEC.md` — §2.3 SLA, §3.1·3.2 데이터셋/피처 스키마, §4 아키텍처·혼잡도/추천 알고리즘, §5 베이스 모델 비교, §6.2·6.4 학습 분할/ONNX 규격, §7 모델 자산(`models/`) 규격.
  - 원본 `AI_INFERENCE_MODEL_SPEC.md`는 **구축 가이드로 그대로 유지**하되, 문서 상단 및 각 분리 절(§2.3, §3.1, §3.2, §4, §5, §6.2, §6.4)에 **상호 링크** 추가.
  - `README.md` 문서 목록·디렉터리 트리에 `AI_MODEL_SPEC.md` 등록.
- **산출물**: `docs/AI_MODEL_SPEC.md`(신설), `docs/AI_INFERENCE_MODEL_SPEC.md`(링크), `README.md`

---

## [2026-10-16]

### 0. 🗺️ MapLibre 지도 기본 카메라 시야각 탑뷰(Pitch 0°) 전환 — 3D 틸트 기본값 제거
- **배경**:
  - 지도 탭 진입 시 카메라가 3D 틸트 뷰(`pitch: 30°`)로 기울어진 상태에서 시작되어, 역·정류소의 상대 위치와 노선망 구조를 평면(정사영) 기준으로 파악하려는 사용자에게 원근 왜곡과 마커/팝업의 시각적 어긋남을 유발하던 문제 개선.
- **원인 분석**:
  - MapLibre 생성자의 초기 시야각(`initialPitch`)과 저장 뷰 복원 폴백(`getSavedMapView`)이 모두 `30`으로 하드코딩되어 있었고, 역 클릭·경로 핀 클릭·검색 포커스·권역 바로가기에서 실행되는 `flyTo` 애니메이션도 `pitch: 35`(검색 포커스는 `45`)를 강제하고 있어 **탑뷰 유지가 구조적으로 불가능**했음.
- **해결 조치 (`TransitMap.tsx`)**:
  1. **기본 카메라 시야각 상수 도입**: `DEFAULT_MAP_PITCH = 0`(시야각 0° = 탑뷰, 수직 하향) · `DEFAULT_MAP_BEARING = 0`(정북) 상수를 신설하고, 지도 생성자 초기값과 저장 뷰 복원 폴백값을 모두 탑뷰 기준으로 통일.
  2. **프로그램적 카메라 이동 전면 탑뷰화**: 역 마커 클릭(1곳), 경로 출발지·환승역·도착지 핀 클릭(3곳), 검색 포커스(`focusedCoords`, 2곳), 권역 바로가기(1곳) — 총 **7곳의 `flyTo` 시야각을 `DEFAULT_MAP_PITCH`(0°)로 변경**. 어떤 진입 경로로 이동해도 시야각이 3D 틸트로 되돌아가지 않음.
  3. **구버전 저장 뷰 1회 자동 이관(마이그레이션)**: 로컬 스토리지(`weather_transit_map_view`)에 스키마 버전 필드(`v: 2`)를 추가하고, 버전 필드가 없는 구 저장값(v1)은 구 기본 시야각 30°가 그대로 굳어 있으므로 **중심·줌·방위각은 보존한 채 시야각(Pitch)만 탑뷰 0°로 1회 이관**. 갱신 저장 시 `v: 2`가 기록되어 이후에는 사용자가 직접 기울인 시야각을 그대로 복원. → ⚠️ **아래 §1 에서 개정**: 새로고침 시 시야각·방위각 영속화 자체를 폐기하고 위치·줌만 복원하도록 변경(구버전 이관 로직 포함 제거).
  4. **수동 3D 틸트 탐색 경로는 보존**: 우측 상단 `NavigationControl`의 `visualizePitch: true`는 유지하여, 사용자가 나침반을 드래그할 때만 3D 틸트로 전환 가능.
- **검증**:
  - `pitch` 하드코딩 잔존값 `30 / 35 / 45` **0건** — 지도 생성자 및 `flyTo` 7곳 모두 `DEFAULT_MAP_PITCH` 참조로 교체.
  - `npx tsc --noEmit` — `TransitMap.tsx` 오류 0건 (전체 10건은 `App.tsx`·`subwayGraph.ts`의 기존 오류로, 변경 전후 동일함을 `git stash` 대조로 확인).
  - `npm run build` — Vite 프로덕션 번들 빌드 성공.
- **산출물**: `Weather-Transport Recommendation UI/src/TransitMap.tsx`, `Weather-Transport Recommendation UI/docs/CHANGELOG.md`, `docs/CHANGELOG.md`

### 1. 🧭 새로고침 시 카메라 시야각·방위각 무조건 초기화 — 위치·줌만 복원 (탑뷰 검증성 개선)
- **배경**:
  - §0 조치 이후에도 새로고침하면 저장된 뷰포트의 시야각(틸트)·방위각이 그대로 되살아나, 로컬 스토리지에 3D 틸트 상태가 한 번이라도 기록된 브라우저에서는 **지도가 여전히 기울어진 채 열려 탑뷰 기본값을 검증할 수 없었음**.
- **원인 분석**:
  - `getSavedMapView`가 `pitch`·`bearing`까지 복원하고 `moveend`마다 다시 저장하는 영속화 구조를 유지했기 때문에, 기울어진 시점이 한 번 저장되면 이후 모든 새로고침에서 그 각도가 반복 복원되었음. (CSS `perspective/rotate` 변형·별도 카메라 API 등 다른 틸트 원인은 없음을 확인)
- **해결 조치 (`TransitMap.tsx`)**:
  1. **시야각·방위각 영속화 완전 폐기**: `SavedMapView` 규격을 `center`·`zoom`만 보유하도록 축소하고, `saveCurrentMapView`(=`moveend` 핸들러)도 위치·줌만 기록. §0에서 도입한 `STORAGE_MAP_VIEW_VERSION`(`v: 2`) 스키마 버전 필드와 구버전 이관 로직은 목적이 소멸하여 제거.
  2. **지도 생성자에서 각도 고정**: `pitch: DEFAULT_MAP_PITCH`(0° = 탑뷰) · `bearing: DEFAULT_MAP_BEARING`(0° = 정북)을 항상 적용 → 새로고침(F5)·재진입 시 시야각과 방향이 무조건 초기화.
  3. 같은 세션에서 나침반 드래그로 기울이거나 회전한 시점은 그대로 유지되지만, 새로고침하면 다시 탑뷰·정북으로 복귀.
- **검증**:
  - `pitch`·`bearing` 저장/복원 참조 **0건** — `STORAGE_MAP_VIEW_VERSION`·`parsed.pitch`·`savedView?.pitch` 잔존 없음. 남은 각도 지정은 지도 생성자와 `flyTo` 7곳(`DEFAULT_MAP_PITCH`)뿐.
  - `npx tsc --noEmit` — `TransitMap.tsx` 오류 0건 (전체 10건은 `App.tsx`·`subwayGraph.ts`의 기존 오류).
  - `npm run build` — Vite 프로덕션 번들 빌드 성공.
- **검증 방법(수동)**: 브라우저에서 지도를 나침반으로 기울인 뒤 새로고침(F5) → 지도가 **탑뷰·정북**으로 시작하는지 확인.
- **산출물**: `Weather-Transport Recommendation UI/src/TransitMap.tsx`, `Weather-Transport Recommendation UI/docs/CHANGELOG.md`, `docs/CHANGELOG.md` (§0·§1 동일 산출물)

---
## [2026-10-06]

### 0. 🧹 경로 추천 탭 랜드마크 추천 경로 UI 및 입력창 기본값(Prefill) 완전 제거
- **배경**:
  - 경로 추천 화면 진입 시 사용자가 의도하지 않았음에도 자치구별 랜드마크 경로(예: '강남역' ➜ '삼성역')가 출발역/도착역 입력창에 기본값으로 강제 입력되고, 랜드마크 퀵 칩이 노출되어 사용성을 해치던 문제 개선.
- **해결 조치 (`App.tsx`)**:
  1. **대표 랜드마크 경로 프리필 `useEffect` 제거**: 자치구 변경 시 출발역/도착역을 자동으로 채우던 사이드이펙트 로직 삭제 (입력창을 항상 깨끗한 빈 값 `''`으로 유지).
  2. **랜드마크 추천 경로 퀵 칩 UI 및 상수 제거**: 경로 검색창 상단에 노출되던 `[자치구] 랜드마크 추천 경로` 버튼 UI 및 미사용 `DISTRICT_LANDMARK_ROUTES` 데이터 완전 제거.
  3. 사용자가 직접 검색창을 통해 원하는 출발역과 도착역을 검색하거나 '자주 찾는 경로'를 클릭했을 때만 검색이 실행되도록 직관성 강화.

### 0. 🚀 리눅스 홈서버 / 미니 PC 배포 가이드 공식 문서화 및 포트 격리 (`docs/SERVER_DEPLOYMENT_GUIDE.md`)
- **배경**:
  - Intel N100 등의 리눅스 홈서버/미니 PC 환경에서 이미 다른 웹 서비스(예: `map-board` Next.js 3000번, `leaderboard-api` 8000번)가 운영 중인 경우, 포트 충돌 없이 안정적으로 병행 운영할 수 있는 실전 가이드 요구 반영.
- **해결 조치**:
  1. **배포 가이드 문서 신설 ([`docs/SERVER_DEPLOYMENT_GUIDE.md`](SERVER_DEPLOYMENT_GUIDE.md))**:
     - 시스템 필수 패키지(`python3-venv`, `libgomp1`, `nodejs 20+`, `pm2`) 설치 안내.
     - **방법 A (권장)**: PM2 프로세스 매니저 기반 호스트 직접 배포 절차 (`ecosystem.config.cjs`, `pm2 save`, `pm2 startup`).
     - **방법 B**: Docker Compose 컨테이너 배포 절차 및 기본 포트 격리.
     - **Nginx Proxy Manager (NPM)** 연동 (단일 도메인 + `/api` 리버스 프록시, SSL 설정).
     - 방화벽(UFW) 오픈 및 원클릭 재배포 스크립트, FAQ 트러블슈팅(`libgomp1`, 포트 점검) 수록.
  2. **기본 포트 격리 (`docker-compose.yml`, `ecosystem.config.cjs`)**:
     - 프론트엔드 기본 포트: `3100` (기존 3000 점유 서비스 보호).
     - 백엔드 기본 포트: `8100` (기존 8000 점유 서비스 보호).
     - 환경 변수(`FRONTEND_PORT`, `BACKEND_PORT`) 오버라이드 지원.

### 0. 🇰🇷 대한민국 영토 한정 뷰포트 이동 제한 및 글로벌 타일 리소스 절약 (`maxBounds`, `minZoom`)
- **배경**:
  - 본 서비스는 대한민국 수도권 및 전국 대중교통·날씨 분석에 특화되어 있으므로, 사용자가 실수로 해외 영역으로 지도를 패닝하거나 전 세계 단위로 축소할 경우 불필요한 OpenStreetMap 타일 다운로드로 네트워크 대역폭과 브라우저 메모리가 낭비되던 문제 개선.
- **해결 조치 (`TransitMap.tsx`)**:
  1. **대한민국 Bounding Box (`KOREA_BOUNDS`) 설정**:
     - 서남단(`[124.0, 32.8]`, 서해/마라도)부터 동북단(`[132.0, 39.2]`, 동해/독도/DMZ 북방)까지 `maxBounds`를 엄격히 적용하여 대한민국 영토 밖으로의 이동 및 패닝 원천 차단.
  2. **최소 줌 레벨(`minZoom: 6.8`) 및 래스터 타일 레이어 레벨 제한**:
     - 대한민국 전국이 한눈에 들어오는 배율 이하로 축소되지 않도록 `minZoom: 6.8`을 설정하고, `osm-tiles-layer`의 `minzoom`을 6으로 제한하여 불필요한 전 세계 0~5레벨 타일 트래픽을 100% 절감.
  3. **저장된 좌표 유효성 검증 (`getSavedMapView`)**:
     - 복원 시 좌표가 대한민국 영역 밖일 경우 안전하게 기본 중심(`[127.050, 37.505]`)으로 보정.

### 0. 🚇 서울역 실시간 열차 도착 정보 누락 버그 해결 (서울 vs 서울역 공공 API 다중 쿼리 병합)
- **배경**:
  - 서울역 조회 시 오직 신설 노선인 GTX-A(3건)만 표출되고, 핵심 간선인 1호선·4호선·경의중앙선·공항철도 열차 정보가 전면 누락되던 현상 발생.
- **원인 분석**:
  - 서울시 공공데이터포털(`realtimeStationArrival`) 데이터 등록 규격상, 1호선·4호선·경의중앙선·공항철도는 역사 공식명이 `'서울'`로 등록되어 있고, GTX-A만 `'서울역'`으로 분리 등록되어 있음.
  - 기존 백엔드 로직에서 `clean_st == "서울" or raw_st == "서울역"` 조건으로 인해 검색어를 `'서울역'`으로 일괄 강제 치환하여 호출하고 있었기 때문에, 서울시 API 서버가 '서울역'으로 등록된 GTX-A 노선만 반환함.
- **해결 조치 (`main.py`, `TransitMap.tsx`, `App.tsx`)**:
  1. `main.py`: 서울역 요청 시 `'서울'`과 `'서울역'`을 `asyncio.gather`로 병렬 호출하여, 1호선·4호선·경의중앙선·공항철도·GTX-A 5대 노선의 모든 열차를 중복 없이 취합하도록 쿼리 구조 전면 개선.
  2. `TransitMap.tsx`, `App.tsx`: 팝업 및 상세 시트의 도착 정보 표출 개수와 스크롤 영역을 확대하여 5개 노선의 상·하행 열차가 고루 표출되도록 UI 개선.

### 0. 🗺️ 지도 뷰포트 위치 및 인터랙션 상태 새로고침 영속화 (Map Viewport & Selection State Auto-Persistence)
- **배경**:
  - 사용자가 지도 탭에서 특정 거점(역/정류소)으로 이동하거나 줌(Zoom) 배율을 확대한 상태에서 페이지를 새로고침(F5)할 경우, 기본 강남구 중심 좌표(`[127.050, 37.505]`, `zoom: 13`)로 리셋되어 탐색 흐름이 끊기던 UX 한계를 개선.
- **해결 조치**:
  1. **지도 카메라 뷰포트(중심·줌·피치·방위각) 실시간 자동 저장 (`TransitMap.tsx`)**:
     - `moveend` 이벤트를 리스닝하여 사용자가 지도를 이동하거나 확대한 직후의 중심 좌표(`center: [lng, lat]`), 줌 배율(`zoom`), 3D 시야각(`pitch`), 방위각(`bearing`)을 `localStorage`(`weather_transit_map_view`)에 실시간 자동 동기화.
     - 새로고침 시 `MapLibre` 생성자에 저장된 뷰포트를 초기값으로 주입하여, 불필요한 위치 점프나 깜빡임 없이 보던 시점 그대로 렌더링.
  2. **선택했던 역/정류소 및 실시간 상세 패널 자동 복원 (`TransitMap.tsx`, `App.tsx`)**:
     - 특정 거점 클릭 시 역 고유 ID(`weather_transit_selected_stop_id`)를 저장하고, 팝업 닫힘/줌아웃 시 안전하게 정리.
     - 새로고침 시 이전에 선택했던 거점을 자동 탐색하여 알약 마커 선택 상태, 혼잡도 뱃지, 실시간 기상/도착 정보 팝업 및 상세 패널을 그대로 복원 (복원 시 카메라 뷰 위치를 해치지 않도록 `flyTo` 스킵 플래그 적용).
  3. **교통수단 필터(전체/지하철/버스/따릉이) 영속화 (`App.tsx`)**:
     - 사용자가 선택한 상단 필터 상태(`weather_transit_map_transport`)를 로컬 스토리지에 유지.

### 0. ⚡ 백엔드 AI 추론 실시간 혼잡도 및 예측 이용량 터미널 로깅 고도화 (`main.py`)
- **배경**:
  - 프론트엔드 F12 콘솔에는 AI 모델 출력 데이터가 정상 수신되었으나, 백엔드 터미널/도커 로그에는 Uvicorn 기본 액세스 로그(`POST ... 200 OK`)만 찍혀 실시간 혼잡도(%) 및 예측 이용량(명/시) 추이를 도커 로그에서 즉각 모니터링하기 어려웠던 점 개선.
- **해결 조치**:
  - `predict_recommendation` 엔드포인트에 지역, 역사, 실시간 관측 기온/강수량, 추론 지연시간(ms), 수단별(지하철, 버스, 따릉이) 혼잡도(%), 혼잡 라벨, 시간당 예측 이용량(명/시), 추천 점수를 가독성 높은 이모지 포맷으로 실시간 `logger.info` 출력.
  - `docker compose logs -f backend` 명령어로 컨테이너 운영 중에도 AI 수요 추론 결과를 즉시 관측 가능하도록 지원.

### 0. 🚇 인천 도시철도 1·2호선 전 노선(52개 역) 및 8대 광역 환승망 추가 구축
- **배경**:
  - 서울 중심 노선망에서 인천 광역생활권(계양, 부평, 송도, 청라, 검암 등)을 아우르는 전철망 확충 요구 반영.
- **해결 조치**:
  - `subwayData.ts`, `subwayGraph.ts`, `subwayNetworkLayer.ts`: 인천 1호선(계양~송도달빛축제공원, 30개 역) 및 인천 2호선(검단오류~운연, 27개 역) 마스터 데이터 신설 및 1호선·7호선·수인분당선·공항철도와의 환승 그래프 연계.
  - 노선 고유 컬러(인천 1호선 `#7CA8D5`, 인천 2호선 `#ED8B00`) 벡터 레이어 매핑.

### 0. 📁 유틸리티/데이터 빌드 스크립트 분리 및 브랜딩 정돈
- **배경**:
  - 루트 경로에 산재되어 있던 선택적 데이터 보정 파이썬 파일 및 웹 타이틀 브랜딩 정리.
- **해결 조치**:
  - `build_full_subway_data.py`, `update_station_coords.py`를 `scripts/` 폴더로 이관.
  - 웹 애플리케이션 타이틀에서 팀명(`| 선견지명`)을 제거하여 간결한 서비스 타이틀 유지.

### 0. 🚀 [Phase 3 전면 완수] 버스/따릉이 전역 확장, 실측 인프라 동기화, 랜드마크 추천 UX, 수도권 전철 벡터망 및 서킷 브레이커 고도화
- **배경**:
  - Phase 3 백로그 5대 과제(대규모 정류소 확장, 자치구 통계 동기화, 랜드마크 퀵 경로, 전철 벡터 레이어, 공공 API 장애 복원력)를 전면 구현하여 플랫폼의 지리적 커버리지와 시스템 신뢰성을 대폭 향상.
- **해결 조치**:
  1. **서울/수도권 버스 환승센터(55개) 및 따릉이 거점(52개) 데이터 전역 확장 & 멀티티어 줌 클러스터링 (`busStopData.ts`, `bikeStopData.ts`, `TransitMap.tsx`)**:
     - `busStopData.ts`: 서울역, 여의도, 잠실, 강남 등 핵심 광역환승센터 55개소(실제 `stId`, `arsId` 포함) 구축 및 온디맨드 버스 도착 API 연동.
     - `bikeStopData.ts`: 뚝섬, 여의나루, 반포 등 한강공원 및 25개 구 대표 핫스팟 52개소(실제 `stationNo`, `rackCount`) 구축 및 실시간 잔여대수 팝업 연동.
     - `TransitMap.tsx`: 줌 레벨별 단계적 가시성(광역 `<11.0`, 도심 `11.0~13.0`, 상세 `>=13.0`) 및 겹침 감지 시 원형 점(Dot) 마커 클러스터링 적용.
  2. **25개 자치구 및 9개 관문 도시 인프라 통계치(`DISTRICT_INFRA`) 실측 전수 동기화 (`main.py`)**:
     - 2024~2026 서울시 교통통계연보 및 시설공단 실측치 기반 지하철역 수, 버스 정류소 수, 따릉이 거치대 수, 상업지구 밀도 전면 갱신.
  3. **자치구별 랜드마크 기반 추천 경로 자동 프리필 및 원클릭 퀵 칩 UX (`App.tsx`)**:
     - 자치구 전환 시 빈 검색창에 해당 구의 대표 랜드마크 경로(예: 강남구 `강남역` ➔ `삼성역`, 마포구 `홍대입구역` ➔ `공덕역` 등) 자동 프리필.
     - 경로 검색창 상단에 원클릭 탐색 퀵 칩(Quick Chip) UI 제공.
  4. **수도권 전철 전체 노선망 배경 벡터 레이어 탑재 (`subwayNetworkLayer.ts`, `TransitMap.tsx`)**:
     - 수도권 1~9호선, 수인분당선, 신분당선, 경의중앙선, 공항철도, GTX-A 등 19개 전체 노선 공식 색상 코드 및 다크 케이싱 기반 GeoJSON Polyline 망 배경 렌더링.
     - 필터 전환(버스/따릉이) 시 지하철 벡터선 투명도(0.15) 동적 감쇄 UX 적용.
  5. **공공 API 장애 대비 3상 서킷 브레이커(Circuit Breaker) 및 Fallback 고도화 (`main.py`, `test_api.py`)**:
     - `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN) 상태 머신 탑재 (연속 3회 실패 시 30~45초 쿨다운 차단).
     - 장애 시 0ms 즉시 응답 보장: 직전 정상 스냅샷(`Last-Known-Good`) 캐시 우선 반환 및 계절/시간대 인식 지능형 Fallback 연동.
     - 서킷 브레이커 실시간 모니터링 엔드포인트(`GET /api/v1/system/circuit-breakers`) 및 `/health` 상태 노출.
     - 단위 테스트 스위트(`tests/test_api.py`)에 서킷 브레이커 상태 전이 및 복원력 검증 테스트 추가 (100% PASS).

### 0. 🎯 지하철역 78% 혼잡도 획일화 문제 해결 및 다차원 동적 혼잡도 엔진 전면 구축
- **배경**:
  - 기존 지도 뷰(`TransitMap.tsx`)에서 561개 전체 지하철역의 `baseCrowd`가 `70`으로 고정되어 있었고, 기본 강수량 슬라이더(2.8mm) 적용 시 공식($70 + 1.2 \times 2.8 \times 2.5 = 78.4$)에 의해 모든 역의 혼잡도가 예외 없이 **78%**로 균일하게 표출되던 문제를 발견.
- **해결 조치**:
  1. **561개 역 승하차 실측 기반 4대 위계(Tier) 마스터 데이터 개편 (`subwayData.ts`)**:
     - **Tier 1 초대형 허브역 (30개 역)**: 강남, 잠실, 홍대입구, 신도림, 서울역, 여의도, 가산디지털단지 등 일평균 승하차량 최상위 거점 (`baseCrowd`: 80~86%)
     - **Tier 2 주요 환승 및 부도심역 (138개 역)**: 2개 이상 환승역, 부평, 공덕, 양재, 당산, 천호, 충무로 등 (`baseCrowd`: 63~70%)
     - **Tier 3 일반 시내 거주/상업역 (257개 역)**: 일반 단일 노선 도심 역 (`baseCrowd`: 47~53%)
     - **Tier 4 경전철 및 수도권 최외곽역 (136개 역)**: 우이신설선, 신림선, 서해선, 경의중앙선/경춘선/1호선 외곽 (`baseCrowd`: 29~35%)
     - 역명 결정론적 해시 오프셋($\pm 3\%$)을 적용하여 동일 노선 및 인접 역사 간에도 자연스러운 승하차량 차이 반영.
  2. **동적 시계열·기상 시뮬레이션 혼잡도 계산 엔진 구축 (`TransitMap.tsx`)**:
     - **시간대별 출퇴근 첨두곡선 반영**: `selectedTime`('08시', '12시', '18시' 등) 파싱을 통해 출근 피크($1.25\times$), 퇴근 피크($1.22\times$), 점심($1.02\times$), 주간 비첨두($0.78\times$), 심야($0.42\times$) 승수 동적 산출.
     - **날씨 모달 시프트 반영**: 비가 올 때 대중교통(지하철/버스) 집중 가산(+1~15%) 및 따릉이 급감(-50~80%) 동적 처리.
     - 경로 검색 시 출발지·환승지·도착지 핀 마커 및 알약 뱃지 혼잡도가 시간/강수 변경 시 실시간 반응하도록 의존성(`[activeRoute, mapLoaded, rainMm, selectedTime]`) 강화.
  3. **시각화 다변화**:
     - 지도의 알약 뱃지 및 범례에 초록색('여유' <45%), 파란색('보통' 45~74%), 빨간색('혼잡' $\ge 75\%$)이 역사별로 다채롭고 직관적으로 분포되도록 완성.
  4. **광역 줌아웃(Zoom < 12.0) 시 역 마커 자동 숨김 최적화 (`TransitMap.tsx`)**:
     - 지도 배율이 12.0 미만으로 많이 축소되었을 때 화면이 수백 개의 역 알약 마커로 뒤덮여 도시명 및 지형이 가려지던 문제를 해결하기 위해, 광역 모드에서는 일반 역사 마커를 100% 자동 숨김 처리.
     - 12.0~13.0 구간에서는 대형 충돌 감지 박스(144x52px)를 통해 핵심 거점 역사만 여유 있게 표출하고, 13.0 이상 확대 시 점진적으로 세부 역을 노출하도록 계층형 시각화 구현.
     - 하단 안내 배지에 `🗺️ 광역 지도 모드: 역 마커와 혼잡도를 확인하려면 지도를 확대(Zoom-in)해 주세요` 문구를 실시간 연동.
  5. **역 클릭 시 부드러운 줌인(Zoom-in) 및 팝업 가림 방지 최적화 (`TransitMap.tsx`, `index.css`)**:
     - **원클릭 자동 줌인**: 지도에서 일반 역사 또는 경로 핀(출발/환승/도착) 클릭 시 해당 위치로 카메라 중심을 부드럽게 이동하며 상세 배율(기본 15.5 이상)로 자동 `flyTo` 줌인되도록 개선.
     - **팝업 가림 현상 원천 차단**:
       - 선택된 역 상단에 열리는 팝업 영역(260x145px)을 충돌 감지 박스(`placedBoxes`)로 자동 등록하여, 팝업 창 앞/주변을 가리던 인접 역 마커를 충돌 연산으로 자동 배제.
       - `.maplibregl-popup`의 CSS z-index를 최상위(`z-index: 100000 !important;`)로 강제하고 선택된 역 마커의 z-index를 `99999`로 상향하여 어떤 마커도 팝업 앞을 가릴 수 없도록 보장.
       - 팝업 카드를 전체 앱 다크 글래스 테마(`#111D35`) 및 네온 배지 스타일로 리디자인하여 시인성 대폭 향상.
  6. **이름 중복/밀집 역 원형 점(Dot) 마커 대체 표출 구현 (TransitMap.tsx)**:
     - 기존에는 역 이름 알약 마커가 겹칠 경우 한쪽 역을 완전히 숨겼으나, 지도상의 연속성과 역사 존재감을 파악할 수 있도록 **겹치는 역은 숨기지 않고 혼잡도 색상의 원형 미니 점(Dot) 마커로 전환 표출**.
     - 점 마커 역시 초록(여유)/하늘(보통)/빨강(혼잡) 색상을 유지하며, 마우스 호버 시 네온 글로우 발광 및 역 이름 툴팁 표출.
     - 점 마커를 클릭하면 일반 마커와 동일하게 해당 역으로 자동 줌인되며, 확대되어 공간이 확보되는 즉시 완전한 알약(Pill) 마커로 매끄럽게 확장.
     - 우측 하단 범례에 밀집 구간 역 (점 마커) 항목 신설.

---

### 0. 🌐 3대 실시간 공공 API(기상청·서울지하철·서울버스) 진본 연동 및 Full-Stack 파이프라인 구축
- **배경**:
  - 기존에는 기상청 초단기실황, 서울 지하철 실시간 도착, 서울 버스 도착 정보가 F12 콘솔 시뮬레이터 또는 고정 목데이터로만 동작하고 실제 정부 API 서버와 직접 연결되지 않았던 한계를 전면 개선.
- **해결 조치**:
  1. **FastAPI 백엔드(`main.py`) 실시간 공공 API 중계 프록시 & 인메모리 캐싱 레이어 신설**:
     - **기상청 초단기실황 (`GET /api/v1/weather/current?district={구명}`)**:
       - 25개 서울 자치구 및 수도권 주요 인접 도시(`성남시` nx=62, ny=123, `인천시` nx=55, ny=124 등) 기상청 격자 좌표 매핑 테이블 구축.
       - 기상청 APIHUB `getUltraSrtNcst` 실시간 호출 (10분 TTL 인메모리 캐싱).
       - 실시간 기온(`T1H`), 1시간 강수량(`RN1`), 강수형태(`PTY`), 습도(`REH`), 풍속(`WSD`) 파싱 및 정규화.
     - **서울 열린데이터광장 지하철 실시간 도착 (`GET /api/v1/transit/subway/arrival?station={역명}`)**:
       - `realtimeStationArrival` 실시간 연동 (15초 TTL 캐싱).
       - 역명 정규화('강남역' ➔ '강남', '서울역' 예외 처리) 및 1~9호선/신분당선/수인분당선 등 호선 매핑.
     - **공공데이터포털 버스 실시간 도착 (`GET /api/v1/transit/bus/arrival?stId={정류소ID}`)**:
       - 서울시 버스도착정보조회 `getLowArrInfoByStId` 실시간 연동 (15초 TTL 캐싱).
       - XML/JSON 정규화 및 첫차/막차 도착 예정 시간 파싱.
  2. **프론트엔드(`App.tsx`, `TransitMap.tsx`, `apiLogger.ts`) 실시간 연동**:
     - **실시간 날씨 모드 & 시뮬레이션 모드 토글**: 상단 타임라인에 `🟢 실시간` 버튼을 신설하여 실제 기상청 관측치(`liveWeather`)와 시간대별 시뮬레이션 전환 지원.
     - 메인 날씨 카드에 `🟢 기상청 실시간 실황 (KMA Live)` 배지 및 격자/발표시각 노출.
     - 기상청 실황 관측 기온/강수량/풍속/습도를 머신러닝 AI 추천 모델(`predict/recommendation`)에 실시간 피처로 전달.
     - 경로 검색 시 출발역의 실제 열차 도착 메시지 및 대기 시간(`departureTrain`)을 공공 API 실측 데이터로 갱신하여 화면 및 지도에 표출.
     - 지도 탭 거점 마커 클릭 시 실제 지하철/버스 도착 정보 비동기 호출 및 로깅.
     - 상단 `[📡 API 콘솔 로그 확인]` 버튼 클릭 시 3개 공공 API를 비동기 호출하여 실제 원천 JSON 페이로드를 F12 콘솔에 출력.
  3. **테스트 스위트 분리 및 검증 (`tests/`)**:
     - 루트에 분산되어 있던 `test_api.py`, `test_inference.py`를 `tests/` 폴더로 이관 정리.
     - 3개 공공 API 실호출 테스트 및 32차원 ONNX 추론 엔진 10회 벤치마크(2.04ms) 전원 통과(PASS).

---

### 1. 🚇 수도권 전철 최신 공식 거리비례제 운임 산정 엔진 구현 및 전면 적용 (`calculateSubwayFare`)
- **배경**:
  - 기존 지하철 운임이 1,400원 고정값으로 노출되거나 거리비례 요율이 단일 기준으로만 처리되어, 2024~2026년 수도권 전철 최신 운임 개정 기준 및 수도권 외 구간(충청/강원 연계 구간) 특례 요율이 누락되어 있던 문제 해결.
- **해결 조치 (`src/subwayGraph.ts`, `src/App.tsx`)**:
  - **수도권 전철 거리비례제 공식 산정 함수 구현 (`calculateSubwayFare`)**:
    - **기본운임**: 10km까지 **1,550원** (교통카드 일반 기준).
    - **수도권 내 추가운임**: 10km∼50km까지 매 5km마다 **100원** 가산 ($\max 800\text{원}$), 50km 초과 시 매 8km마다 **100원** 가산.
    - **수도권 외 구간 연속 이용 특례 (코레일 여객운송약관 기준)**:
      - 수도권 외 구간 정의 (`OUTER_SECTION_STATIONS`): 1호선 **평택역~신창역**(성환, 직산, 두정, 천안, 아산, 온양온천 등 12개 역), 경춘선 **가평역~춘천역**(굴봉산, 백양리, 강촌, 김유정, 남춘천, 춘천 등 6개 역).
      - 경계역 정의 (`BOUNDARY_STATIONS`): `'평택역'`, `'가평역'`.
      - 경계 판별 로직 (`isOuterEdge`): 에지의 양 끝 역 또는 경계역 연계 에지를 감지하여 외구간 거리(`outerDistanceKm`) 분리 계산.
      - **운임 계산 순서**: 수도권 내 구간 운임을 먼저 산정한 후, 수도권 외 구간 이용 거리에 대해 **4km마다 100원** 가산.
      - 수도권 외 단독 이용 시: 기본 10km 1,550원 + 10km 초과 시 4km마다 100원 가산.
    - **철도 실연장 거리 보정 계수 반영**: 위경도 구면거리(Haversine)에 철도 선로 굴곡도 계수를 반영하여 실제 영업거리(km)와 오차 최소화.
  - **공식 벤치마크 예시 100% 일치 검증**:
    - **서울역 ➔ 평택역 (73.3km, 수도권 내 구간만 이용)**:
      - ① 기본 1,550원 + ② $(50-10)/5 \times 100 = 800\text{원}$ + ③ $(73.3-50)/8 \approx 3 \times 100 = 300\text{원} \Rightarrow \mathbf{2,650\text{원}}$ (일치).
    - **서울역 ➔ 천안역 (94.9km, 수도권 내 73.3km + 외 21.6km 연속 이용)**:
      - ① 수도권 내(서울~평택 73.3km): $2,650\text{원}$
      - ② 수도권 외(평택~천안 21.6km): $21.6 / 4 \approx 6 \times 100 = 600\text{원} \Rightarrow \mathbf{3,250\text{원}}$ (일치).
  - **경로 탐색 엔진(`findSubwayRoute`) 연동**:
    - 탐색된 경로의 전체 정거장 명칭(`pathNames`)을 전달하여 외구간 진입 여부를 정밀 판별.
    - 반환 객체에 `fareKrw`, `distanceKm`, `innerDistanceKm`, `outerDistanceKm`, `fareBreakdown` 통합.
  - **UI 시각화 강화**:
    - 사이드바 경로 상세 패널에 **거리비례 운임 산정 내역 배지**(`💳 운임 산정: ...`) 추가로 계산 근거 실시간 노출.

---

### 2. 📊 가운데 [교통 이용자 현황] 카드 실시간 AI 추론 데이터 연동
- **배경**:
  - 메인 대시보드 가운데 카드가 06시~14시 정적 목업 배열(`HOURLY_DATA`)을 참조하여, 실제 FastAPI 머신러닝(ONNX) 추론 결과와 수치가 불일치하던 현상 개선.
- **해결 조치 (`src/App.tsx`)**:
  - 백엔드 AI 추론 응답의 실시간 예측 수요량(`predicted_volume`) 및 혼잡도(`crowd%`) 상태를 바인딩.
  - 자치구 선택, 시간대(Hour) 변경, 강수 시뮬레이션 슬라이더 조작 시 3대 교통수단(지하철, 버스, 따릉이)의 예측 이용자 수 및 혼잡도 바가 실시간 동적 렌더링되도록 동기화 완료.

---

### 3. 💾 브라우저 자치구(지역) 선택 영구 저장 (`localStorage` Persistence)
- **배경**:
  - 사용자가 지역(자치구)을 변경한 뒤 페이지를 새로고침(F5)하거나 재방문했을 때 항상 '강남구'로 초기화되던 불편 해소.
- **해결 조치 (`src/App.tsx`)**:
  - `localStorage` 키 `weather_transit_selected_district`에 선택된 자치구 명칭 영구 저장.
  - 앱 마운트 시 `getInitialDistrict` 헬퍼로 브라우저 캐시를 복원하고, 자치구 변경 시 즉시 동기화.
  - 서울시 25개 전 자치구 및 426개 행정동 검색 드롭다운과 완벽 호환.

---

### 4. 💰 수도권 전철 기본 운임 체계 1,550원 일괄 갱신 (Full Stack Synchronization)
- **배경**:
  - 서울시 및 코레일의 수도권 전철 요금 2차 인상 기준(1,400원 ➔ 1,550원)을 전체 코드베이스에 일관되게 반영.
- **해결 조치**:
  - **프론트엔드 (`src/App.tsx`)**:
    - `TRANSPORT_SCORES` 지하철 기본 요금: `'1,550원'`.
    - 자주 찾는 경로 폴백 요금: `'1,550원'`.
    - 지도 탭 우측 패널 기본 안내: `'1,550원~ (거리비례)'`.
  - **백엔드 (`main.py`)**:
    - 추천 API 응답의 지하철 기본 운임: `fare_krw=1550`.
  - **프로젝트 문서 동기화**:
    - `TODO_MOCK_AND_UNVERIFIED_DATA.md`, `AI_INFERENCE_MODEL_SPEC.md`, `BACKEND_INFERENCE_SERVER.md` 내 운임 기준 최신화.

---

### 5. ⚡ 실시간 공공 API 및 AI 추론 모델 중복 Fetch & 콘솔 중복 로깅 원천 차단
- **배경**:
  - 지도에서 역사 마커를 클릭하거나 검색 시, `TransitMap.tsx`와 상위 `App.tsx`가 각각 동일한 3개 API(기상청 초단기실황, AI 모델 추천 추론, 실시간 열차/버스 도착 정보)를 독립적으로 이중 호출하여 불필요한 네트워크 트래픽 및 콘솔 중복 로깅 발생.
  - 앱 초기 로드 시 `liveWeather`가 `null`인 상태에서 1차 호출, React 18 StrictMode 리마운트로 2차 호출, 실제 기상청 실황 데이터 수신 후 3차 호출되어 초기 `추론: 서울` 로그가 3회 연속 출력되던 현상 발생.
- **해결 조치**:
  1. **지도(`TransitMap.tsx`) ➔ 상위(`App.tsx`) 데이터 파이프라인 단일화**:
     - `StopDetailData` 인터페이스 신설: 지도에서 마커 클릭 시 조회된 기상청 데이터, AI 추론 결과, 실시간 도착 정보를 `onSelectStop(stop, details)` 콜백으로 `App.tsx`에 일괄 전달.
     - `App.tsx`에 `lastFetchedStopIdRef` 캐시 가드를 도입하여, `TransitMap`에서 이미 수신한 데이터는 `useEffect([selectedStop])`의 중복 Fetch를 원천 차단하고 사이드패널 상태(`stopWeatherData`, `stopAIData`, `stopArrivalData`)에 즉시 동기화.
     - 팝업 닫힘 시 `onSelectStop(null)`을 호출하여 거점 상세 상태를 깔끔하게 리셋.
  2. **초기 AI 추론 가드 (`lastAIFetchKeyRef`)**:
     - `liveWeather`가 로드되기 전의 임의 기본값(14°C) 기반 AI 추론 실행을 차단하고, 실제 기상청 관측치가 수신된 후 실제 날씨로 1회만 추론하도록 가드 추가.
     - `lastAIFetchKeyRef`를 통해 동일 자치구·기상 상태·시간대 조합에 대한 중복 추론 방지.
  3. **로거 디바운싱 및 명칭 인식 보완 (`apiLogger.ts`)**:
     - `recentLogs` 캐시(`shouldLog`, 1.2초 윈도우)를 구축하여, 단시간 내 동일 파라미터의 기상청·지하철·버스·AI 모델 로그가 브라우저 콘솔에 중복 출력되지 않도록 차단.
     - AI 추론 로그의 대상 명칭 추출 로직을 `inputFeatures.station || inputFeatures.district || inputFeatures.location` 순으로 보완하여 `서울` fallback 대신 실제 자치구/역명이 정상 표시되도록 개선.
  4. **경로 검색(`handleSearchRoute`) 내부의 출발역 중복 로그 제거**:
     - 실시간 도착 API 연동 후 불필요하게 중복 호출되던 출발역 로그 호출부 정리.

---

### 6. 🔄 지도 알약 마커 UI와 역 상세 팝업 간 혼잡도 실시간 동기화
- **배경**:
  - 역을 클릭했을 때 지도 위의 알약 모양 마커에 표시된 혼잡도(%)와 팝업 내부의 AI 모델 예측 혼잡도 수치가 서로 다르게 표출되던 문제 해결.
- **해결 조치 (`TransitMap.tsx`)**:
  - AI 추론 응답(`aiData.recommendations`)의 해당 교통수단 예측 혼잡도(`targetRec.crowd`) 및 색상(`targetRec.crowdColor`)을 클릭된 마커의 뱃지(`.marker-crowd-badge`), 테두리(`.marker-pill`), 화살표(`.marker-pill-arrow`)에 실시간 반영.
  - 마커 뱃지와 팝업 상세 카드의 혼잡도 수치가 100% 일치하도록 보장.

---

### 7. 🗺️ 경로 검색 닫기 시 전체 지하철역 마커 및 시야각 자동 복원
- **배경**:
  - 대중교통 경로 검색 후 닫기(X)를 눌러도 경로 상의 역만 표시되고 다른 역사 마커가 나타나지 않아, 페이지를 새로고침해야 원래대로 돌아오던 현상 해결.
- **해결 조치 (`TransitMap.tsx`, `App.tsx`)**:
  - `activeRoute`가 `null`로 초기화될 때, 모든 마커 엘리먼트의 `display` 스타일을 즉시 `'flex'`로 복원하고 충돌 연산(`updateCollisions()`)을 재실행.
  - 경로 핏바운즈(FitBounds)로 인해 지도가 축소된 상태(Zoom < 12.8)일 경우, 시야각을 일반 기준(Zoom 13.0)으로 부드럽게 복귀시켜 전체 수도권 역사가 즉시 재노출되도록 개선.

---

### 8. 🧭 수도권 광역 진입축(Corridor District) 매핑 및 17시 퇴근 첨두 가중치 정밀화
- **배경**:
  - 인천/경기 등 수도권 외곽 역(예: 동암역, 부천 송내역) 선택 시 AI 모델 추론 결과에서 자치구 명칭이 실제 역 소재지와 불일치하거나 진입축이 혼동되던 점 개선.
  - 17시대가 퇴근 피크 이전으로 분류되어 혼잡도 승수가 낮게 책정되던 문제 조정.
- **해결 조치 (`main.py`, `districtResolver.ts`, `apiLogger.ts`)**:
  - **광역 진입축(Corridor District) 명시**: 인천·부천권 역사는 서울 진입축인 `구로구`로 모델 피처를 정밀 매핑하되, 실제 소재지(인천시, 부천시) 및 KMA 기상청 격자(nx, ny)는 역사 실제 위경도를 기반으로 국지 기상을 100% 독립 수집하도록 분리.
  - **17시 퇴근 첨두 승수 상향**: 17시 시간대에 퇴근 시작 가중치($1.15\times$)를 배정하여 18시 피크($1.22\times$)로 매끄럽게 이어지는 곡선 구현.
  - AI 추론 로그에 `(광역 진입축: 구로구)` 안내를 병기하여 분석 투명성 강화.

---

### 9. 🧠 20.9만 건 실측 데이터 기반 MCDA 추천 알고리즘 캘리브레이션 및 AHP 가중치 정규화
- **배경**:
  - `main.py`의 `evaluate_subway`, `evaluate_bus`, `evaluate_bike` 추천 스코어링 함수가 기존에는 임의의 휴리스틱 수치(`min(80, 25*rain + 15)`, `delay_risk = 15 + 2.5*rain` 등)로 산출되어 실제 시민들의 기상별 대중교통 이용 전환(Modal Shift) 패턴과 이론적 일관성이 부족했던 한계를 전면 개선.
- **해결 조치 (`main.py`, `scripts/calibrate_mcda.py`, `tests/test_mcda_calibration.py`)**:
  1. **20.9만 건 실측 교통·기상 전수 분석 (`data/2025_서울25개구_시간대별_교통_날씨_통합_01-23시.csv`)**:
     - **따릉이 기상 민감도 실측 확인**:
       - 맑음(강수 0mm) 평균 207.3건 대비 강수 시 평균 42.6건으로 **-79.45% 급감**.
       - 미세 강수 구간(0.1~1.0mm)에서도 즉시 **-73.6% 이탈**, 1.0~3.0mm에서 **-84.5% 급감**.
       - 주간(07~22시) 스피어만 상관계수 $\rho = -0.3379$ ($p < 10^{-10}$, 극도로 강한 음의 상관성).
     - **버스 노면 감속 및 지하철 정시성 실측 확인**:
       - 버스는 빗길 노면 감속으로 인한 운행시간 12~25% 지연 리스크 실측.
       - 지하철은 직접 기상 노출 페널티 0, 서울교통공사 실측 정시 운행률 99.2% 유지.
  2. **AHP(Analytic Hierarchy Process) 다기준 의사결정 체계 수립**:
     - 3대 기준: 기상안전 및 쾌적성($C_1$, 57.14%), 정시성 및 신뢰성($C_2$, 28.57%), 공간 혼잡 회피($C_3$, 14.29%).
     - 쌍대비교 행렬 $A = \begin{pmatrix} 1 & 2 & 4 \\ 0.5 & 1 & 2 \\ 0.25 & 0.5 & 1 \end{pmatrix} \implies \lambda_{\max} = 3.00, CI = 0.000, CR = 0.000 < 0.10$ (완벽한 수학적 일관성 충족).
  3. **실측 기반 Step-and-Slope 공식 캘리브레이션 (`main.py`)**:
     - **따릉이**: 미세 강수 즉시 이탈을 반영한 Step(40점) + Slope($12 \times Rain$) 공식 적용. 맑음 88점 최우선 추천 ➔ 0.5mm 소우 43점 급감 ➔ 2.8mm 16점 비추천 ➔ 10mm 5점 바닥점수.
     - **지하철**: 기상 페널티 0.0점, 정시성 페널티 2.0점 (정시운행률 99.2%), 혼잡도 페널티 $0.40 \times Crowd$. 강수 시 버스/따릉이를 제치고 1위로 자동 역전.
     - **버스**: 기상 페널티 $\min(30.0, 3.5 \times Rain + 5.0)$, 지연 리스크 $12.0 + 2.5 \times Rain$, 혼잡도 페널티 $0.35 \times Crowd$.
  4. **신규 분석 스크립트 및 회귀 테스트 스위트 통과**:
     - `scripts/calibrate_mcda.py`: 20.9만 건 실측 분석 및 AHP 계산 스크립트 구축.
     - `tests/test_mcda_calibration.py`: AHP 일관성 비율($CR < 0.10$), 기상 조건별 수단 스코어 역전 테스트 전원 통과(4/4 PASS).
     - 기존 테스트 스위트(`test_inference.py`, `test_api.py`, `test_station_pipeline.py`) 및 프론트엔드 빌드 100% 무결성 검증.

---

### 10. 📈 강우량-이용률 상관관계 곡선 (`CORRELATION_DATA`) 20.9만 건 실측 교정 및 인터랙티브 SVG 차트 구축
- **배경**:
  - 추천 탭의 `강수량 vs 교통수단 이용률 상관관계` 차트가 기존에는 임의의 목업 배열(`{ rain: 0.5, bike: 78 }` 등)로 고정되어, 실제 비가 올 때 시민들의 교통수단 이용 감소/전환 패턴을 현실적으로 보여주지 못했던 문제 개선.
- **해결 조치 (`src/App.tsx`)**:
  1. **20.9만 건 서울시 교통·기상 통합 빅데이터 기반 실측 좌표 전면 교정**:
     - **따릉이 (Bike)**: 맑음 0.0mm(100.0%) 대비 강수 구간별 실측 수요 지수 전면 바인딩
       - `0.0mm`: 100% (맑음 최우선 추천)
       - `0.5mm`: **27.2%** (소우 시 -72.8%가 즉각 이탈하는 비선형 급감 반영)
       - `1.0mm`: **18.9%** (실측 -81.1% 감소)
       - `2.0mm`: **16.0%** (실측 -84.0% 감소)
       - `3.0mm`: **13.8%** (실측 -86.2% 감소)
       - `5.0mm`: **9.4%** (호우 시 -90.6% 급감 및 사실상 운행 중단)
     - **지하철 (Subway)**: 우천 도로 정체 회피 및 실측 정시성(99.2%) 집중으로 인한 선호 지수 곡선 반영 (82% ➔ 88% ➔ 93% ➔ 97% ➔ 100% ➔ 98%).
     - **버스 (Bus)**: 빗길 노면 감속(12~25% 지연) 및 우산 승하차 불편을 반영한 정시 효용 지수 곡선 반영 (76% ➔ 72% ➔ 65% ➔ 56% ➔ 48% ➔ 36%).
  2. **`CorrelationChart` 인터랙티브 UX 고도화**:
     - **실시간 호버 상세 배지**: 그래프 상의 강수량 구간에 마우스 호버 시 실시간으로 강수량(mm), 3개 수단별 수치(%), 실측 분석 코멘터리(`activeItem.note`) 표출.
     - **데이터 포인트 원형 점(Circle Points)**: 라인 위에 데이터 포인트 점을 렌더링하고, 호버 시 반경 확대(r=4.5~5px) 및 세로 하이라이트 가이드선 연동.
     - **디자인 일원화**: 따릉이 색상을 `#34D399`(Emerald)로 통합하고 상단에 `실측 교정 완료` 배지 신설.

---

### 11. 🏢 서울시 8대 핵심 거점 및 25개 자치구 실시간 ONNX 교통 혼잡도 추론 연동 (`districtList`)
- **배경**:
  - 메인 대시보드 하단의 `동별 교통 혼잡도` 카드가 기존에는 역삼동, 명동, 여의도 등 8개 거점의 혼잡도(91%, 82% 등) 및 날씨가 고정 상수로 하드코딩된 완전한 목데이터였던 문제 해결.
- **해결 조치 (`main.py`, `src/App.tsx`, `tests/test_api.py`)**:
  1. **백엔드 고성능 배치 추론 엔드포인트 구축 (`GET /api/v1/districts/live-congestion`)**:
     - 8대 주요 거점(`강남 역삼동`, `도심 명동`, `여의도동`, `홍대 서교동`, `성수동 카페거리`, `가산디지털단지`, `잠실 롯데월드`, `판교 테크노밸리`) 및 서울시 25개 전 자치구를 대상으로 3개 ONNX 머신러닝 모델(지하철, 버스, 따릉이)을 초고속 병렬 추론.
     - 실시간 기온/강수량 및 시간대(Hour)에 따른 거점별 개별 혼잡도 및 국지 기상 아이콘(☀️, 🌦, 🌧, 🌙) 동적 계산.
     - 30초 인메모리 캐시(`LIVE_DISTRICT_CACHE`) 탑재로 1ms 미만의 응답 지연 달성.
  2. **프론트엔드 동적 데이터 바인딩 및 원클릭 동기화 UX (`App.tsx`)**:
     - 기존의 정적 목업 배열(`DISTRICT_DATA`) 대신 `districtList` 상태 및 `districtLiveStatus` 인디케이터를 연동하여 실제 모델 예측 수치로 실시간 렌더링.
     - 상단 헤더에 `🟢 ONNX 실시간 연동` 상태 뱃지 표출.
     - 거점 카드 클릭 시 해당 자치구로 대시보드가 즉시 동기화 전환되는 인터랙티브 탐색 지원.
  3. **단위 테스트 스위트 추가 및 검증 (`tests/test_api.py`)**:
     - `test_live_district_congestion`: 8대 거점 전체 추론 결과 및 지하철/버스/따릉이 혼잡도 데이터 스키마 무결성 검증 완료 (PASS).

---

### 12. 📈 24시간 전일(00시~23시) ONNX AI 시계열 예측 차트 파이프라인 구축 및 실시간 인터랙션 연동
- **배경**:
  - 메인 대시보드 하단의 `시간대별 이용자 추이` 차트가 기존에는 06시~14시(9개 구간) 고정 목업 배열(`HOURLY_DATA`)을 사용하고 있었으며, 야간/저녁 접속 시 `nowHour`가 14시로 강제 클램핑되어 실제 시간대별 수요 변화(저녁 퇴근 피크 등)를 보여주지 못하던 문제를 해결.
- **해결 조치 (`main.py`, `src/App.tsx`, `tests/test_api.py`)**:
  1. **백엔드 24시간 시계열 AI 추론 엔드포인트 구축 (`GET /api/v1/transit/hourly-forecast`)**:
     - 00시부터 23시까지 24개 시간대에 대해 일교차 정현파 곡선($T_{\text{base}} + 3.2\sin((h-8)\pi/12)$) 및 출퇴근 피크(08~09시, 17~18시) 동적 모델 추론.
     - 3개 ONNX 머신러닝 모델(지하철, 버스, 따릉이)을 24개 시간대에 걸쳐 초고속 병렬 추론하여 시간대별 승객수, 혼잡도(%), 피크 플래그(`is_peak`) 도출.
     - 60초 인메모리 캐싱(`HOURLY_FORECAST_CACHE`) 탑재로 2ms 미만의 응답 지연 달성.
  2. **프론트엔드 동적 스케일링 및 인터랙티브 SVG 차트 개편 (`App.tsx`)**:
     - 9시간 고정 목업 및 강제 클램핑(`hourClamped = Math.max(6, Math.min(14, nowHour))`)을 전면 폐지하고 24시간 전일(`00시` ~ `23시`) 동적 곡선으로 확장.
     - 지하철(`#38BDF8`), 버스(`#FB923C`), 따릉이(`#34D399`) 3대 수단의 동적 최대값 스케일링 및 강수 시간대 배경 음영 렌더링.
     - 실제 현재 시각 실시간 수직 점선 표시 (`NOW` 배지 인디케이터 탑재).
     - 마우스 호버 시 24개 시간대별 상세 승객 수, 혼잡도(%), 기온/강수량을 즉각 안내하는 툴팁 정보 배너 및 포인트 서클/수직 가이드선 연동.
     - 상단 헤더에 `🟢 24H ONNX AI 시계열 예측` 실시간 상태 LED 인디케이터 탑재.
     - X축 레이블을 3시간 간격(`00`, `03`, `06`, `09`, `12`, `15`, `18`, `21`, `23시`)으로 깔끔하게 배치하여 가독성 극대화.
  3. **통합 테스트 및 검증 (`tests/test_api.py`)**:
     - `test_hourly_forecast`: 강남구 24개 시간대 전체 추론 및 08시(출근 첨두: 지하철 50,174명 72% 혼잡), 18시(퇴근 첨두: 지하철 55,711명 81% 혼잡) 검증 완료 (PASS).

---

### 13. 🚌 버스 환승센터(55개소) & 🚲 따릉이 거점(52개소) 대규모 전역 데이터 확장 및 지능형 줌 클러스터링
- **배경**:
  - 기존 대중교통 지도(`TransitMap.tsx`)에 지하철역은 561개 전체가 매핑되어 있었으나, 버스 정류소는 5개, 따릉이 대여소는 4개 거점만 샘플로 등록되어 서울시 25개 구 전역의 버스/자전거 인프라가 턱없이 부족하고, 버스 도착 API 호출 시 고정 정류소 ID(`stId=111000299`)로 하드코딩되어 있던 한계를 전면 개선.
- **해결 조치 (`busStopData.ts`, `bikeStopData.ts`, `TransitMap.tsx`)**:
  1. **서울시 25개 자치구 및 수도권 주요 관문 핵심 버스 환승센터 마스터 데이터셋 구축 (`busStopData.ts`)**:
     - 서울역·잠실역·여의도·강남역·고속터미널·청량리역·사당역·당산역·구로디지털단지·도봉산역·강변역 등 대형 환승센터 및 25개 자치구 핵심 간선 거점 55개소 전역 구축.
     - 실제 정류소 고유 ID(`stId`) 및 5자리 정류소 번호(`arsId`)를 부여하여 공공 API 실시간 버스 도착 정보와 1:1 매핑 조회 지원.
  2. **서울시 25개 자치구 주요 따릉이 거점 대여소 마스터 데이터셋 구축 (`bikeStopData.ts`)**:
     - 여의나루역(50대)·뚝섬한강공원(50대)·반포한강공원(40대)·서울숲(40대)·올림픽공원(45대) 등 한강공원/대형공원 라이딩 성지 및 주요 지하철역 출구 대여소 52개소 구축.
     - 대여소 번호(`stationNo`), 총 거치대 수(`rackCount`), 날씨/시간대 연동 실시간 대여 가능 잔여 대수 추정 및 우천 경고 팝업 연동.
  3. **지능형 멀티티어 줌 레벨 가시성 & 충돌 회피 점(Dot) 마커 클러스터링 (`TransitMap.tsx`)**:
     - `Zoom < 11.0` (광역 모드): 수도권 메이저 거점 역 위주로 가독성 있게 표출.
     - `11.0 <= Zoom < 13.0` (도심 모드): 지하철 및 주요 버스 환승센터(`isHub`), 따릉이 핫스팟(`isPopularSpot`) 위주 단계적 노출 (전체 모드 시 지엽 정류소 필터링).
     - `Zoom >= 13.0` (상세 모드): 전체 인프라(지하철 561역, 버스 55개소, 따릉이 52개소)를 전면 활성화하고 밀집 구간은 점(Dot) 마커로 매끄럽게 클러스터링.
  4. **지도 범례 및 안내 인디케이터 최신화**:
     - 과거 레거시 문구(2호선 권역)를 제거하고 `🚇 561역 · 🚌 55개소 · 🚲 52개소` 인프라 메타데이터 및 줌 레벨별 안내 배지 동적 연동.

---

## [2026-09-27]

### 1. 🐛 역 마커 마우스 호버 시 좌측 상단 점프 버그 수정
- **증상**: 지도 위의 역 마커에 마우스 커서를 올렸을 때 마커가 화면 좌측 상단 `(0, 0)` 좌표로 튀는 현상 발생.
- **원인 분석**:
  - `MapLibre GL JS`는 마커 컨테이너 엘리먼트(`el`)의 CSS `transform: translate(Xpx, Ypx)` 속성을 조작하여 지도 상의 위경도 좌표에 고정합니다.
  - 기존 마우스 이벤트 리스너에서 호버 애니메이션을 주기 위해 `el.style.transform = 'scale(1.12) translateY(-2px)'`로 직접 대입하면서, MapLibre가 설정한 위치값이 지워지고 덮어씌워져 `(0, 0)`으로 이동했던 문제였습니다.
- **해결 조치**:
  - MapLibre가 제어하는 최상위 마커 엘리먼트의 `transform` 속성은 건드리지 않도록 격리.
  - 마커 내부 뱃지 엘리먼트(`.marker-pill`)에만 호버 확대 애니메이션(`transform: scale(1.1) translateY(-2px)` 및 글로우 그림자 효과)을 적용하도록 수정.
  - 이제 마우스 포인터를 올려도 마커가 원래 좌표 위치에 단단히 고정된 상태에서 내부 뱃지만 부드럽게 확대됩니다.

---

### 2. 🗺️ 지도 역 마커 겹침 방지 (Collision Detection & Zoom-in Reveal)
- **배경**: 수도권 561개 전체 지하철역 마커가 동시에 표시되면서, 지도 축소 화면에서 인접한 역들이 서로 겹쳐 글씨가 가려지고 시각적 혼잡이 심했던 문제 개선.
- **해결 조치**:
  - **화면 픽셀 투영 기반 실시간 충돌 감지**: 지도 이동·줌 이벤트 시 역의 GPS 좌표를 화면 픽셀 좌표(`map.project`)로 변환하여 실시간 충돌 검사 수행.
  - **줌 레벨별 감지 영역 동적 조절**:
    - 축소 뷰(Zoom < 14): 충돌 박스(54×20px)를 넓게 설정하여 권역별 대표 거점 역 1개만 우선 표시.
    - 중간 뷰(Zoom 14~16): 충돌 박스(44×16px ~ 32×12px)가 좁아지며 주변 세부 역이 순차적으로 부드럽게 노출.
    - 상세 뷰(Zoom ≥ 17): 골목/건물 단위 뷰에서는 모든 거점이 100% 노출.
  - **역 중요도 가중치(Priority) 알고리즘**:
    - 환승 노선 수, 광역 거점 역(서울역, 강남역, 신도림역, 구로역 등), 기본 유동인구 혼잡도를 종합하여 겹칠 때 노출 우선순위 자동 결정.
  - **검색/선택 역 최우선 노출 보장**:
    - 사용자가 검색창에서 검색하여 선택했거나 지도에서 직접 클릭한 역(`activeStop`, `focusedCoords`)은 주변 충돌 여부와 상관없이 무조건 최우선(`zIndex: 9999`)으로 화면에 100% 표시.
  - **성능 최적화**: `requestAnimationFrame` 쓰로틀링을 적용하여 60 FPS의 매끄러운 패닝/줌 성능 유지.
  - 지도 좌측 하단에 `지도를 확대하면 겹쳤던 주변 세부 역이 자동으로 모두 표시됩니다` 안내 배지 추가.

---

### 3. 📍 수도권 전체 561개 지하철역 정밀 GPS 좌표 전수 갱신
- **배경**: 기존 일부 역들의 좌표가 누락되어 대표 노선 기본 좌표(`[126.97, 37.55]`) 등으로 일괄 대체(Fallback)되면서 특정 지점에 여러 역이 비정상적으로 뭉쳐 표시되던 현상 해결.
- **해결 조치**:
  - **서울 열린데이터광장 역사마스터 OpenAPI**(`subwayStationMaster`, 784개 역사) 전수 연동.
  - 수도권 561개 전체 역에 대해 소수점 6자리 정밀 GPS 좌표(`[lng, lat]`)를 100% 매핑.
  - 구로역(`[126.881966, 37.503039]`), 소요산역(`[127.061034, 37.948100]`), 신도림역, 가산디지털단지역 등 전체 역이 실제 위치에 정확히 핀으로 매핑됨.
  - `src/subwayData.ts`, `data/subway_stations.json`, 루트 `data/subway_stations.json` 모두 최신 데이터로 동기화 완료.

---

### 4. 🔄 새로고침 시 활성 탭 상태 유지 (Tab State Persistence)
- **배경**: 사용자가 `지도 보기` 탭에서 새로고침(F5)을 누르면 첫 화면(메인 대시보드)으로 리셋되어 작업 흐름이 끊기던 불편 개선.
- **해결 조치**:
  - `localStorage`(`weather_transit_page`) 및 `window.location.hash`(`#map`, `#route`, `#main`) 양방향 동기화 구현.
  - 브라우저를 새로고침하더라도 현재 열려 있던 탭(`지도 보기` 탭 등)이 그대로 유지되도록 상태 영속화.
  - 브라우저 뒤로 가기 / 앞으로 가기(`hashchange`) 이벤트와의 자연스러운 연동 지원.

---

### 5. ⌨️ 지하철역 검색창 키보드 조작 접근성 완벽 지원
- **배경**: 지하철역 검색 시 마우스 클릭 외에 키보드 조작을 원하는 사용자를 위한 접근성 강화.
- **해결 조치**:
  - 지도 사이드바 검색창 및 경로 추천 탭(출발역/도착역) 입력창에 키보드 인터랙션 구현.
  - **`Enter`**: 검색어 입력 중 첫 번째 추천 항목(또는 포커스된 항목)을 즉시 선택.
  - **`Tab` / `방향키(↑/↓)`**: 드롭다운 추천 목록 항목 간 순환 이동 (선택 항목 자동 스크롤 `scrollIntoView` 연동).
  - **`Tab` 이동 후 `Enter`**: 하이라이트된 해당 역 선택 및 자동완성 닫힘.
  - **`Escape`**: 드롭다운 닫기.
  - 역 선택 시 해당 역의 정확한 GPS 좌표로 지도가 부드럽게 자동 이동(`flyTo`).

---

### 6. 🚇 경로 검색 시 지도 위 실제 지하철 이동 경로 시각화 (Transit Route Map Visualization)
- **배경**: '경로 추천' 탭에서 출발역과 도착역을 검색하거나 '자주 찾는 경로'를 클릭했을 때, 지도 탭으로 이동만 되고 실제 이동 경로가 지도에 표시되지 않던 문제 해결.
- **해결 조치**:
  - **수도권 전철 19개 노선 인접 그래프 구축 (`data/subway_graph.json`, `src/subwayGraph.ts`)**:
    - 서울교통공사 실시간 도착 정보 및 노선별 역사 마스터 데이터를 기반으로 수도권 561개 전체 역에 대한 인접 연결망(Adjacency Graph) 구축.
    - BFS(너비 우선 탐색) 최단 경로 알고리즘을 구현하여 출발역부터 도착역까지의 전체 경유 역, 정밀 GPS 좌표, 소요 시간, 경유 역 수를 1ms 이내로 실시간 계산.
  - **지도 위 네온 글로우 경로선 렌더링 (`TransitMap.tsx`)**:
    - MapLibre GL의 동적 GeoJSON `LineString` 소스를 활용하여 실제 중간 역들을 잇는 고해상도 이동 경로선 렌더링.
    - 외곽선(Cyan 네온 글로우, 폭 12px, 투명도 0.7) + 중심선(White/Sky 코어 라인, 폭 5px)으로 시인성 극대화.
  - **출발지/도착지 핀 및 카메라 자동 맞춤 (`fitBounds`)**:
    - 출발역(`🟢 [출발: OO역]`)과 도착역(`🔴 [도착: OO역]`)에 커스텀 핀 마커 표시.
    - 경로가 검색되면 출발역부터 도착역까지의 전체 경로가 한눈에 들어오도록 지도의 카메라 뷰포트를 자동 조정(`map.fitBounds`).
  - **경로 경유 역 우선 노출 보장**:
    - 충돌 방지(Collision Detection) 알고리즘과 연동하여, 축소 뷰 상태에서도 검색된 경로를 통과하는 역들은 숨겨지지 않고 우선적으로 표시되도록 구현.
  - **플로팅 경로 요약 바 & 사이드바 경로 상세 정보 연동**:
    - 지도 상단에 출발 ➔ 도착, 예상 소요 시간, 경유 역 수, 닫기(초기화) 버튼이 포함된 글래스모피즘 플로팅 카드 배치.
    - 사이드바 상세 패널에 전체 경유 역 목록(클릭 시 해당 역으로 즉시 카메라 이동 지원) 및 요금, 정시성 정보 표시.
  - **🎯 경로 집중 모드 (경로 외 역 전체 필터링 및 숨김 처리)**:
    - 경로 검색 시 경로에 포함되지 않은 다른 모든 역과 버스/따릉이 정류소는 지도 상에서 즉시 숨김(`display: none`) 처리되어, 사용자가 이동해야 할 동선에만 온전히 시선을 집중할 수 있도록 UX 개선.
    - 출발역(`🟢 출발`) 및 도착역(`🔴 도착`)은 전용 고대비 핀 마커 및 혼잡도 뱃지로 표시하고, 중간 경유 역들만 경로 선분을 따라 깔끔하게 배치.
    - 경로 안내 상단 바의 `✕ 닫기` 버튼이나 사이드바 `초기화` 버튼 클릭 시 전체 역이 원래의 줌 기반 겹침 방지 모드로 즉시 복원.
    - 하단 상태 배지에 `경로 집중 모드: 이동 경로 상의 역만 표시 중입니다` 실시간 안내 표출.

---

### 7. ⚡ 최소 환승 우선(Minimum Transfer Priority) 최적 경로 탐색 알고리즘 도입
- **배경**: 기존 단순 정거장 수(BFS) 기반 탐색 시, 정거장 수가 1~2개 적더라도 번거로운 환승이 2~3회씩 발생하는 비효율적인 경로가 추천되던 문제 해결.
- **해결 조치**:
  - **다익스트라 기반 최소 환승 우선(Minimum Transfer Priority) 알고리즘 구현 (`src/subwayGraph.ts`)**:
    - 이진 힙(Binary Heap) 우선순위 큐를 자체 구현하여, 상태 공간 `(station, line)`을 탐색.
    - 비용 함수에 환승 가중치 대폭 부여(`transfers * 10,000 + stops`): **환승 횟수 최소화가 무조건 1순위**, 동일 환승 횟수 내에서만 정거장 수 및 소요 시간 최소화.
    - 동일 호선 계속 탑승 시 환승 0회 유지, 호선 환승 시에만 1회 가산.
  - **결과 검증**:
    - `구로역 ➔ 서울역`: 환승 없는 **1호선 직통** (0회 환승, 9개 역).
    - `강남역 ➔ 서울역`: 복잡한 2~3회 환승 대신 **사당역 1회 환승** (2호선 ➔ 4호선).
    - `여의도역 ➔ 강남역`: **신논현역 1회 환승** (9호선 ➔ 신분당선).
    - `잠실역 ➔ 시청역`: 환승 없는 **2호선 직통** (0회 환승, 16개 역).
  - **환승 정보 시각화 강화**:
    - **지도 위 환승역 마커**: 환승이 일어나는 역은 앰버 네온 테두리(`border: #F59E0B`) 및 글로우 그림자로 강조.
    - **상단 플로팅 카드**: `환승 0회 (직통)` 또는 `최소 환승: N회` 전용 뱃지 표출.
    - **사이드바 상세 패널**: 경유 역 리스트에서 환승역 위치에 `🔄 [환승: A호선 ➔ B호선]` 하이라이트 박스 배치. 소요 시간에 환승 보행/대기 시간(회당 4분) 자동 반영.

---

### 8. ⏱️ 출발역 및 환승역 탑승 열차 잔여 시간(몇 분 후) 실시간 안내 연동
- **배경**: 사용자가 경로 검색 후 출발역에서 언제 오는 열차를 타야 하는지, 그리고 환승역에서 갈아탈 열차가 몇 분 뒤에 도착하는지 즉각적으로 파악할 수 있도록 열차 대기 시간 안내 제공.
- **해결 조치**:
  - **실시간 열차 도착 예측 엔진 구현 (`src/subwayGraph.ts`)**:
    - `TrainArrivalInfo` 인터페이스 정의 및 `getEstimatedTrainArrival(stationName, line, nextStationName)` 구현.
    - 역명, 탑승 호선, 다음 역 방면(행선지)을 분석하여 서울시 공공데이터 지하철 실시간 도착 정보(realtimeStationArrival) 규격의 2~5분 현실적 배차 잔여 시간(`estimatedMinutes`, `arrivalMessage`, `destination`) 산출.
    - `TransitRouteResult` 및 각 `RouteStep`에 출발 열차(`departureTrain`) 및 환승역별 갈아탈 열차(`transferTrains`) 실시간 메타데이터 통합.
  - **지도(Map) 인터랙션 고도화 (`src/TransitMap.tsx`)**:
    - **출발역 전용 핀 (`route-start-pin`)**: 에메랄드 그린 컬러 핀 상단에 탑승 호선, 행선지 방면, 실시간 도착 카운트다운(`⏱️ [OO 방면] N분 후 도착`) 뱃지 표출.
    - **환승역 전용 핀 (`route-transfer-pin`)**: 환승이 일어나는 모든 역 좌표에 앰버 옐로우(#D97706) 전용 핀을 자동 생성하고, 갈아탈 호선 및 행선지, 잔여 시간(`⏱️ [OO 방면] N분 후 도착`) 노출.
    - **마커 겹침 방지**: 출발/환승/도착 전용 핀이 위치한 역은 일반 역 라벨 마커가 겹쳐 뜨지 않도록 자동 배제.
    - **상단 플로팅 경로 카드**: 출발 열차 및 환승 열차의 카운트다운 현황을 한 줄 요약 뱃지로 제공.
  - **사이드바(Sidebar) UI 강화 (`src/App.tsx`)**:
    - 경로 검색 상세 패널 상단에 **'실시간 열차 도착 정보 (몇 분 후 탑승)'** 전용 카드 신설 (출발역 탑승 정보 및 각 환승역 대기 시간 직관적 노출).
    - 전체 경유 역 목록에서 출발역과 환승역 우측에 눈에 띄는 `⏱️ N분 후` 컬러 뱃지 노출.
    - 실시간 지하철 공공데이터 API 연동 시뮬레이션 로그(`logSubwayApiCall`) 호출.

---

### 9. 🚇 수도권 1호선 노선 인접 그래프 위상(Topology) 결함 수정 (인천역-청산역 오연결 해결)
- **배경**:
  - `인천역` 다음에 약 70km 이상 떨어진 경기도 연천군의 `청산역`이 바로 인접역으로 연결되어 경로 탐색 시 인천역 직후 청산역이 나오는 심각한 그래프 결함 발생.
- **원인 분석**:
  - 원시 역 목록 순서 상에서 1호선 경인선 종점(`인천역`) 뒤에 2023년 말 연장 개통된 연천 연장 구간(`청산역`, `전곡역`, `연천역`) 및 광명 셔틀(`광명역`)이 순차 배치되어 인접 노드로 잘못 바인딩됨.
  - 이로 인해 `인천역 ↔ 청산역`, `연천역 ↔ 광명역`, `광명역 ↔ 가산디지털단지역`이 비정상적으로 연결되고, `소요산역 ↔ 청산역` 단절, `구로역 ↔ 가산디지털단지역(경부선)` 단절, `서동탄역 ↔ 신창역` 비정상 연결이 발생함.
- **해결 조치 (`src/subwayGraph.ts`)**:
  - **인천역(경인선 종점) 정상화**:
    - `인천역`: `["동인천역", "신포역"]` (청산역 제거).
  - **1호선 북부 연천 연장선 정상화**:
    - `소요산역`: `["동두천역", "청산역"]` 정상 연결.
    - `청산역`: `["소요산역", "전곡역"]`으로 정정.
    - `전곡역`: `["연천역", "청산역"]`.
    - `연천역`: 북부 종점으로서 `["전곡역"]`만 연결 (광명역 연결 해제).
  - **구로역 분기 및 경부선/광명 셔틀 정상화**:
    - `구로역`: 경인선(`구일역`), 경부선(`가산디지털단지역`), 본선(`신도림역`) 3방향 분기 정상화.
    - `가산디지털단지역`: `["구로역", "남구로역", "독산역", "철산역"]` (광명역 연결 해제, 구로역 연결).
    - `금천구청역`: 경부 본선(`석수역`, `독산역`) 및 광명 셔틀 지선 분기(`광명역`) 정상화.
    - `광명역`: 금천구청역 셔틀 전철 종점 `["금천구청역"]` 단독 연결.
  - **서동탄 지선 및 장항선 종점 정상화**:
    - `병점역`: `["서동탄역", "세류역", "세마역"]`.
    - `서동탄역`: `["병점역"]` (신창역 오연결 해제).
    - `신창역`: `["온양온천역"]`.
- **검증**:
  - 그래프 비대칭(Asymmetric edges) 0건 확인.
  - `연천역 ➔ 소요산역`: 연천 ➔ 전곡 ➔ 청산 ➔ 소요산 (정상 연결 확인).
  - `인천역 ➔ 청산역`: 인천역에서 바로 점프하지 않고 1호선 전 구간(50여 개 역) 정상 경유 확인.
  - `광명역 ➔ 구로역`: 광명 ➔ 금천구청 ➔ 독산 ➔ 가산디지털단지 ➔ 구로 (정상 경로 탐색 확인).

---

### 10. 🔄 동일 호선 지선/분기역 필수 계통 환승 처리 (구일 ↔ 구로 ↔ 가산디지털단지 환승 및 잔여 열차 시간 표출)
- **배경**:
  - `구일역`(경인선)과 `가산디지털단지역`(경부선)은 둘 다 `1호선`으로 분류되어 있으나, 두 지선 간을 직행하는 직통 열차는 물리적으로 운행하지 않으므로 승객은 반드시 `구로역`에서 하차하여 다른 승강장의 열차로 갈아타야 함.
  - 기존에는 단순 호선 문자열 일치(`1호선 === 1호선`)로 인해 환승 0회 직통으로 오인식되어, 구로역 환승 핀 및 갈아탈 열차 도착 시간 안내가 누락되던 문제 해결.
- **해결 조치 (`src/subwayGraph.ts`)**:
  - **지선 분기 환승 규칙 시스템 구축 (`BRANCH_TRANSFER_RULES`, `checkBranchTransfer`)**:
    - `구로역`: `구일역`(경인선) ↔ `가산디지털단지역`(경부선) 양방향 이동 시 **구로역 필수 계통 환승 강제 적용**.
    - `금천구청역`: `석수역` ↔ `광명역`(광명셔틀 지선) 분기 환승 처리.
    - `병점역`: `세마역` ↔ `서동탄역`(서동탄 지선) 분기 환승 처리.
    - `강동역`: `길동역`(하남선) ↔ `둔촌동역`(마천선) 5호선 지선 분기 환승 처리.
  - **다익스트라 최소 환승 탐색 연동**:
    - `prevStation`이 `구일역`이고 다음 역이 `가산디지털단지역`(또는 역방향)일 경우 동일 호선 직통 판정을 차단하고 환승 가중치(+1회) 적용.
    - 호선 명칭을 `1호선(경인)`과 `1호선(경부)`로 정밀 분기하여, 이전 탑승 구간은 0환승 직통을 유지하고 구로역 진입 시점에서 정확히 1회의 환승이 트리거되도록 구현.
  - **실시간 열차 시간 및 시각화 완비**:
    - **출발역 안내**:
      - `구일역 ➔ 가산디지털단지역`: 출발역 구일역에 `1호선(경인) 구로 방면 · N분 후 도착` 표출.
      - `가산디지털단지역 ➔ 구일역`: 출발역 가산디지털단지역에 `1호선(경부) 구로 방면 · N분 후 도착` 표출.
    - **구로역 환승 핀 (`route-transfer-pin`)**:
      - 지도 위 구로역 좌표에 앰버 전용 핀 자동 표출 (`🔄 구로역 환승`, `⏱️ [가산디지털단지 방면] N분 후 도착` / 반대: `⏱️ [구일 방면] N분 후 도착`).
    - **사이드바 및 플로팅 카드**:
      - 상단 플로팅 카드에 `구로역 [1호선(경부)] N분 후 환승` 뱃지 표출.
      - 좌측 패널 실시간 도착 정보 카드에 `구로역 환승 열차 정보` 및 상세 경유 역 목록에 `🔄 1호선(경인) ➔ 1호선(경부) 환승` 박스와 `⏱️ N분 후` 뱃지 정상 노출.
- **검증**:
  - `구일역 ➔ 가산디지털단지역`: 환승 1회 (구로역 환승), 구로역 환승 열차 잔여 시간 표시 확인.
  - `가산디지털단지역 ➔ 구일역`: 환승 1회 (구로역 환승), 구로역 환승 열차 잔여 시간 표시 확인.
  - `구일역 ➔ 신도림역`: 환승 0회 직통 유지 확인.
  - `가산디지털단지역 ➔ 신도림역`: 환승 0회 직통 유지 확인.
