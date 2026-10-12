# 📊 Benchmarks — 모델 자산 및 평가 규약

> 학습된 ONNX 모델 스냅샷과 벤치마크 재료를 보관하는 디렉터리입니다.
> **모델 자산 구조/차원 규격은 이 문서를 단일 기준(SSoT)으로 삼습니다.**

---

## 1. 폴더 구조

```text
benchmarks/
├── README.md                     # (이 문서) 자산 구조 및 평가 규약
├── CastTransit.ipynb             # LightGBM 학습/튜닝/ONNX export 노트북 (v2: 실제 32차원)
├── evaluate_models.py            # 공정 비교 평가 스크립트 (v2: 실피처 + 사양서 §6.1 분할)
├── original/                     # [기준선 A] 배포본 스냅샷 (25차원)
│   ├── lgb_bike_demand.onnx
│   ├── lgb_bus_demand.onnx
│   └── lgb_subway_demand.onnx
├── results/                      # 평가 결과 (comparison_<timestamp>.json / .md)
└── 2026-10-12/
    ├── tuned/                    # [구 후보] v1 배치(25차원 + 상수 0 더미 7) — 참고 보관
    │   ├── lgb_bike_demand.onnx
    │   ├── lgb_bus_demand.onnx
    │   └── lgb_subway_demand.onnx
    └── tuned_real/               # [신규 후보] v2 실제 32차원 실피처 산출물 배치 위치
        └── README.md             # 파일 반입 방법 안내
```

---

## 2. 모델 자산 목록 (검증값)

| 구분 | 경로 | 차원 | 파일 크기 (byte) | 비고 |
| :--- | :--- | :---: | ---: | :--- |
| **기준선 A** | `original/lgb_bike_demand.onnx` | **25** | 4,719,076 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_bus_demand.onnx` | 25 | 4,712,686 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_subway_demand.onnx` | 25 | 4,696,656 | `models/` 와 MD5 동일 |
| **구 후보(v1)** | `2026-10-12/tuned/lgb_bike_demand.onnx` | **32** | 6,782,549 | v1 배치(25 + 더미 7) · 참고 보관 |
| 구 후보(v1) | `2026-10-12/tuned/lgb_bus_demand.onnx` | 32 | 13,251,388 | v1 배치(25 + 더미 7) · 참고 보관 |
| 구 후보(v1) | `2026-10-12/tuned/lgb_subway_demand.onnx` | 32 | 9,805,101 | v1 배치(25 + 더미 7) · 참고 보관 |

---

## 3. 입력 차원 규격 (⚠️ 중요)

- 배포본(`models/`, `original/`)은 **25차원**이며, 신규 후보(`2026-10-12/tuned_real/`)와 구 후보(`2026-10-12/tuned/`)는 **32차원**입니다. 단, **배치가 서로 다릅니다.**

| 자산 | 피처 배치 | 차원 | 비고 |
| :--- | :--- | :---: | :--- |
| `original/`, `models/` | 사양서 §3.2 부분집합 | **25** | 배포본 |
| `2026-10-12/tuned_real/` | **사양서 §3.2 순서 (8/8/5/11)** | **32** | v2 노트북 산출물 (실피처) |
| `2026-10-12/tuned/` | v1 배치 (8/8/1/3/3/2 + 더미 7) | 32 | 참고 보관 전용 |

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
  - `benchmarks/evaluate_models.py`(v2)는 이 자산을 **기본 비교 대상에서 제외**합니다(인덱스 16 이후가 전부 어긋남). 그대로 서빙에 사용하지 마십시오.
- **`tuned_real/`(v2)**: 2026-10-13부터는 32차원을 **실측 피처**로 채웁니다(인프라 4 + `same_day_last_week_*` 3). 배치 순서가 사양서 §3.2와 문자 단위로 일치합니다.

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
python benchmarks/evaluate_models.py --model tuned_32d_real=benchmarks/2026-10-12/tuned_real
```

- 기본 비교 쌍: `production_25d`(=`original/`) ↔ `tuned_32d_real`(=`2026-10-12/tuned_real/`, 파일이 없으면 `[skip]`).
- 두 모델이 **동일한 피처 프레임**에서 각각 25차원 서브셋 / 전체 32차원을 받으므로, 성능 차이는 피처 구성 차이만 반영합니다.
- 25차원 레거시 모델은 `is_holiday = 0`(학습 당시 분포) 변형도 함께 평가해 참고치를 남깁니다(값이 같으면 자동으로 진단 문구로 축약).

### 4.2 학습 노트북 실행 (Colab)

`benchmarks/CastTransit.ipynb` 를 **[Cell 1] → [Cell 7] 순서로 실행**합니다(Step 5-1 = [Cell 6-1] Optuna 튜닝 포함).

- Colab 기본 제공이 아닌 패키지는 **셀 안에서 자동 설치**됩니다 — `optuna`([Cell 6-1]), `onnxmltools`·`skl2onnx`([Cell 7]).
  - 설치 직후 `importlib.invalidate_caches()` 로 **같은 커널에서 즉시 import** 되도록 처리했습니다.
- 네트워크가 막힌 환경에서는 [Cell 1] 주석의 `!pip install -q lightgbm optuna onnxmltools skl2onnx onnxruntime` 를 1회 수동 실행하세요.
- 산출물(`lgb_{bike,bus,subway}_demand.onnx` + `feature_schema.json`)은 **`2026-10-12/tuned_real/`** 에 배치한 뒤 §4.1 을 재실행하면 `tuned_32d_real` 행이 자동으로 채워집니다.

---

## 5. 변경 이력

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
- **v1(2026-10-12) 이력**: 같은 문서 §1~부록 A — 25차원 + 상수 0 더미 7 비교(해석 주의: §0.1)
- 원본 수치: `results/comparison_<timestamp>.{json,md}` (`python benchmarks/evaluate_models.py` 로 재생성)