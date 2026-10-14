# 📊 Benchmarks — 모델 자산 및 평가 규약

> 학습된 ONNX 모델 스냅샷과 벤치마크 재료를 보관하는 디렉터리입니다.
> **모델 자산 구조/차원 규격은 이 문서를 단일 기준(SSoT)으로 삼습니다.**

---

## 1. 폴더 구조

```text
benchmarks/
├── README.md                     # (이 문서) 자산 구조 및 평가 규약
├── CastTransit.ipynb             # LightGBM 학습/튜닝/ONNX export 노트북 (v2: 실제 32차원)
├── evaluate_models.py            # 공정 비교 평가 스크립트 (v2: 실피처 + 사양서 §6.1 분할 + 스키마 SSoT 검증)
├── retrain_25d.py                # [실험] 동일 v2 파라미터 + 25차원 서브셋 재학습 (차원 vs 튜닝 분리)
├── original/                     # [기준선 A] 배포본 스냅샷 (25차원)
│   ├── lgb_bike_demand.onnx
│   ├── lgb_bus_demand.onnx
│   └── lgb_subway_demand.onnx
├── results/                      # 평가 결과 (comparison_<timestamp> / retrain_25d_<timestamp>.json·md)
├── 2026-10-12/
│   ├── tuned/                    # [구 후보] v1 배치(25차원 + 상수 0 더미 7) — 기본 비교 포함
│   │   ├── README.md
│   │   ├── lgb_bike_demand.onnx
│   │   ├── lgb_bus_demand.onnx
│   │   └── lgb_subway_demand.onnx
│   └── tuned_real/               # [종료] 2026-10-14 로 이관된 빈 배치 위치 (안내 README 만 유지)
│       └── README.md
└── 2026-10-14/                   # [신규 후보] v2 실제 32차원 실피처 산출물 (2026-10-14 Colab 학습)
    ├── lgb_bike_demand.onnx
    ├── lgb_bus_demand.onnx
    ├── lgb_subway_demand.onnx
    ├── feature_schema.json       # 피처 순서·분할·지표 메타 (SSoT — 평가·서빙이 읽어 assert)
    ├── tuned_25d/                # [실험] 동일 v2 파라미터 + 25차원 재학습 (서빙 정렬 가능)
    │   ├── lgb_bike_demand.onnx
    │   ├── lgb_bus_demand.onnx
    │   ├── lgb_subway_demand.onnx
    │   └── feature_schema.json   # 25차원 서빙 배치 스키마(model_version: v2-전처리_2-25d-retrain)
    └── README.md                 # 자산 설명·평가 방법
```

> 피처 스키마 로더/검증 모듈은 레포 루트의 [`feature_schema.py`](../feature_schema.py) 이며,
> 서빙(`main.py`)·평가(`evaluate_models.py`)·재학습(`retrain_25d.py`)이 **공통으로 import** 합니다.

---

## 2. 모델 자산 목록 (검증값)

| 구분 | 경로 | 차원 | 파일 크기 (byte) | 비고 |
| :--- | :--- | :---: | ---: | :--- |
| **기준선 A** | `original/lgb_bike_demand.onnx` | **25** | 4,719,076 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_bus_demand.onnx` | 25 | 4,712,686 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_subway_demand.onnx` | 25 | 4,696,656 | `models/` 와 MD5 동일 |
| **구 후보(v1)** | `2026-10-12/tuned/lgb_bike_demand.onnx` | **32** | 6,782,549 | v1 배치(25 + 더미 7) · 기본 비교 포함 |
| 구 후보(v1) | `2026-10-12/tuned/lgb_bus_demand.onnx` | 32 | 13,251,388 | v1 배치(25 + 더미 7) · 기본 비교 포함 |
| 구 후보(v1) | `2026-10-12/tuned/lgb_subway_demand.onnx` | 32 | 9,805,101 | v1 배치(25 + 더미 7) · 기본 비교 포함 |
| **신규 후보(v2)** | `2026-10-14/lgb_bike_demand.onnx` | **32** | 7,020,769 | v2 실피처(8/8/5/11) · 2026-10-14 학습 |
| 신규 후보(v2) | `2026-10-14/lgb_bus_demand.onnx` | 32 | 13,596,760 | v2 실피처(8/8/5/11) · 2026-10-14 학습 |
| 신규 후보(v2) | `2026-10-14/lgb_subway_demand.onnx` | 32 | 7,345,447 | v2 실피처(8/8/5/11) · 2026-10-14 학습 |
| **25차원 재학습** | `2026-10-14/tuned_25d/lgb_bike_demand.onnx` | **25** | 5,709,941 | 동일 v2 파라미터 + 25차원 서빙 서브셋 · **서빙 정렬 가능** |
| 25차원 재학습 | `2026-10-14/tuned_25d/lgb_bus_demand.onnx` | 25 | 14,574,454 | 동일 v2 파라미터 + 25차원 서빙 서브셋 |
| 25차원 재학습 | `2026-10-14/tuned_25d/lgb_subway_demand.onnx` | 25 | 3,713,077 | 동일 v2 파라미터 + 25차원 서빙 서브셋 |

