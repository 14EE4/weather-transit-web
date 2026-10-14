# `tuned_real/` — 신규 32차원 **실피처** 모델 산출물 보관 위치

> ## ⛔ [2026-10-14] 배치 위치 종료 — 아래 안내는 이력 보존용입니다.
> 실제 산출물은 **`benchmarks/2026-10-14/`** 에 반입되었습니다(커밋 `07292b4`).
> `benchmarks/evaluate_models.py::MODEL_SETS` 의 `tuned_32d_real` 경로도 `2026-10-14/` 로 갱신되어,
> **이 폴더는 더 이상 사용하지 않습니다.** 자산 설명·평가 방법은 [`../2026-10-14/README.md`](../2026-10-14/README.md) 참조.

`benchmarks/CastTransit.ipynb`(v2, 실제 32차원 8/8/5/11)를 Colab에서 실행하면
아래 3개 파일이 다운로드됩니다. 이 폴더에 그대로 넣어 주세요.

| 파일 | 설명 |
| :--- | :--- |
| `lgb_bike_demand.onnx` | 따릉이 대여 수요 (입력 32차원 · Opset 14) |
| `lgb_bus_demand.onnx` | 버스 승차 수요 (입력 32차원) |
| `lgb_subway_demand.onnx` | 지하철 승차 수요 (입력 32차원) |
| `feature_schema.json` | 피처 순서/분할/공휴일 캘린더 메타 (검증용) |

## 왜 별도 폴더인가

`benchmarks/2026-10-12/tuned/` 의 기존 32차원 모델은 v1 배치
(25차원 `8/8/1/3/3/2` + 상수 0 더미 7)로 학습되어,
v2 실피처 배치(`8/8/5/11`)와 **컬럼 순서가 다릅니다.**
그대로 비교하면 인덱스 16 이후가 전부 어긋나므로 별도 폴더로 분리했습니다.

## 평가

```bash
python benchmarks/evaluate_models.py
# → benchmarks/results/comparison_{timestamp}.json / .md
```

`evaluate_models.py` 는 사양서 §6.1 Temporal Split(test 2025-11-16 ~ 12-31)과
2025 대한민국 실제 공휴일 캘린더(19일)를 적용하며, 25차원 배포본과 **동일한
피처 프레임**에서 32차원 서브셋/전체를 각각 만들어 공정 비교합니다.