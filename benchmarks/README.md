# 📊 Benchmarks — 모델 자산 및 평가 규약

> 학습된 ONNX 모델 스냅샷과 벤치마크 재료를 보관하는 디렉터리입니다.
> **모델 자산 구조/차원 규격은 이 문서를 단일 기준(SSoT)으로 삼습니다.**

---

## 1. 폴더 구조

```text
benchmarks/
├── README.md                     # (이 문서) 자산 구조 및 평가 규약
├── CastTransit.ipynb             # LightGBM 학습/튜닝/ONNX export 노트북 (v2.1: 2023~2025 3개년 28열 통합데이터)
├── evaluate_models.py            # 공정 비교 평가 스크립트 (32차원 실피처 + 스키마 SSoT 검증)
├── retrain_25d.py                # [실험] 동일 v2 파라미터 + 25차원 서브셋 재학습 (차원 vs 튜닝 분리)
├── retrain_25d_colab.ipynb       # [실험·Colab] 25차원 재학습 Colab 재현 노트북
├── 2026-10-29/                   # [현행 배포본] v2.1 다년도(2023~2025) 32차원 실피처 산출물 (models/ 와 동일)
│   ├── lgb_bike_demand.onnx
│   ├── lgb_bus_demand.onnx
│   ├── lgb_subway_demand.onnx
│   ├── feature_schema.json       # 피처 순서·다년도 분할·하이퍼파라미터 메타 (SSoT)
│   └── README.md                 # 산출물 사양 및 메트릭
├── results/                      # 평가 결과 (comparison_<timestamp>.json / .md)
└── archive/                      # [레거시 자산 보관소] 과거 세대 모델 및 실험 보관
    ├── README.md                 # 아카이브 안내
    ├── original/                 # [기준선] 초기 배포본 스냅샷 (25차원)
    ├── 2026-10-12/               # [구 후보] v1 32차원 (25차원 + 더미 7차원)
    └── 2026-10-14/               # [구 배포본] 2025 단년도 32차원 실피처 및 25차원 재학습 모델
```

> 피처 스키마 로더/검증 모듈은 레포 루트의 [`feature_schema.py`](../feature_schema.py) 이며,
> 서빙(`main.py`)·평가(`evaluate_models.py`)·재학습이 **공통으로 import** 합니다.

---

## 2. 모델 자산 목록 (검증값)

| 구분 | 경로 | 차원 | 타깃 | 비고 |
| :--- | :--- | :---: | :--- | :--- |
| **현행 배포본 (v2.1)** | `benchmarks/2026-10-29/lgb_bike_demand.onnx` | **32** | `따릉이_대여` | 2023~2025 다년도 학습, $R^2=0.9894$, `models/` 동기화 |
| 현행 배포본 (v2.1) | `benchmarks/2026-10-29/lgb_bus_demand.onnx` | **32** | `버스_승차` | 2023~2025 다년도 학습, $R^2=0.9928$, MAPE=13.81% 대폭 개선 |
| 현행 배포본 (v2.1) | `benchmarks/2026-10-29/lgb_subway_demand.onnx` | **32** | `지하철_승차` | 2023~2025 다년도 학습, $R^2=0.9950$, MAE=284.4 |
| 현행 스키마 | `benchmarks/2026-10-29/feature_schema.json` | — | — | v2.1-multiyear-32d (다년도 시계열 분할 SSoT) |
| **아카이브 (v2)** | `benchmarks/archive/2026-10-14/` | 32 / 25 | 승차 3종 | 2025 단년도 데이터 학습 산출물 |
| **아카이브 (v1)** | `benchmarks/archive/2026-10-12/tuned/` | 32 | 승차 3종 | 25차원 + 더미 7차원 구조 |
| **아카이브 (기준선)** | `benchmarks/archive/original/` | 25 | 승차 3종 | 최초 25차원 배포본 모델 |

---

## 3. 현행 모델 피처 규격 (32차원 실피처)

현재 운영 모델은 **실제 32차원 피처(더미 0 없음)** 를 사용하며 순서는 아래와 같습니다:

| 인덱스 | 피처 그룹 | 피처명 |
| :--- | :--- | :--- |
| **[0–7]** | 시간 및 달력 (8) | `month_sin`, `month_cos`, `hour_sin`, `hour_cos`, `dayofweek`, `is_weekend`, `is_holiday`, `is_rush_hour` |
| **[8–15]** | 기상 관측 및 파생 (8) | `temperature`, `wind_speed`, `humidity`, `precipitation`, `is_raining`, `rain_intensity`, `sensible_temp`, `discomfort_index` |
| **[16–20]** | 공간 및 인프라 (5) | `district_code`, `district_subway_stations`, `district_bus_stops`, `district_bike_racks`, `commercial_density` |
| **[21–31]** | 시계열 래그 및 1시간 변화량 (11) | `따릉이_대여_lag_1h`, `버스_승차_lag_1h`, `지하철_승차_lag_1h`, `따릉이_대여_roll_3h`, `버스_승차_roll_3h`, `지하철_승차_roll_3h`, `same_day_last_week_bike`, `same_day_last_week_bus`, `same_day_last_week_sub`, `temp_diff_1h`, `rain_diff_1h` |

---

## 4. 평가 규약

- **원천 데이터**: `data/2025_서울25개구_교통날씨_전처리_2.csv` (209,875행 × 28열/33열 호환)
- **시계열 분할**: 사양서 Temporal Split 기준
- **평가 스크립트 실행**:
  ```bash
  python benchmarks/evaluate_models.py
  ```
- **개별 모델 지정 평가**:
  ```bash
  python benchmarks/evaluate_models.py --model current_32d=benchmarks/2026-10-29
  ```
- **자세한 비교 리포트**: [`docs/CURRENT_MODEL_PERFORMANCE.md`](../docs/CURRENT_MODEL_PERFORMANCE.md) 참조
