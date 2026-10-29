# 📦 Archived Documentation (레거시 문서 보관소)

이 디렉터리는 과거 버전(v1, v2 단년도 25차원/구 32차원 더미)의 모델 개발, 전처리 및 성능 벤치마크 문서를 보관하는 아카이브입니다.
현재 운영 중인 최신 다년도(2023~2025) 32차원 파이프라인 명세와 분리하여 혼선을 방지하고 개발 히스토리를 보존합니다.

---

## 📂 보관된 문서 목록

| 파일명 | 원래 위치 | 설명 및 보관 사유 |
| :--- | :--- | :--- |
| [`DATA_PREPROCESSING_HANDOFF_v2.md`](./DATA_PREPROCESSING_HANDOFF_v2.md) | `docs/DATA_PREPROCESSING_HANDOFF.md` | 2025년 단년도 33열 원천 데이터 핸드오프 문서 (풍향, 지하철 하차 등 미사용 컬럼 포함 구 규격). 2026-10-29 다년도 28열 통합 파이프라인으로 대체됨. |
| [`MODEL_PERFORMANCE_REPORT_v1_v2.md`](./MODEL_PERFORMANCE_REPORT_v1_v2.md) | `docs/MODEL_PERFORMANCE_REPORT.md` | v1(25차원) 및 v2(2025 단년도 32차원) 모델 비교 성능 리포트. 2026-10-29 신규 모델 성능은 [`CURRENT_MODEL_PERFORMANCE.md`](../CURRENT_MODEL_PERFORMANCE.md)로 이관. |
| [`AI_INFERENCE_MODEL_SPEC_initial.md`](./AI_INFERENCE_MODEL_SPEC_initial.md) | `docs/AI_INFERENCE_MODEL_SPEC.md` | 초기 개발 단계(2026-09-30) 모델 기획 및 구축 종합 가이드 원문. |

---

## 📌 현재 현행(Current) 문서 안내

현재 프로덕션 및 개발에 사용되는 최신 문서들은 아래 링크를 참조하십시오.

1. **최신 데이터 규격**: [`docs/CURRENT_DATA_SPEC.md`](../CURRENT_DATA_SPEC.md) (2023~2025 3개년 28열 표준 데이터셋 및 32차원 피처 생성 규격)
2. **최신 모델 성능 리포트**: [`docs/CURRENT_MODEL_PERFORMANCE.md`](../CURRENT_MODEL_PERFORMANCE.md) (2026-10-29 기준 v2.1 32차원 모델 평가 및 Optuna 파라미터)
3. **최신 AI 모델 통합 사양서**: [`docs/AI_MODEL_SPEC.md`](../AI_MODEL_SPEC.md) (서빙 및 추론 인터페이스 명세)