---

## 3. 입력 차원 규격 (⚠️ 중요)

- 배포본(`models/`, `original/`)은 **25차원**이며, 신규 후보(`2026-10-14/`)와 구 후보(`2026-10-12/tuned/`)는 **32차원**입니다. 단, **배치가 서로 다릅니다.**

| 자산 | 피처 배치 | 차원 | 비고 |
| :--- | :--- | :---: | :--- |
| `original/`, `models/` | 사양서 §3.2 부분집합 | **25** | 배포본 |
| `2026-10-14/` | **사양서 §3.2 순서 (8/8/5/11)** | **32** | 2026-10-14 Colab 산출물 (실피처) |
| `2026-10-12/tuned_real/` | (배치 종료) | — | 2026-10-14 로 이관 · 안내 README 만 유지 |
| `2026-10-12/tuned/` | v1 배치 (8/8/1/3/3/2 + 더미 7) | 32 | 기본 비교 포함 (`MODEL_LAYOUTS["tuned_32d_v1"] = "v1"`), 서빙 투입 금지 |
| `2026-10-14/tuned_25d/` | **사양서 §3.2 의 25차원 서브셋과 동일 배치** | **25** | 차원 vs 튜닝 분리 실험 산출물 · `main.py::prepare_session_input` 과 정렬되어 **서빙 투입 가능** |

- **25차원 = 32차원 − 7** 부분집합입니다. (아래 표는 사양서 §3.2 기준)

| 사양 32차원 인덱스 | 피처 그룹 | 25차원 포함 |
| :--- | :--- | :---: |
| [0–7] | 캘린더/시계열 8 | ✅ |
| [8–15] | 기상 관측/파생 8 | ✅ |
| [16] | `district_code` | ✅ |
| **[17–20]** | **공간 인프라 4** (역사·정류소·거치대·상업밀도) | ❌ 제외 |
| [21–26] | 래그 3 + 이동평균 3 | ✅ |
| **[27–29]** | **`same_day_last_week_*` 3** | ❌ 제외 |
| [30–31] | `temp_diff_1h`, `rain_diff_1h` | ✅ |

- 서빙 코드(`main.py::prepare_session_input`)는 25/32차원을 모두 지원합니다.
- **주의 — `2026-10-12/tuned/`(v1)**: 노트북 v1이 25개 피처 뒤에 **상수 0 더미 7개(`infra_dummy_0..6`)** 를 덧붙여 만든 32차원입니다.
  - 정보량은 25차원과 동일했고, **배치 순서가 사양서/`main.py` 와 달랐습니다**([25–31]이 더미).
  - 평가 스크립트는 라벨별 배치(`MODEL_LAYOUTS["tuned_32d_v1"] = "v1"`)를 지정해 **자기 배치로 공정 비교에 포함**합니다(2026-10-14 개정). v1 배치 행렬은 **25차원 서브셋 + 0 열 7개**로 재현합니다.
  - ⛔ **서빙에는 투입할 수 없습니다** — `main.py::prepare_session_input()` 은 32차원 모델에 32차원 실피처 벡터를 그대로 전달하므로 인덱스 17 이후가 어긋납니다.
