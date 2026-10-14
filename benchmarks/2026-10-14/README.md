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

## 피처 스키마 소비 (SSoT · 2026-10-14)

이 폴더의 `feature_schema.json` 은 이제 **평가·서빙 코드가 직접 읽어 차원·순서를 assert 하는 단일 진실 공급원**입니다.

| 소비 지점 | 동작 |
| :--- | :--- |
| 서빙 `main.py` | 기동 시 `ModelRegistry.load_feature_schema()` → 스키마 ↔ `FEATURE_ORDER_32` ↔ **실제 ONNX 입력 차원** 3중 대조. 불일치면 기동 중단, 결과는 `GET /health` 의 `feature_schema` 블록에 노출 |
| 평가 `benchmarks/evaluate_models.py` | 실행 초반 `verify_feature_schema()` 로 순서·타깃·분할 경계 assert(`--schema` 로 경로 지정, 미지정 시 자동 탐색) · 결과를 리포트에 기록 |
| 재학습 `benchmarks/retrain_25d.py` | `metrics.*.tuned.best_params` 를 **고정 파라미터**로 소비 |
| 테스트 `tests/test_feature_schema.py` | 규격·3자 순서 일치·25차원 서브셋·ONNX 자산 차원·타깃/분할/공휴일·네거티브 가드·`/health`·**컨테이너 배포 파일 목록** **8종** |

## `tuned_25d/` — 동일 v2 파라미터 25차원 재학습 (실험 · 2026-10-14)

`benchmarks/retrain_25d.py` 가 이 폴더의 `feature_schema.json` 에 기록된 **v2 튜닝 파라미터를 그대로 고정**하고,
피처만 25차원 서빙 서브셋(`main.py::prepare_session_input` 과 동일 배치)으로 줄여 재학습한 산출물입니다.

| 파일 | 설명 | 크기(byte) |
| :--- | :--- | ---: |
| `lgb_bike_demand.onnx` | 따릉이 (입력 `[None, 25]`) | 5,709,941 |
| `lgb_bus_demand.onnx` | 버스 (입력 25차원) | 14,574,454 |
| `lgb_subway_demand.onnx` | 지하철 (입력 25차원) | 3,713,077 |
| `feature_schema.json` | 25차원 서빙 배치 스키마 (`model_version: v2-전처리_2-25d-retrain`) | 3,044 |

- **목적**: ① 차원 vs 튜닝 효과 분리(교란 3중 해소) · ② **서빙 가능한 개선본** 확보.
- **결과**(`benchmarks/results/comparison_20261014_192204.{json,md}` 4-way): bus·subway 는 배포본 대비 전 지표 개선(bus MAE −26.6 / subway MAE −38.9), bike 는 R²·RMSE 소폭 열세·MAE/MAPE 우세 → **개선분의 대부분은 튜닝 효과**, 32차원 증가의 순수 효과는 **지하철에서만** 확인됩니다.
- ✅ **Colab 재현 검증 완료(2026-10-14)** — Colab(lightgbm 4.7.0) 산출물 `tuned_25d_colab/` 과 **12개 지표 Δ = 0** · `best_iteration` 680 / 1,498 / 446 동일 → 플랫폼 편차 없음. bus 는 P0-1(결측 24.59% 보간)로 **잠정치**입니다.
- 평가: `python benchmarks/evaluate_models.py --model tuned_25d=benchmarks/2026-10-14/tuned_25d`

## `tuned_25d_colab/` — Colab 재현 산출물 (**지표 Δ=0 검증 완료** · 2026-10-14)

`benchmarks/retrain_25d_colab.ipynb` 를 Colab 에 **업로드만** 해서 실행해 얻은 산출물입니다(위 `tuned_25d/` 는 로컬 대조군으로 보존).
Colab 은 `.py` 파일을 열어 실행하는 환경이 아니므로(`retrain_25d.py` 는 `main.py`·`feature_schema.py` 까지 import 체인) **노트북 1개로 완결**되도록 설계했습니다 → 위 `CastTransit.ipynb` 의 전처리 셀 4개(`[Cell 3]`/`[Cell 4-A]`/`[Cell 4-B]`/`[Cell 5]`)를 **태그로 찾아 `exec`**(피처 드리프트 0) · Optuna 는 재탐색하지 않고 위 스키마의 `best_params` 를 **고정 주입**.

| 파일 | 설명 | 크기(byte) |
| :--- | :--- | ---: |
| `lgb_bike_demand.onnx` | 따릉이 (입력 `[None, 25]`) | 5,709,941 |
| `lgb_bus_demand.onnx` | 버스 (입력 25차원) | 14,574,454 |
| `lgb_subway_demand.onnx` | 지하철 (입력 25차원) | 3,713,077 |
| `feature_schema.json` | 25차원 스키마 (`v2-전처리_2-25d-retrain-colab`) + Colab `env` 기록 | 3,081 |
| `README.md` | 반입·검증 결과 안내 | 2,4xx |

### 검증 결과 — **로컬 `tuned_25d/` 와 플랫폼 편차 0** (`benchmarks/results/comparison_20261014_214856.{json,md}`)

| 수단 | R² | RMSE | MAE | MAPE≠0 | best_iter | 로컬 대비 Δ |
| :---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 🚲 bike | 0.9883 | 16.666 | 9.677 | 16.19% | 680 | **Δ = 0** |
| 🚌 bus | 0.9912 | 528.628 | 342.732 | 14.07% | 1,498 | **Δ = 0** |
| 🚇 subway | 0.9935 | 769.318 | 330.871 | 4.96% | 446 | **Δ = 0** |

- R²·RMSE·MAE·MAPE·`best_iteration` **12개 지표 전부 Δ = 0.000000** · `best_params`·25차원 피처 순서 일치 · ONNX **파일 크기 3종 동일**(직렬화 메타 차이로 SHA256 만 상이).
- Colab 환경(스키마 `env`): python 3.13.16 · **lightgbm 4.7.0(로컬과 동일)** · numpy 2.1.3 · pandas 2.2.3.
- ⇒ 로컬 실험 결과가 **Colab 재현성까지 확보**되어, 교체 후보(`tuned_25d` ≡ `tuned_25d_colab` 동일 모델) 판단 근거는 변동 없습니다.
- 평가(5-way): `python benchmarks/evaluate_models.py --model tuned_25d_colab=benchmarks/2026-10-14/tuned_25d_colab --model tuned_25d=benchmarks/2026-10-14/tuned_25d`