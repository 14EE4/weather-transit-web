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

### 🛡️ 3. 시스템 안정성 및 장애 대응 (Backlog)
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
  - 교체 확정 시: `docs/AI_MODEL_SPEC.md` §3.2·§7 · `docs/BACKEND_INFERENCE_SERVER.md` §4 · `docs/SYSTEM_ARCHITECTURE.md` §6.2 의 "25차원 부분집합" 서술 정리
  - 교체 후 검증: `python tests/test_inference.py`(32차원 정합성·레이턴시 SLA) · `python tests/test_api.py`
- [ ] **해석 주의 (P0-1 미해결)** — 테스트 구간 `버스_승차` 결측 24.59%(8,625행 보간) 영향으로 **버스 수치는 잠정치**. 원천 재수집 또는 평가구간 축소 합의 후 확정
- [ ] **차원 vs 튜닝 분리 실험 (신설)** — 동일 `study.best_params` + **25차원 서브셋** 재학습 → 동일 테스트 구간 재비교 (`docs/MODEL_PERFORMANCE_REPORT.md` §7 후속 과제)
- [ ] **`feature_schema.json` SSoT 소비 (신설)** — 평가 스크립트·서빙이 스키마를 읽어 **차원·순서를 assert** 하도록 전환(피처 불일치 재발 원천 차단)
- [ ] **(데이터팀 회신 대기)** P1-1 파생 피처 7종 CSV 포함 시 노트북 하드코딩 재구성 로직 제거
- [ ] **(데이터팀 회신 대기)** P1-3 결측 대체 정책 확정 시 노트북 대체 규칙 1:1 일치화