- **`2026-10-14/`(v2)**: 2026-10-14 Colab 학습 산출물입니다. 32차원을 **실측 피처**로 채웁니다(인프라 4 + `same_day_last_week_*` 3). 배치 순서가 사양서 §3.2와 문자 단위로 일치합니다.
  - `feature_schema.json`(`model_version: v2-전처리_2-32d`)이 피처 32개 순서·분할 경계·공휴일 캘린더·튜닝 하이퍼파라미터를 함께 기록합니다.
  - **이 스키마가 피처 정의의 단일 진실 공급원(SSoT)** 입니다 — 서빙 기동 시(`main.py::ModelRegistry.load_feature_schema`)와 평가 실행 시(`evaluate_models.py::verify_feature_schema`)가 스키마를 읽어 **차원·순서·타깃·분할 경계를 assert** 합니다. 불일치는 기동/실행 실패로 즉시 드러납니다.
  - 구 배치 위치 `2026-10-12/tuned_real/` 은 **안내 README 만 남긴 종료 폴더**입니다.
- **`2026-10-14/tuned_25d/`(25차원 재학습)**: `benchmarks/retrain_25d.py` 가 **스키마의 v2 튜닝 파라미터를 그대로 고정**하고 피처만 25차원 서빙 서브셋으로 줄여 재학습한 산출물입니다(`feature_schema.json` 의 `model_version: v2-전처리_2-25d-retrain`).
  - 목적: ① 차원 증가의 **순수 효과** 분리(§4.3) · ② **서빙 가능한 개선본** 확보(25차원이라 `prepare_session_input` 정렬 대상이 그대로 일치).
  - 배포 슬롯(`models/`) 교체 여부는 성능 게이트 결과로만 판단합니다(§4.3 · `docs/MODEL_PERFORMANCE_REPORT.md` §0.4).

---

## 4. 평가 규약 (Temporal Split)

`docs/AI_MODEL_SPEC.md` §6.1 기준 (**2026-10-13 공식 확정** — 원천 CSV의 `분할` 컬럼은 사용하지 않습니다).

```text
[ 2025-01-01 ~ 2025-09-30 ] : Train      (156,975행) - 학습
[ 2025-10-01 ~ 2025-11-15 ] : Validation ( 26,450행) - 조기 종료/튜닝
[ 2025-11-16 ~ 2025-12-31 ] : Test       ( 26,450행) - 최종 일반화 검증
```

- 평가 지표: R² / RMSE / MAE / MAPE(실측 0 제외) + ONNX 단건 추론 레이턴시(ms).
- 학습·평가 원천: `data/2025_서울25개구_교통날씨_전처리_2.csv` (209,875행 × 33열)
- 피처: **실제 32차원 실피처(8/8/5/11)** — 인프라 4 + `same_day_last_week_*` 3을 실측 산출. **상수 0 더미 폐기.**
- `is_holiday`: **2025 대한민국 공휴일 19일** 캘린더(`main.py::KR_HOLIDAYS`) 기준이며 `is_weekend` 와는 별개 지표입니다.
- 단일 소스: `DISTRICT_CODE_MAP` / `DISTRICT_INFRA` / `KR_HOLIDAYS` 를 `main.py` 에서 직접 import 하여 학습↔서빙 드리프트를 차단합니다.

### 4.1 평가 실행

```bash
python benchmarks/evaluate_models.py
# 다른 폴더를 추가/덮어쓰려면 (반복 지정 가능):
python benchmarks/evaluate_models.py --model tuned_32d_real=benchmarks/2026-10-14
# 25차원 재학습 실험 자산도 포함 (서빙 정렬 가능한 25차원 모델):
python benchmarks/evaluate_models.py --model tuned_25d=benchmarks/2026-10-14/tuned_25d
# 32차원 자산의 피처 배치를 강제하려면 (v1=25+더미 7 / v2=사양서 §3.2):
python benchmarks/evaluate_models.py --layout my_label=v1
# 피처 스키마(SSoT) 경로를 명시하려면 (미지정 시 자동 탐색):
python benchmarks/evaluate_models.py --schema benchmarks/2026-10-14/feature_schema.json
```

