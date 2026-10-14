# 📋 Weather & Transit Web 프로젝트 TODO 및 백로그 (Backlog)

본 문서는 Weather & Transit Web 서비스의 향후 개발 및 개선 과제를 관리하는 공식 TODO 리스트입니다.

---

## 📌 우선순위별 개발 백로그

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
  - **주의(정상)**: `/health.feature_schema.status` 는 현재 **`legacy-subset-25d`** 입니다 — 배포 모델이 25차원이고 스키마가 32차원이라 **레거시 서브셋 정렬로 동작하는 정상 상태**이며, `verified` 는 `models/` 를 32차원 자산(+`models/feature_schema.json`)으로 교체했을 때 나옵니다(→ `tests/test_feature_schema.py` Test 7 기대값과 일치)
  - 재검증 절차: `docker compose up -d --build` → `docker compose ps`(`backend` = `healthy`) → `GET /health`(스키마·차원 확인) → `docker compose logs backend`(`[schema]` 라인) → `python tests/test_feature_schema.py` · `python tests/test_inference.py` · `python tests/test_api.py`
  - 실패 시 확인 지점: `main.py` import 목록 ↔ `Dockerfile.backend` COPY 목록 · 스키마 탐색 경로(`--schema`/`FEATURE_SCHEMA_PATH` → `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json`)
  - 참고: `docs/DOCKER_CONTAINERIZATION_PLAN.md` §5 Phase 4-5·4-6 · `docs/CHANGELOG.md` [2026-10-14] §3
- [ ] 공공 API 서버 장애 시 자동 Fallback 서킷 브레이커 고도화
- [ ] Redis 기반 분산 캐시 레이어 도입 (대규모 트래픽 대비)

---

### 🤖 4. 32차원 실피처 모델 신규 학습 및 검증 (진행 중 — **학습·반입·평가 완료**, 배포 판단 = **전면 교체 보류** · 수단별 검토 남음)

> **배경**: 2026-10-13 파이프라인 v2 개정으로 학습·평가 기준이 **실제 32차원 실피처(8/8/5/11)** 로 확정되었고, **2026-10-14 Colab 실행으로 32차원 모델 3종 학습이 완료되어 `benchmarks/2026-10-14/` 에 반입되었습니다.** (커밋 `07292b4`)
> - **반입 자산**: `lgb_{bike,bus,subway}_demand.onnx`(ONNX 입력 `[None, 32]`, 이름 `float_input`) + `feature_schema.json`(`model_version: v2-전처리_2-32d`)
> - **선행 검증(완료)**: `feature_schema.json.feature_cols`(32개) == `benchmarks/evaluate_models.py::FEATURE_COLS_32` == `main.py::build_feature_vector` 인덱스 0~31 → **순서 완전 일치**. 공휴일 캘린더 **19일** 일치(`main.py::KR_HOLIDAYS`)
> - **노트북 기록 Test 지표**(2025-11-16~12-31, n=26,450) — 평가 스크립트 교차검증 **통과**(재현성 확인): bike R² 0.98729 / bus 0.99006 / subway 0.99515
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
- [x] **배포 판단 (Gate) — 전면 교체 보류 (2026-10-14)** — 3수단 전부 유의 우세 조건 **미충족**(bike R²·RMSE 열세 / bus MAPE 열세 / subway 우세) → **`models/` 는 25차원 유지**
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
- [ ] **`models/` 교체 판단 (신설 · 최우선)** — `benchmarks/2026-10-14/tuned_25d/`(25차원 재학습본)는 **서빙 정렬이 그대로 맞는** 교체 후보(32차원 자산 교체안과 달리 배치 변환 불필요)
  - 판단 재료: 4-way/5-way 리포트 — bus·subway 는 전 지표 개선 / bike 는 R²·RMSE 소폭 열세(MAE·MAPE 우세) → **수단별 교체(지하철·버스 우선)** 또는 bike 제외 논의 · Colab 재현본 `tuned_25d_colab/` 은 `tuned_25d` 와 **지표 완전 동일**이라 판단에 영향 없음
  - 교체 시: `models/lgb_{bike,bus,subway}_demand.onnx` 반입 → `/health.feature_schema.status` 가 `verified` 로 바뀌는지 확인 · `python tests/test_feature_schema.py` · `python tests/test_inference.py` · `python tests/test_api.py`
  - 교체 확정 시 문서 정리: `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 의 "25차원 = 32차원 − 7" 서술 기준 모델 갱신
  - 교체 전 백업/롤백: `models/` 는 `benchmarks/original/` 과 **SHA256 동일 스냅샷**으로 판정되어 있어 문제 시 즉시 원복 가능 · 교체는 **파일 단위(수단별) 부분 교체**로도 가능
- [ ] **교체 승인 기준(Gate) 확정 (신설)** — 전면 교체 기준("3수단 전부 유의 우세")으로는 이미 보류됨 → **수단별 기준**(예: subway 단독 교체 허용 조건)과 bike 처리 방침(제외/보류) 결정 필요
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
