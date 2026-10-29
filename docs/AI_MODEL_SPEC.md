# 🧩 AI 모델 사양서 (AI Model Specification)

> **문서 버전**: v2.1-multiyear-32d  
> **최종 수정일**: 2026-10-29  
> **적용 모델**: LightGBM ONNX 3종 (`models/lgb_{bike,bus,subway}_demand.onnx`)  
> **단일 진실 공급원(SSoT)**: [`models/feature_schema.json`](../models/feature_schema.json)  
> **관련 문서**: [CURRENT_DATA_SPEC.md](./CURRENT_DATA_SPEC.md) · [CURRENT_MODEL_PERFORMANCE.md](./CURRENT_MODEL_PERFORMANCE.md) · [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)

---

## 📌 목차
1. [모델 개요 및 목표](#1-모델-개요-및-목표)
2. [성능 지표 및 서비스 수준 협약 (SLA)](#2-성능-지표-및-서비스-수준-협약-sla)
3. [입력 피처 규격 (32차원 실피처)](#3-입력-피처-규격-32차원-실피처)
4. [모델 아키텍처 및 추론 파이프라인](#4-모델-아키텍처-및-추론-파이프라인)
5. [다년도 학습 및 분할 규격 (Temporal Split)](#5-다년도-학습-및-분할-규격-temporal-split)
6. [배포 모델 자산 명세 (`models/`)](#6-배포-모델-자산-명세-models)
7. [과거 버전 아카이브 안내](#7-과거-버전-아카이브-안내)

---

## 1. 모델 개요 및 목표

본 시스템은 서울시 25개 자치구의 날씨 및 시계열 교통 관측 데이터(총 62.9만 행)를 기반으로 **실시간 다중 수단 수요 예측**과 **최적 이동수단 추천 스코어링**을 제공하는 고성능 경량 AI 엔진입니다.

1. **다중 수단 수요 예측 (Multi-modal Demand Prediction)**:
   - 기상 요인(강수량, 기온, 습도, 풍속)과 시공간 특성(자치구 인프라, 시간대, 요일, 공휴일, 과거 래그)을 종합하여 **따릉이 대여 / 버스 승차 / 지하철 승차** 수요를 동시 예측.
2. **실시간 혼잡도 지수화 (Congestion Indexing)**:
   - 예측된 수송 수요를 수단별 최대 수용능력(Capacity 95 백분위수)과 비교하여 0~100% 혼잡도로 정규화 (`여유 <45%`, `보통 45~75%`, `혼잡 >75%`).
3. **AHP 기반 추천 스코어링**:
   - 기상 안전/쾌적성(57.14%), 정시성(28.57%), 혼잡 회피(14.29%)의 3대 요소를 반영하여 수단별 0~100점 추천 점수 및 SHAP 기여도 기반 자연어 추천 사유 도출.

---

## 2. 성능 지표 및 서비스 수준 협약 (SLA)

| 항목 | 목표 SLA | 현행 실측 달성치 (2026-10-29) | 상태 |
| :--- | :---: | :---: | :---: |
| **단건 추론 지연 (Latency)** | $\le 15\text{ ms}$ | **0.054 ~ 0.057 ms** (3수단 합산 0.17 ms) | 🟢 **초과 달성 (50배 빠름)** |
| **따릉이 예측 정확도** | $R^2 \ge 0.85$, $\text{MAPE} \le 18\%$ | **$R^2 = 0.9894$, $\text{MAPE} = 16.08\%$** | 🟢 **목표 달성** |
| **버스 승차 예측 정확도** | $R^2 \ge 0.88$, $\text{MAPE} \le 15\%$ | **$R^2 = 0.9928$, $\text{MAPE} = 13.81\%$** | 🟢 **목표 달성** |
| **지하철 승차 예측 정확도** | $R^2 \ge 0.90$, $\text{MAPE} \le 12\%$ | **$R^2 = 0.9950$, $\text{MAPE} = 11.23\%$** | 🟢 **목표 달성** |

*세부 모델별 검증 지표는 [`docs/CURRENT_MODEL_PERFORMANCE.md`](./CURRENT_MODEL_PERFORMANCE.md) 참조.*

---

## 3. 입력 피처 규격 (32차원 실피처)

현행 모델은 더미 변수 없이 **순수 32차원 실수 벡터**를 입력받습니다.  
피처의 순서 및 정의는 [`models/feature_schema.json`](../models/feature_schema.json) 및 [`main.py::build_feature_vector`](../main.py)와 100% 일치합니다.

```
 인덱스   피처명                      타입     설명
────────────────────────────────────────────────────────────────────────────
 [0..3]  month_sin, month_cos       float    월 순환 인코딩 (sin/cos 2π*month/12)
         hour_sin, hour_cos         float    시간 순환 인코딩 (sin/cos 2π*hour/24)
 [4..7]  dayofweek                  int      요일 (0:월 ~ 6:일)
         is_weekend                 int      주말 여부 (토/일 = 1)
         is_holiday                 int      관공서 공휴일 캘린더 19일 기준 여부
         is_rush_hour               int      출퇴근 시간대 (08~09시, 18~20시 = 1)
────────────────────────────────────────────────────────────────────────────
 [8..15] temperature                float    기온 (°C)
         wind_speed                 float    풍속 (m/s)
         humidity                   float    상대 습도 (%)
         precipitation              float    1시간 강수량 (mm)
         is_raining                 int      강수 유무 (강수량 > 0 = 1)
         rain_intensity             int      강우 강도 (0:무강우, 1:소우, 2:보통, 3:폭우)
         sensible_temp              float    체감온도 (°C)
         discomfort_index           float    불쾌지수
────────────────────────────────────────────────────────────────────────────
 [16..20] district_code             int      자치구 코드 (1:강남 ~ 25:중랑)
          district_subway_stations  int      구 내 지하철역 수
          district_bus_stops        int      구 내 버스 정류소 수
          district_bike_racks       int      구 내 따릉이 거치대 수
          commercial_density        float    구 상업/업무밀도 지수
────────────────────────────────────────────────────────────────────────────
 [21..26] 따릉이_대여_lag_1h          float    1시간 전 따릉이 대여량
          버스_승차_lag_1h           float    1시간 전 버스 승차량
          지하철_승차_lag_1h         float    1시간 전 지하철 승차량
          따릉이_대여_roll_3h         float    직전 3시간 이동평균
          버스_승차_roll_3h          float    직전 3시간 이동평균
          지하철_승차_roll_3h        float    직전 3시간 이동평균
 [27..29] same_day_last_week_bike   float    7일 전 동일 요일·동일 시각 대여량
          same_day_last_week_bus    float    7일 전 동일 요일·동일 시각 승차량
          same_day_last_week_sub    float    7일 전 동일 요일·동일 시각 승차량
 [30..31] temp_diff_1h              float    전 시간 대비 기온 변화량
          rain_diff_1h              float    전 시간 대비 강수량 변화량
```

*자치구별 인프라 수치 및 상세 전처리 규격은 [`docs/CURRENT_DATA_SPEC.md`](./CURRENT_DATA_SPEC.md) 참조.*

---

## 4. 모델 아키텍처 및 추론 파이프라인

### 4.1 파이프라인 플로우

```mermaid
flowchart LR
    A["실시간 관측<br>(기상청 / 서울교통)"] --> B["피처 엔지니어링<br>(인프라 조인 & 래그)"]
    B --> C["32차원 벡터 빌드<br>(build_feature_vector)"]
    C --> D["ONNX Runtime<br>(lgb_*_demand.onnx)"]
    D --> E["예측 수요량 (bike, bus, sub)"]
    E --> F["혼잡도 정규화 (0~100%)"]
    F --> G["AHP 종합 추천 스코어 산출"]
```

### 4.2 AHP 기반 이동수단 추천 스코어링 공식 ($Score_m$)

$$Score_m = \max\left(5, \; \min\left(99, \; 100 - \left( 0.5714 \cdot \text{WeatherPenalty}_m + 0.2857 \cdot \text{DelayRisk}_m + 0.1429 \cdot \text{CrowdPenalty}_m \right)\right)\right)$$

- **기상 페널티 ($WeatherPenalty$)**:
  - 따릉이: $\min(85, \; (40.0 + 12.0 \times Rain) \cdot \mathbb{I}_{Rain>0})$ (0.1mm 비에도 -73.6% 급감 반영)
  - 버스: $\min(30, \; 3.5 \times Rain + 5.0)$ (승하차 우산 및 감속 불편)
  - 지하철: $0.0$ (지하 운행으로 기상 노출 없음)
- **정시성 위험 ($DelayRisk$)**:
  - 따릉이: 8.0, 버스: $12.0 + 2.5 \times Rain$, 지하철: 2.0 (실측 정시운행률 99.2%)
- **혼잡도 페널티 ($CrowdPenalty$)**:
  - 따릉이: $0.15 \times C_{\text{bike}}$, 버스: $0.35 \times C_{\text{bus}}$, 지하철: $0.40 \times C_{\text{subway}}$

---

## 5. 다년도 학습 및 분할 규격 (Temporal Split)

과거 데이터 누수를 방지하기 위해 3개년 시계열을 엄격히 시간순으로 분할합니다:

```text
[ 2023-01-01 ~ 2024-09-30 ] : Train Set      (약 38.5만 행, 61.2%) - 모델 가중치 학습
[ 2024-10-01 ~ 2024-12-31 ] : Validation Set (약  5.4만 행,  8.6%) - Early Stopping 및 파라미터 튜닝
[ 2025-01-01 ~ 2025-12-31 ] : Test Set       (약 21.0만 행, 33.3%) - 1년 전체 Out-of-Time 최종 검증
```

---

## 6. 배포 모델 자산 명세 (`models/`)

모든 배포 모델은 `models/` 디렉터리에 위치하며 서빙 시작 시 `ModelRegistry`에 의해 무결성 검증을 거칩니다.

| 자산 파일명 | 알고리즘 | 추론 타깃 | 텐서 형상 | 파일 크기 | SHA-256 (Prefix) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `lgb_bike_demand.onnx` | LightGBM GBDT | 따릉이_대여 | `[None, 32]` | 7,020,769 B | `b491fa58...` |
| `lgb_bus_demand.onnx` | LightGBM GBDT | 버스_승차 | `[None, 32]` | 13,596,760 B | `0fcabf26...` |
| `lgb_subway_demand.onnx` | LightGBM GBDT | 지하철_승차 | `[None, 32]` | 7,345,447 B | `cf578b7b...` |
| `feature_schema.json` | JSON Schema | 메타/SSoT | — | 3,180 B | `473f309a...` |

---

## 7. 과거 버전 아카이브 안내

초기 25차원 모델(v1), 7차원 더미 변수 실험, 2025 단년도 전처리 핸드오프 문서는 히스토리 보존을 위해 아카이브로 격리 보관 중입니다.

- **문서 아카이브**: [`docs/archive/README.md`](./archive/README.md)
  - 구 전처리 인수인계서: [`docs/archive/DATA_PREPROCESSING_HANDOFF_v2.md`](./archive/DATA_PREPROCESSING_HANDOFF_v2.md)
  - 구 모델 비교 리포트: [`docs/archive/MODEL_PERFORMANCE_REPORT_v1_v2.md`](./archive/MODEL_PERFORMANCE_REPORT_v1_v2.md)
- **자산 아카이브**: [`benchmarks/archive/README.md`](../benchmarks/archive/README.md)
  - 기준선 25차원 모델: `benchmarks/archive/original/`
  - v1 더미 모델: `benchmarks/archive/2026-10-12/`
  - 2025 단년도 v2 모델: `benchmarks/archive/2026-10-14/`