- **실행 첫 단계에서 피처 스키마를 검증**합니다(`verify_feature_schema`) — 스키마의 `feature_cols` 차원·순서가 이 스크립트의 상수와 다르면 **즉시 중단**합니다. 검증 결과는 리포트 헤더와 JSON `feature_spec.schema` 에 기록됩니다(스키마 미발견 시 `skipped` 로 표기하고 내장 상수로 진행).
- 기본 비교 **3종**: `production_25d`(=`original/`, 25차원) · `tuned_32d_v1`(=`2026-10-12/tuned/`, v1 배치) · `tuned_32d_real`(=`2026-10-14/`, v2 실피처). `--model tuned_25d=...` 를 주면 25차원 재학습 자산까지 **4-way** 로 비교합니다.
  - 배포 슬롯 `models/` 는 `original/` 과 **바이트 동일(SHA256)** 이므로 별도 행을 만들지 않고, 리포트 말미 `자산 무결성 (SHA256)` 절에 동일 자산으로 표기됩니다(스크립트가 자동 스캔).
- **세대별 피처 배치**를 `MODEL_LAYOUTS` 로 지정해 각 모델을 **자기 배치로만** 평가합니다: `v2`(사양서 §3.2 · 8/8/5/11) / `v1`(25차원 `8/8/1/3/3/2` + 상수 0 더미 7). 25차원 모델은 배치와 무관하게 25차원 서브셋을 받습니다.
- 모든 모델이 **동일한 테스트 행**(사양서 §6.1 `test 2025-11-16 ~ 12-31`, n=26,450)을 사용하므로 수단별 순위 비교가 성립합니다.
- 레거시 모델(배포본 25차원 / v1 32차원)은 `is_holiday = 0`(학습 당시 분포) 변형도 함께 평가해 참고치를 남깁니다(값이 같으면 자동으로 진단 문구로 축약).
- 리포트에는 모델 표 외에 **`production_25d` 대비 델타 표**와 **SHA256 자산 무결성** 절이 함께 생성됩니다.

### 4.2 학습 노트북 실행 (Colab)

`benchmarks/CastTransit.ipynb` 를 **[Cell 1] → [Cell 7] 순서로 실행**합니다(Step 5-1 = [Cell 6-1] Optuna 튜닝 포함).

- Colab 기본 제공이 아닌 패키지는 **셀 안에서 자동 설치**됩니다 — `optuna`([Cell 6-1]), `onnxmltools`·`skl2onnx`([Cell 7]).
  - 설치 직후 `importlib.invalidate_caches()` 로 **같은 커널에서 즉시 import** 되도록 처리했습니다.
- 네트워크가 막힌 환경에서는 [Cell 1] 주석의 `!pip install -q lightgbm optuna onnxmltools skl2onnx onnxruntime` 를 1회 수동 실행하세요.
- 산출물(`lgb_{bike,bus,subway}_demand.onnx` + `feature_schema.json`)은 **`2026-10-14/`**(2026-10-14 학습분)에 배치되어 있으며, §4.1 을 실행하면 `tuned_32d_real` 행이 자동으로 채워집니다.

---

### 4.3 25차원 재학습 — 차원 vs 튜닝 분리 실험 (`retrain_25d.py`)

v2 후보(32차원)와 배포본(25차원)의 차이는 ①차원 ②Optuna 튜닝 ③신규 원천(`전처리_2`)이 **동시에** 바뀐 결과(교란 3중)입니다. 이 스크립트는 **②를 고정**하고 ①만 25차원으로 바꾼 대조군을 만듭니다.

```bash
python benchmarks/retrain_25d.py            # 학습 + 지표 리포트(로컬 CPU, lightgbm 필요)
python benchmarks/retrain_25d.py --export   # + ONNX 3종/25차원 스키마 반출(benchmarks/<실행일>/tuned_25d)
```

- 고정 파라미터 출처: `feature_schema.json::metrics.<mode>.tuned.best_params`(SSoT). `--params PATH` 로 직접 지정도 가능합니다.
- 전처리·지표·분할은 `evaluate_models.py` 를 **import 해서 재사용**합니다(드리프트 차단).
- 결과 리포트: `benchmarks/results/retrain_25d_<timestamp>.{json,md}` (스키마 기록치 대비 Δ 포함).
- **실측 결과(2026-10-14)** — Test 2025-11-16~12-31, n=26,450 · 원본 `results/comparison_20261014_192204.{json,md}`:

