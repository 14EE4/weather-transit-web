# `2026-10-14/` — v2 실제 32차원 **실피처** 모델 산출물 (2026-10-14 학습)

`benchmarks/CastTransit.ipynb`(v2, 실제 32차원 8/8/5/11)를 Colab에서 실행해 생성한
Optuna 튜닝 모델 3종과 메타 스키마입니다. (커밋 `07292b4`)

| 파일 | 설명 | 크기(byte) |
| :--- | :--- | ---: |
| `lgb_bike_demand.onnx` | 따릉이 대여 수요 (ONNX 입력 `[None, 32]`, `float_input`) | 7,020,769 |
| `lgb_bus_demand.onnx` | 버스 승차 수요 (입력 32차원) | 13,596,760 |
| `lgb_subway_demand.onnx` | 지하철 승차 수요 (입력 32차원) | 7,345,447 |
| `feature_schema.json` | 피처 순서(32)·분할 경계·공휴일 캘린더·튜닝 파라미터/지표 메타 | 3,296 |

## 왜 별도 폴더인가

`benchmarks/2026-10-12/tuned/` 의 구 32차원 모델은 v1 배치
(25차원 `8/8/1/3/3/2` + 상수 0 더미 7)로 학습되어 v2 실피처 배치(`8/8/5/11`)와
**컬럼 순서가 다릅니다.** 그대로 비교하면 인덱스 16 이후가 전부 어긋나므로 별도 폴더로 분리했고,
안내 README 만 남아 있던 빈 배치 위치 `benchmarks/2026-10-12/tuned_real/` 은 이 폴더로 대체되었습니다.

## 검증 (사전 확인 완료)

- `feature_schema.json.feature_cols`(32) == `evaluate_models.py::FEATURE_COLS_32` == `main.py::build_feature_vector` 인덱스 0~31 → **순서 완전 일치**
- 공휴일 캘린더 19일 == `main.py::KR_HOLIDAYS[2025]`
- ONNX 입력: 3종 모두 `[None, 32]` / 이름 `float_input`

## 노트북 기록 Test 지표 (2025-11-16 ~ 12-31, n=26,450)

| 수단 | R² | RMSE | MAE | best_iteration |
| :---: | ---: | ---: | ---: | ---: |
| 🚲 bike | 0.98729 | 17.382 | 9.669 | 834 |
| 🚌 bus | 0.99006 | 561.352 | 370.441 | 1,390 |
| 🚇 subway | 0.99515 | 662.095 | 277.633 | 865 |

> 위 수치는 노트북 자체 산출값입니다. **공정 비교·배포 판단은 아래 평가 스크립트 결과로만** 수행합니다.
> 버스는 테스트 구간 `버스_승차` 결측 24.59% 보간 영향으로 **잠정치**입니다(`docs/DATA_PREPROCESSING_HANDOFF.md` P0-1).

## 평가

```bash
# (venv) 프로젝트 루트
python benchmarks/evaluate_models.py
# → benchmarks/results/comparison_{timestamp}.json / .md 에 tuned_32d_real 3행 추가
```

`evaluate_models.py` 는 `MODEL_SETS` 기본값으로 이 폴더(`tuned_32d_real`)를 자동 포함하며,
사양서 §6.1 Temporal Split(test 2025-11-16~12-31)과 2025 대한민국 실제 공휴일 캘린더(19일)를 적용해
25차원 배포본과 **동일한 피처 프레임**에서 25차원 서브셋/전체 32차원을 각각 만들어 공정 비교합니다.

**교차검증 기준**: 산출 R²/RMSE 가 위 노트북 기록치와 소수점 수준으로 일치해야 합니다.
불일치 시 전처리 차이(버스 선형보간, 기온·습도 interpolate, `same_day_last_week` 7일 전 self-merge)를 먼저 확인하십시오.