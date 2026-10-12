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

### 🤖 4. 32차원 실피처 모델 신규 학습 및 검증 (Next Sprint / 예정)

> **배경**: 2026-10-13 파이프라인 v2 개정으로 학습·평가 기준이 **실제 32차원 실피처(8/8/5/11)** 로 확정되었으나, **32차원 모델은 아직 새로 학습되지 않았습니다.** `benchmarks/2026-10-12/tuned_real/` 은 현재 안내 README 만 있는 **빈 배치 위치**이며, `benchmarks/results/` 의 32차원 행은 산출물 반입 후 자동으로 채워집니다.
> **관련 문서**: [데이터 전처리 인수인계서](./DATA_PREPROCESSING_HANDOFF.md) · [모델 성능 비교 보고서](./MODEL_PERFORMANCE_REPORT.md) §0 · `benchmarks/README.md` §4.2

- [ ] **학습 실행 (Colab / RunPod)** — `benchmarks/CastTransit.ipynb` [Cell 1] → [Cell 7] 순차 실행
  - 로컬 환경에 `lightgbm` · `optuna` · `onnxmltools` 미설치 → **클라우드 실행 필수**
  - [Cell 6-1] Optuna 튜닝(30 trials) + [Cell 7] ONNX export + `feature_schema.json` 생성
  - 미설치 패키지는 각 셀에서 자동 설치되도록 가드 적용됨(optuna → Cell 6-1, onnxmltools/skl2onnx → Cell 7)
- [ ] **산출물 배치** — `lgb_{bike,bus,subway}_demand.onnx` + `feature_schema.json` → `benchmarks/2026-10-12/tuned_real/`
- [ ] **평가 재실행** — `python benchmarks/evaluate_models.py`
  - 확인 항목: 피처 결측 0 / 공휴일 10,925행(5.21%) / test 26,450행 / 32차원 레이아웃(8/8/5/11) 일치
  - 결과: `benchmarks/results/comparison_<timestamp>.{json,md}` 에 `tuned_32d_real` 3행 추가
- [ ] **성능 보고서 갱신** — `docs/MODEL_PERFORMANCE_REPORT.md` §0.2 에 32차원 실측 수치 반영
  - v1 결론("개선은 전부 Optuna 튜닝 효과, 차원 증가 효과는 없음")이 v2 실피처에서도 성립하는지 **재검증**
- [ ] **해석 주의 (P0-1 미해결)** — 테스트 구간 `버스_승차` 결측 24.59%(8,625행 보간) 영향으로 **버스 수치는 잠정치**. 원천 재수집 또는 평가구간 축소 합의 후 확정
- [ ] **배포 판단** — 32차원이 25차원 대비 유의미하게 우세하면 `models/` 교체 + `docs/AI_MODEL_SPEC.md` §3.2 · `docs/BACKEND_INFERENCE_SERVER.md` §4 의 "25차원 부분집합" 서술 정리
- [ ] **(데이터팀 회신 대기)** P1-1 파생 피처 7종 CSV 포함 시 노트북 하드코딩 재구성 로직 제거
- [ ] **(데이터팀 회신 대기)** P1-3 결측 대체 정책 확정 시 노트북 대체 규칙 1:1 일치화