| 수단 | 배포본 25d | **재학습 25d (동일 v2 파라미터)** | Δ vs 배포본 | v2 32d |
| :---: | ---: | ---: | ---: | ---: |
| 🚲 bike | 0.9887 / 16.372 / 9.815 | 0.9883 / 16.666 / 9.677 | R² −0.0004 · RMSE +0.294 · **MAE −0.138** | 0.9873 / 17.382 / 9.669 |
| 🚌 bus | 0.9897 / 571.741 / 369.300 | **0.9912 / 528.628 / 342.732** | **R² +0.0015 · RMSE −43.1 · MAE −26.6** | 0.9901 / 561.358 / 370.444 |
| 🚇 subway | 0.9924 / 826.324 / 369.732 | **0.9935 / 769.318 / 330.871** | **R² +0.0010 · RMSE −57.0 · MAE −38.9** | 0.9951 / 662.095 / 277.633 |

- 결론: **개선분의 대부분은 하이퍼파라미터 튜닝 효과**이며(25차원만으로도 bus·subway 전 지표 개선), **32차원 증가의 순수 효과는 🚇 지하철에서만** 확인됩니다(bus 는 25차원이 더 우세, bike 는 동일 수준).
- 25차원 재학습본은 **서빙 정렬이 그대로 맞으므로**(`prepare_session_input` 의 25차원 서브셋과 배치 동일) `models/` 교체 후보가 될 수 있습니다.
- ⚠️ 로컬(lightgbm 4.7) 실행값이며 Colab 버전과 `best_iteration` 이 다를 수 있습니다(규모·방향 비교용). 버스는 P0-1(테스트 구간 결측 24.59% 보간)로 **잠정치**.

### 4.4 피처 스키마 SSoT 및 정합성 테스트

```bash
python tests/test_feature_schema.py   # 7종: 규격·3자 순서 일치·25d 서브셋·ONNX 차원·타깃/분할·네거티브 가드·/health
python tests/test_inference.py        # 서빙 기동 시 스키마 검증 + 추론 SLA
```

- 스키마 탐색 순서: ①`--schema`/명시 인자 ②`FEATURE_SCHEMA_PATH` 환경변수 ③`models/feature_schema.json`(배포 슬롯) ④`benchmarks/2026-10-14/feature_schema.json`.
- 서빙은 기동 시 **스키마 ↔ `main.py::FEATURE_ORDER_32` ↔ 실제 ONNX 입력 차원**을 3중 대조하고, `/health` 의 `feature_schema` 블록에 결과를 노출합니다(`status`: `verified` / `legacy-subset-25d` / `mixed-32d/25d` / `not-found`).

---

## 5. 변경 이력

### [2026-10-14] 피처 스키마 SSoT 소비 + 25차원 재학습 (차원 vs 튜닝 분리 실험)
- **배경**: ① v1 32차원 자산을 v2 배치로 넣으면 조용히 예측이 붕괴(R² −0.59/−0.93/0.19 실측)했고, 학습·평가·서빙이 피처 순서를 각자 하드코딩하고 있었습니다. ② 배포본 vs v2 후보의 차이는 차원·튜닝·원천이 동시에 바뀐 **교란 3중**이라 순수 차원 효과를 알 수 없었습니다.
- **조치**:
  1. **`feature_schema.py` 신설(SSoT 모듈)** — 스키마 탐색(`--schema` → `FEATURE_SCHEMA_PATH` → `models/feature_schema.json` → `benchmarks/2026-10-14/feature_schema.json`) + `schema_feature_cols` / `validate_expected_order` / `validate_targets` / `validate_split_bounds` / `legacy_25d_indices` / `schema_summary`, 불일치 시 `FeatureSchemaError`(인덱스 진단 포함).
  2. **서빙(`main.py`)**: `FEATURE_ORDER_32` 상수 추가 + `build_feature_vector` 차원 assert · 기동 시 `load_feature_schema` → `validate_model_dimensions` 로 **스키마 ↔ 코드 ↔ ONNX 입력 차원 3중 대조**(스키마 차원도 25차원도 아니면 기동 중단) · `/health` 에 `feature_schema` 블록 추가. 25차원 서브셋 인덱스 정의는 SSoT 한 곳으로 통일.
  3. **평가(`evaluate_models.py`)**: `--schema` CLI + `verify_feature_schema`(순서·타깃·분할 경계 assert, 32차원/25차원 스키마 모두 지원) · 리포트에 스키마 검증 줄·JSON `feature_spec.schema` 추가 · `reference_ih0` 참고치는 **레거시 라벨 한정**(새 25차원 자산 오표기 방지).
  4. **25차원 재학습(`retrain_25d.py` 신설)**: 스키마의 v2 `best_params` 를 고정하고 피처만 25차원 서빙 서브셋으로 줄여 재학습 → 지표 리포트 + `--export` 시 ONNX·25차원 스키마 반출.
  5. **테스트(`tests/test_feature_schema.py` 신설)**: 규격 / 3자 순서 일치 / 25차원 서브셋 / ONNX 자산 차원 / 타깃·분할·공휴일 / 네거티브 가드 5종 / `/health` 노출 — **7종 전부 통과**.
