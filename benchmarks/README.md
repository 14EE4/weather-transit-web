# 📊 Benchmarks — 모델 자산 및 평가 규약

> 학습된 ONNX 모델 스냅샷과 벤치마크 재료를 보관하는 디렉터리입니다.
> **모델 자산 구조/차원 규격은 이 문서를 단일 기준(SSoT)으로 삼습니다.**

---

## 1. 폴더 구조

```text
benchmarks/
├── README.md                     # (이 문서) 자산 구조 및 평가 규약
├── CastTransit.ipynb             # LightGBM 학습/튜닝/ONNX export 노트북
├── original/                     # [기준선 A] 배포본 스냅샷 (25차원)
│   ├── lgb_bike_demand.onnx
│   ├── lgb_bus_demand.onnx
│   └── lgb_subway_demand.onnx
└── 2026-10-12/
    └── tuned/                    # [후보] Optuna 튜닝 학습본 (32차원)
        ├── lgb_bike_demand.onnx
        ├── lgb_bus_demand.onnx
        └── lgb_subway_demand.onnx
```

---

## 2. 모델 자산 목록 (검증값)

| 구분 | 경로 | 차원 | 파일 크기 (byte) | 비고 |
| :--- | :--- | :---: | ---: | :--- |
| **기준선 A** | `original/lgb_bike_demand.onnx` | **25** | 4,719,076 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_bus_demand.onnx` | 25 | 4,712,686 | `models/` 와 MD5 동일 |
| 기준선 A | `original/lgb_subway_demand.onnx` | 25 | 4,696,656 | `models/` 와 MD5 동일 |
| **후보** | `2026-10-12/tuned/lgb_bike_demand.onnx` | **32** | 6,782,549 | Optuna 튜닝본 |
| 후보 | `2026-10-12/tuned/lgb_bus_demand.onnx` | 32 | 13,251,388 | Optuna 튜닝본 |
| 후보 | `2026-10-12/tuned/lgb_subway_demand.onnx` | 32 | 9,805,101 | Optuna 튜닝본 |

---

## 3. 입력 차원 규격 (⚠️ 중요)

- 배포본(`models/`, `original/`)은 **25차원**, `2026-10-12/tuned/` 는 **32차원**입니다.
- **25차원 = 32차원 − 7** 부분집합입니다. (아래 4·5절은 사양서 `docs/AI_INFERENCE_MODEL_SPEC.md` §3.2 기준)

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
- **주의**: 현재 `2026-10-12/tuned/` 는 노트북에서 25개 피처 뒤에 **상수 0 더미 7개(`infra_dummy_0..6`)를 덧붙여 32차원**을 만든 것이므로,
  - 정보량은 25차원과 동일하며,
  - **배치 순서가 사양서/`main.py` 와 다릅니다** ([25–31]이 더미). 그대로 서빙에 사용하지 마십시오.

---

## 4. 평가 규약 (Temporal Split)

`docs/AI_INFERENCE_MODEL_SPEC.md` §6.2 기준.

```text
[ 2025-01-01 ~ 2025-09-30 ] : Train      (약 75%)
[ 2025-10-01 ~ 2025-11-15 ] : Validation (약 12.5%) - 조기 종료/튜닝
[ 2025-11-16 ~ 2025-12-31 ] : Test       (약 12.5%) - 최종 일반화 검증
```

- 평가 지표: R² / MAPE / RMSE / MAE + ONNX 추론 레이턴시(ms).
- 학습 원천: `data/2025_서울25개구_시간대별_교통_날씨_통합_01-23시.csv`

---

## 5. 변경 이력

### [2026-10-12] 중복 모델 통합
- 노트북 export 셀 2회 실행으로 `baseline/` 와 `hyperparameter/` 가 **MD5 동일 중복** 생성됨.
  - `baseline/lgb_*.onnx` == `hyperparameter/lgb_* (1).onnx`
  - 실체는 **[Cell 7-1] Optuna 튜닝본(32차원)** 1종.
- 두 폴더를 삭제하고 **`2026-10-12/tuned/` 단일 폴더로 통합**(해시 검증 후 삭제, 무손실).
- 기준선은 `original/`(25차원 = 배포본) 1종으로 정리.

---

## 6. 성능 비교 분석 보고서

- 25차원(배포본) vs 32차원(Optuna 튜닝) **공정 비교 결과**: [**docs/MODEL_PERFORMANCE_REPORT.md**](../docs/MODEL_PERFORMANCE_REPORT.md)
- 원본 수치: `results/comparison_<timestamp>.{json,md}` (`python benchmarks/evaluate_models.py` 로 재생성)