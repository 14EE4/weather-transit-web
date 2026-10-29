# `tuned_25d_colab/` — Colab 재현 산출물 (**반입·검증 완료** · 2026-10-14)

`benchmarks/retrain_25d_colab.ipynb` 를 Colab에서 실행해 반출한 산출물을 이 폴더에 넣었습니다.
(로컬 실행본 `../tuned_25d/` 는 대조군으로 **그대로 보존**되어 있습니다.)

## 파일 4개 (반입 완료)

| 파일 | 설명 | 크기(byte) |
| :--- | :--- | ---: |
| `lgb_bike_demand.onnx` | 따릉이 대여 수요 (ONNX 입력 `[None, 25]`) | 5,709,941 |
| `lgb_bus_demand.onnx` | 버스 승차 수요 (입력 25차원) | 14,574,454 |
| `lgb_subway_demand.onnx` | 지하철 승차 수요 (입력 25차원) | 3,713,077 |
| `feature_schema.json` | 25차원 서빙 스키마 (`model_version: v2-전처리_2-25d-retrain-colab`) + Colab `env` | 3,081 |

> ONNX 3종 크기는 로컬 `../tuned_25d/` 와 **완전히 동일**했습니다(`feature_dim: 25`·`layout: 25d-subset` 자동 판별).

## ✅ 검증 결과 — 플랫폼 편차 **0** (`benchmarks/results/comparison_20261014_214856.{json,md}`)

| 수단 | R² | RMSE | MAE | MAPE≠0 | best_iter | 로컬 `tuned_25d/` 대비 |
| :---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 🚲 bike | 0.9883 | 16.666 | 9.677 | 16.19% | 680 | **Δ = 0** |
| 🚌 bus | 0.9912 | 528.628 | 342.732 | 14.07% | 1,498 | **Δ = 0** |
| 🚇 subway | 0.9935 | 769.318 | 330.871 | 4.96% | 446 | **Δ = 0** |

- R²·RMSE·MAE·MAPE·`best_iteration` **12개 지표 전부 Δ = 0.000000** · `best_params`·25차원 피처 순서 일치 · ONNX **파일 크기 3종 동일**(직렬화 메타 차이로 SHA256 만 상이).
- Colab 환경(`env` 블록): python 3.13.16 · **lightgbm 4.7.0(로컬과 동일)** · numpy 2.1.3 · pandas 2.2.3.
- ⇒ 로컬 25차원 재학습 결과가 Colab 재현성까지 확보되어 **모델 순위·교체 판단 근거는 변동 없음**.

## (참고) 다시 실행할 때 — 반출 파일 가져오는 방법

1. **Drive 동기화(권장)** — 노트북 `[Step 4]` 가 `MyDrive/weather-transit-web/benchmarks/2026-10-14/tuned_25d_colab/` 에 써 둡니다.
   Drive 웹에서 그 폴더의 파일 4개를 내려받아 **이 폴더에 그대로** 넣습니다.
2. **브라우저 다운로드** — `[Step 4]` 마지막 `files.download` 로 받은 파일 4개를 넣습니다.
   (Drive 폴더째 내려받아 `tuned_25d_colab.zip` 이라면 압축을 풀어 같은 4개를 배치합니다.)

> 재실행 결과가 반입본과 달라졌다면 크기·`feature_dim`·`layout` 부터 확인하십시오. `retrain_25d_colab.ipynb` 의 `[Cell 6-1]`(Optuna)은 **건너뛰고** 스키마의 `best_params` 를 고정 주입하므로, 파라미터가 같으면 산출물은 재현됩니다.

## 확인·평가 명령

```powershell
# 1) 파일 4개 · 크기 확인
Get-ChildItem benchmarks\2026-10-14\tuned_25d_colab

# 2) 4-way 비교(배포본 25d · v1 32d · v2 32d · 이번 Colab 25d)
python benchmarks/evaluate_models.py --model tuned_25d_colab=benchmarks/2026-10-14/tuned_25d_colab

# 3) 로컬 실행본까지 포함한 5-way 비교
python benchmarks/evaluate_models.py --model tuned_25d_colab=benchmarks/2026-10-14/tuned_25d_colab --model tuned_25d=benchmarks/2026-10-14/tuned_25d
```

`evaluate_models.py::pick_input` 이 **ONNX 입력 차원으로 레이아웃을 자동 판별**하므로 별도 옵션이 필요 없습니다(`dim=25` → `25d-subset`).
스키마·대조 기준은 [`../README.md`](../README.md) 의 `tuned_25d_colab/` 절 · 진행 항목은 `docs/TODO.md` §4 를 보십시오.

> 이 폴더의 ONNX 를 비우면 평가 스크립트는 해당 라벨을 `[skip]` 하고 나머지 비교는 그대로 진행합니다(크래시 없음).

## ⚠️ 배포 반입 시 주의 — 이 폴더의 `feature_schema.json` 을 `models/` 슬롯에 넣지 마세요

- 배포 슬롯 교체 대상은 `models/lgb_{bike,bus,subway}_demand.onnx` **ONNX 3종만** 입니다.
- 이 폴더의 스키마는 **25차원**(`model_version: v2-전처리_2-25d-retrain-colab`)인데, `feature_schema.py::validate_expected_order` 는 스키마가 `main.py::FEATURE_ORDER_32`(**32차원**)와 **완전 일치**할 것을 요구합니다 → `models/feature_schema.json` 으로 넣으면 **서버 기동이 중단**됩니다(2026-10-14 실측: `validate_expected_order → FAIL`).
- 교체 후 `/health.feature_schema.status` 는 **`legacy-subset-25d` 유지가 정상**(모델 25차원 + 현행 32차원 SSoT)이며, `verified` 는 **32차원 자산 + 32차원 스키마**일 때만 나옵니다.