- **결과 (`results/comparison_20261014_192204.{json,md}` · 4-way · n=26,450)**:

| 수단 | 배포본 25d | v1 32d | v2 32d | **재학습 25d (동일 v2 파라미터)** |
| :---: | ---: | ---: | ---: | ---: |
| 🚲 bike | 0.9887 / 16.372 / 9.815 | 0.9893 / 15.912 / 9.387 | 0.9873 / 17.382 / 9.669 | 0.9883 / 16.666 / 9.677 |
| 🚌 bus | 0.9897 / 571.741 / 369.300 | 0.9923 / 495.648 / 312.571 | 0.9901 / 561.358 / 370.444 | **0.9912 / 528.628 / 342.732** |
| 🚇 subway | 0.9924 / 826.324 / 369.732 | 0.9940 / 736.058 / 298.796 | **0.9951 / 662.095 / 277.633** | 0.9935 / 769.318 / 330.871 |

  - **차원 vs 튜닝 분리**: 튜닝 파라미터를 고정하고 25차원으로 줄여도 배포본을 상회(bus MAE −26.6 / subway MAE −38.9) → **개선의 대부분은 튜닝 효과**. 32차원 증가의 **순수 효과는 지하철에서만** 확인됩니다(bus 는 25차원이 우세, bike 는 동일 수준).
  - `tuned_25d` 는 25차원이라 **서빙 정렬이 그대로 맞으므로**(`prepare_session_input` 서브셋과 배치 동일) `models/` 교체 후보가 될 수 있습니다.
  - ⚠️ 로컬 lightgbm 4.7 실행값(Colab 버전과 `best_iteration` 상이 가능) · bus 는 P0-1 로 잠정치.
- **정리**: 구 3세대 리포트(`190055`)는 4-way 리포트(`192204`)로 대체했습니다.
- **산출물**: `feature_schema.py`, `benchmarks/retrain_25d.py`, `benchmarks/evaluate_models.py`, `main.py`, `tests/test_feature_schema.py`, `benchmarks/2026-10-14/tuned_25d/`(ONNX 3 + 스키마), `benchmarks/results/{comparison_20261014_192204,retrain_25d_20261014_192001}.{json,md}`, `benchmarks/README.md`, `benchmarks/2026-10-14/README.md`, `docs/{TODO,MODEL_PERFORMANCE_REPORT,CHANGELOG,AI_MODEL_SPEC,BACKEND_INFERENCE_SERVER,API_STRUCTURE}.md`, `.env.example`

### [2026-10-14] 전 세대 모델 3종 동시 비교 지원 (v1 배치 포함)
- **평가 스크립트 개정**: 세대별 **피처 배치(layout)** 를 라벨별로 지정(`MODEL_LAYOUTS`)하고, `--layout LABEL=v1|v2` 로 덮어쓸 수 있게 했습니다.
  - 기본 비교 3종: `production_25d`(25차원) / `tuned_32d_v1`(v1 배치 = 25차원 `8/8/1/3/3/2` + 상수 0 더미 7) / `tuned_32d_real`(v2 실피처 `8/8/5/11`).
  - v1 배치 행렬은 **25차원 서브셋 + 0 열 7개**로 재현합니다(더미는 상수 0 → 정보량 = 25차원).
  - 구 스크립트(`ef1d03d:benchmarks/evaluate_models.py`)의 `FEATURE_COLS` + `infra_dummy_0..6` 정의와 동일함을 이력에서 확인해 고정했습니다.
- **리포트 확장**: 모델 표에 **`피처 배치` 열** · `production_25d` 대비 **델타 표** · ONNX 자산 **SHA256 무결성** 절(배포 슬롯 `models/` ≡ `original/` 자동 검출) 추가.
- **결과** (`results/comparison_20261014_192204.{json,md}` · Test 2025-11-16~12-31, n=26,450 — 구 `190055` 리포트를 4-way 로 대체):

| 수단 | 배포본 25차원 | **v1 32차원(구 후보)** | v2 32차원 실피처(신규 후보) |
| :---: | ---: | ---: | ---: |
| 🚲 bike | 0.9887 / 16.372 / 9.815 | **0.9893 / 15.912 / 9.387** | 0.9873 / 17.382 / 9.669 |
| 🚌 bus | 0.9897 / 571.741 / 369.300 | **0.9923 / 495.648 / 312.571** | 0.9901 / 561.358 / 370.444 |
| 🚇 subway | 0.9924 / 826.324 / 369.732 | 0.9940 / 736.058 / 298.796 | **0.9951 / 662.095 / 277.633** |

  - `tuned_32d_v1` 은 **3수단 12개 지표 전부 배포본보다 우세**(MAE 개선폭: bike −4.4% / bus −15.4% / subway −19.2%) → 구 v1 프레임의 보고치(subway MAE −19.2%, bike R² 0.9893, subway R² 0.9940)를 **재현**했습니다.
  - 동일 프레임에서 v2 와 직접 비교하면 **v1 이 bike·bus 8개 지표 전부 우세**, v2 는 **subway 4개 지표**만 우세합니다.
  - 단, v1 은 **서빙 불가**(배치 비호환)이므로 v1 우세는 "25차원 정보량 + Optuna 튜닝"의 상한을 보여주는 **참고 지표**입니다 → 25차원 재학습 실험의 기대 근거로 사용합니다.
  - 프레임 차이(구 원천 ↔ `전처리_2`)로 bus 수치는 이동합니다(배포본 R² 0.9882→0.9897 · v1 0.9908→0.9923). 순위 해석은 **동일 실행 내부 비교**로 한정하십시오.

### [2026-10-14] v2 실제 32차원 실피처 모델 3종 학습·반입
- **학습·반입**: `benchmarks/CastTransit.ipynb`(v2)를 Colab에서 실행해 **실제 32차원 실피처(8/8/5/11)** 모델 3종을 생성하고 `benchmarks/2026-10-14/` 에 배치했습니다(커밋 `07292b4`).
  - 자산: `lgb_{bike,bus,subway}_demand.onnx`(ONNX 입력 `[None, 32]`) + `feature_schema.json`(3,296 byte)
  - 크기: bike 7,020,769 / bus 13,596,760 / subway 7,345,447 byte
  - 튜닝: `best_iteration` bike 834 / bus 1,390 / subway 865 (Optuna 30 trials — 파라미터는 `feature_schema.json::metrics.*.tuned.best_params`)
- **노트북 기록 Test 지표**(2025-11-16~12-31, n=26,450): bike R² 0.98729 / RMSE 17.382 / MAE 9.669 · bus 0.99006 / 561.352 / 370.441 · subway 0.99515 / 662.095 / 277.633
  - ⚠️ **평가 스크립트 교차검증 통과 (2026-10-14)**: `python benchmarks/evaluate_models.py` 실측값이 노트북 기록치와 **소수점 수준 일치**(bike 0.9873 / bus 0.9901 / subway 0.9951, RMSE 오차 ≤0.006) → 파이프라인 재현성 확인. 버스는 P0-1(테스트 구간 결측 24.59% 보간)로 **잠정치**입니다.
- **배포 판단 (Gate) — 전면 교체 보류 (2026-10-14)**: 3수단 전부 유의 우세 조건 **미충족** →
  - 🚇 subway ✅ 전 지표 우세(MAE −24.9%) / 🚲 bike ⚠️ R²·RMSE 열세(−0.0014 / +1.010) / 🚌 bus ⚠️ MAPE 열세(+3.56%p)
  - 따라서 **`models/` 는 25차원 유지**하고, 수단별 교체 또는 25차원 재학습 비교 후 확정합니다.
- **자산 위치 정리**: 신규 후보 경로를 `2026-10-14/` 로 확정하고, `2026-10-12/tuned_real/` 은 안내 README 만 남긴 **종료 폴더**로 전환. `evaluate_models.py::MODEL_SETS` 의 `tuned_32d_real` 기본 경로도 `2026-10-14/` 로 갱신(기존 경로는 빈 폴더라 `[skip]` 되었음).
- **사전 검증**: `feature_schema.json.feature_cols`(32) == `evaluate_models.py::FEATURE_COLS_32` == `main.py::build_feature_vector` 인덱스 0~31 (순서 완전 일치) · 공휴일 캘린더 19일 일치.

### [2026-10-13] 평가·학습 파이프라인 v2 — 실피처 32차원 · 사양서 분할 확정 · 실제 공휴일 캘린더
- **원천 전환**: `data/2025_서울25개구_교통날씨_전처리_2.csv`(209,875 × 33) 기준으로 학습·평가 파이프라인 통일.
- **32차원을 실측 피처로 구성**: 인프라 4 + `same_day_last_week_*` 3을 실제 산출하여 **상수 0 더미 7을 폐기**.
- **분할 경계 공식 확정**: 사양서 §6.1(`valid 10-01~11-15` / `test 11-16~12-31`)을 기준으로 채택, CSV `분할` 컬럼(`valid ~10-31` / `test 11-01~`) 미사용.
  - 노트북 `SPLIT_SOURCE = 'spec_dates'`, `evaluate_models.py` 동일 경계 적용.
- **`is_holiday` 정의 교체**: `is_weekend` 복제 → **2025 대한민국 실제 공휴일 19일**(`main.py::KR_HOLIDAYS`) 판정으로 변경(학습·서빙 동일 집합).
- **단일 소스 통합**: `district_code`·인프라 4종·공휴일 캘린더를 `main.py` 에서 직접 import(평가 스크립트 포함).
- **자산 재편**: `2026-10-12/tuned/`(v1 더미 배치)는 참고 보관으로 전환하고, 신규 32차원 산출물 위치로 `2026-10-12/tuned_real/` 신설.
  - `evaluate_models.py` 는 v1 32차원 자산을 기본 비교에서 제외(피처 배치 비호환).
- **정리**: 참조 0건인 `gemini-code-1791814037657.py` 삭제(실행 불가한 Colab 셀 파편 — `trained_models`/`X_test` 등 미정의 전역 사용).

### [2026-10-12] 중복 모델 통합
- 노트북 export 셀 2회 실행으로 `baseline/` 와 `hyperparameter/` 가 **MD5 동일 중복** 생성됨.
  - `baseline/lgb_*.onnx` == `hyperparameter/lgb_* (1).onnx`
  - 실체는 **[Cell 7-1] Optuna 튜닝본(32차원)** 1종.
- 두 폴더를 삭제하고 **`2026-10-12/tuned/` 단일 폴더로 통합**(해시 검증 후 삭제, 무손실).
- 기준선은 `original/`(25차원 = 배포본) 1종으로 정리.

---

## 6. 성능 비교 분석 보고서

- **v2(현재) 방법론·수치**: [**docs/MODEL_PERFORMANCE_REPORT.md**](../docs/MODEL_PERFORMANCE_REPORT.md) **§0** — 실피처 32차원 · 사양서 §6.1 분할 · 실제 공휴일 캘린더 기준
- **3세대 동시 비교(v1 포함)**: 같은 문서 **§0.3** — 배포본 25차원 / v1 32차원 / v2 32차원 실피처
- **v1(2026-10-12) 이력**: 같은 문서 §1~부록 A — 25차원 + 상수 0 더미 7 비교(해석 주의: §0.1)
- 원본 수치: `results/comparison_<timestamp>.{json,md}` (`python benchmarks/evaluate_models.py` 로 재생성)