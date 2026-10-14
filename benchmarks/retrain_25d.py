# -*- coding: utf-8 -*-
"""
benchmarks/retrain_25d.py
================================================================================
**차원 vs 튜닝 분리 실험** — v2 32차원 후보와 **동일한 Optuna 파라미터**를 그대로 쓰되
피처를 **25차원 서빙 서브셋**(배포본과 동일한 인덱스 `range(17)+[21..26]+[30,31]`)으로 줄여
재학습하고, 동일 테스트 구간(2025-11-16 ~ 12-31)에서 지표를 비교한다.

무엇을 분리하나
    배포본(25차원) vs v2 후보(32차원)의 성능 차이는 ① 차원 ② Optuna 튜닝 ③ 신규 원천
    (`전처리_2`) 이 동시에 바뀐 결과였습니다(교란 3중). 이 스크립트는 ② 를 **고정**하고
    ① 만 25차원으로 바꾼 대조군을 만듭니다 → "차원 증가의 순수 효과" 를 분리합니다.

산출물
    * (기본) 지표 JSON/MD → `benchmarks/results/retrain_25d_{timestamp}.{json,md}`
    * `--export` 시 ONNX 3종 + `feature_schema.json`(25차원 서빙 배치) →
      기본 `benchmarks/<실행일>/tuned_25d/`
      → 이후 정규 하네스로 검증:
         python benchmarks/evaluate_models.py --model tuned_25d=benchmarks/<실행일>/tuned_25d

전제
    `feature_schema.json`(SSoT) 의 `metrics.<mode>.tuned.best_params` 를 고정 파라미터로 사용합니다.
    스키마가 없으면 `--params PATH` 로 JSON(`{'learning_rate': …, …}`) 을 직접 넘길 수 있습니다.

실행
    python benchmarks/retrain_25d.py                 # 학습 + 지표 리포트 (로컬 CPU)
    python benchmarks/retrain_25d.py --export        # + ONNX/스키마 반출(onnxmltools 필요)
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 피처 정의·지표·전처리는 정규 하네스(evaluate_models)를 그대로 재사용한다(드리프트 차단).
from benchmarks.evaluate_models import (  # noqa: E402
    CSV_PATH,
    FEATURE_COLS_25,
    FEATURE_COLS_32,
    ROOT as _ROOT,  # noqa: F401  (동일 루트 재확인용)
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    load_and_engineer,
    regression_metrics,
    verify_feature_schema,
)
from feature_schema import load_schema, resolve_schema_path, schema_feature_cols  # noqa: E402

BENCH_DIR = ROOT / "benchmarks"
RESULTS_DIR = BENCH_DIR / "results"

# 노트북 [Cell 6-1] 과 동일한 학습 프레임(파라미터 탐색값만 스키마에서 고정 주입)
TRAIN_FRAME = {
    "objective": "regression",
    "metric": "rmse",
    "boosting_type": "gbdt",
    "n_estimators": 1500,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}
EARLY_STOPPING_ROUNDS = 50

TARGETS = {"bike": "따릉이_대여", "bus": "버스_승차", "subway": "지하철_승차"}


def frozen_params(schema: dict | None, explicit: Path | None) -> dict[str, dict]:
    """수단별 고정 하이퍼파라미터를 스키마(SSoT) 또는 `--params` JSON 에서 읽는다."""
    if explicit is not None:
        payload = json.loads(Path(explicit).read_text(encoding="utf-8"))
        if set(payload) >= set(TARGETS) and all(isinstance(v, dict) for v in payload.values()):
            return {mode: dict(payload[mode]) for mode in TARGETS}
        return {mode: dict(payload) for mode in TARGETS}  # 단일 dict → 3수단 공통 적용

    if schema is None:
        raise SystemExit(
            "[중단] feature_schema.json 을 찾지 못했습니다. `--params PATH` 로 파라미터를 지정하세요."
        )
    metrics = schema.get("metrics") or {}
    out: dict[str, dict] = {}
    for mode in TARGETS:
        node = ((metrics.get(mode) or {}).get("tuned") or {})
        if not node.get("best_params"):
            raise SystemExit(f"[중단] 스키마 metrics.{mode}.tuned.best_params 가 없습니다.")
        out[mode] = dict(node["best_params"])
    return out


def train_25d(df, frozen: dict[str, dict], schema: dict | None) -> dict:
    """25차원 서브셋으로 3수단 모델을 학습하고 테스트 지표를 계산한다."""
    import lightgbm as lgb

    train_mask = df["기준_날짜"] <= TRAIN_END
    val_mask = (df["기준_날짜"] > TRAIN_END) & (df["기준_날짜"] <= VAL_END)
    test_mask = df["기준_날짜"] > VAL_END

    X_train = df.loc[train_mask, FEATURE_COLS_25].astype(np.float32).to_numpy()
    X_val = df.loc[val_mask, FEATURE_COLS_25].astype(np.float32).to_numpy()
    X_test = df.loc[test_mask, FEATURE_COLS_25].astype(np.float32).to_numpy()
    print(
        f"[data] 25차원 서브셋 | train={X_train.shape} val={X_val.shape} test={X_test.shape} "
        f"| test {TEST_START}~{TEST_END}"
    )

    schema_metrics = (schema or {}).get("metrics") or {}
    out: dict[str, dict] = {}
    for mode, target_col in TARGETS.items():
        y_tr = df.loc[train_mask, target_col].astype(np.float64).to_numpy()
        y_va = df.loc[val_mask, target_col].astype(np.float64).to_numpy()
        y_te = df.loc[test_mask, target_col].astype(np.float64).to_numpy()

        params = dict(frozen[mode])
        params.update(TRAIN_FRAME)
        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train, y_tr,
            eval_set=[(X_val, y_va)],
            callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
        )
        best_iter = int(getattr(model, "best_iteration_", 0) or TRAIN_FRAME["n_estimators"])
        pred = np.clip(model.predict(X_test), 0.0, None)
        rec = regression_metrics(y_te, pred)
        rec["best_iteration"] = best_iter
        rec["frozen_params"] = dict(frozen[mode])

        v2 = ((schema_metrics.get(mode) or {}).get("tuned") or {})
        if v2:
            rec["reference_v2_32d"] = {k: v2.get(k) for k in ("r2", "rmse", "mae", "best_iteration")}
            rec["delta_vs_v2_32d"] = {
                "r2": rec["r2"] - float(v2["r2"]),
                "rmse": rec["rmse"] - float(v2["rmse"]),
                "mae": rec["mae"] - float(v2["mae"]),
            }
        out[mode] = rec
        print(
            f"[train25d] {mode:6s} R2={rec['r2']:.4f} RMSE={rec['rmse']:+9.3f} "
            f"MAE={rec['mae']:8.3f} MAPE(≠0)={rec['mape_pct_nonzero']:.2f}% "
            f"best_iter={best_iter}"
        )
        out[mode]["_model"] = model  # export 단계에서만 사용(JSON 저장 시 제거)
    return out


def export_assets(results: dict[str, dict], out_dir: Path, schema: dict | None) -> list[str]:
    """`--export` 시 ONNX 3종 + 25차원 서빙 배치 `feature_schema.json` 을 반출한다."""
    try:
        import onnxmltools
        import onnxruntime as ort
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ModuleNotFoundError as exc:  # export 는 선택 단계(지표는 이미 확보됨)
        print(f"[export] 건너뜀 — {exc.name} 미설치 (pip install onnxmltools skl2onnx)")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    initial_type = [("float_input", FloatTensorType([None, len(FEATURE_COLS_25)]))]
    written: list[str] = []
    for mode, rec in results.items():
        path = out_dir / f"lgb_{mode}_demand.onnx"
        onnx_model = onnxmltools.convert_lightgbm(
            rec["_model"], initial_types=initial_type, target_opset=14
        )
        path.write_bytes(onnx_model.SerializeToString())
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        dim = int(sess.get_inputs()[0].shape[1])
        assert dim == len(FEATURE_COLS_25), f"export 차원 오류: {path.name} = {dim}"
        print(f"[export] {path.relative_to(ROOT).as_posix()} ({path.stat().st_size:,} byte, {dim}차원)")
        written.append(path.relative_to(ROOT).as_posix())

    # 25차원 서빙 배치 스키마(서빙 main.py::prepare_session_input 의 서브셋과 동일 순서)
    schema_out = {
        "model_version": "v2-전처리_2-25d-retrain",
        "feature_dim": len(FEATURE_COLS_25),
        "feature_cols": FEATURE_COLS_25,
        "order": ["calendar(8)", "weather(8)", "spatial(1)", "timeseries(6+2)"],
        "layout": "25d-subset",
        "derived_from": {
            "model_version": (schema or {}).get("model_version"),
            "feature_dim_32d": len(FEATURE_COLS_32),
            "note": "v2 32차원 SSoT 의 25차원 서빙 서브셋 — main.py::prepare_session_input 과 순서 동일",
        },
        "targets": TARGETS,
        "split": {
            "train": f"2025-01-01~{TRAIN_END}",
            "valid": f"2025-10-01~{VAL_END}",
            "test": f"{TEST_START}~{TEST_END}",
        },
        "split_source": "spec_dates",
        "holiday_calendar": "KR_HOLIDAYS_2025 (19일, main.py::KR_HOLIDAYS 와 동일)",
        "metrics": {
            mode: {
                "tuned": {
                    k: rec[k] for k in ("r2", "rmse", "mae", "mape_pct_nonzero", "best_iteration")
                },
                "best_params": rec["frozen_params"],
            }
            for mode, rec in results.items()
        },
    }
    schema_path = out_dir / "feature_schema.json"
    schema_path.write_text(json.dumps(schema_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[export] {schema_path.relative_to(ROOT).as_posix()} (25차원 서빙 배치 스키마)")
    written.append(schema_path.relative_to(ROOT).as_posix())
    return written


def write_report(results: dict[str, dict], meta: dict, export_dir: Path | None, written: list[str]) -> Path:
    """결과 JSON/MD 저장 — 정규 하네스(`evaluate_models.py`) 호출 방법까지 함께 기록한다."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"retrain_25d_{stamp}.json"
    md_path = RESULTS_DIR / f"retrain_25d_{stamp}.md"

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "experiment": "차원 vs 튜닝 분리 — 동일 v2 파라미터 + 25차원 서빙 서브셋 재학습",
        "meta": meta,
        "exported": written,
        "results": {
            mode: {k: v for k, v in rec.items() if not k.startswith("_")}
            for mode, rec in results.items()
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 25차원 재학습 (동일 v2 파라미터) — 차원 vs 튜닝 분리 실험",
        "",
        f"- 생성시각: {payload['generated_at']}",
        f"- 원천: `{meta['csv']}` | 분할: train≤{TRAIN_END} / valid≤{VAL_END} / test {TEST_START}~{TEST_END}",
        f"- 피처: 25차원 서빙 서브셋(인덱스 {meta['legacy_indices']}) — 배포본과 동일 정보량",
        f"- 고정 파라미터 출처: {meta['params_source']} (Optuna 재탐색 없음 → **차원 효과만 분리**)",
        "",
        "| 수단 | 재학습 25d R² | 재학습 25d RMSE | 재학습 25d MAE | MAPE(≠0) | best_iter | ΔR² vs v2 32d | ΔMAE vs v2 32d |",
        "| :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, rec in results.items():
        delta = rec.get("delta_vs_v2_32d") or {}
        lines.append(
            f"| {mode} | {rec['r2']:.4f} | {rec['rmse']:.3f} | {rec['mae']:.3f} | "
            f"{rec['mape_pct_nonzero']:.2f}% | {rec['best_iteration']} | "
            f"{delta.get('r2', float('nan')):+.4f} | {delta.get('mae', float('nan')):+.3f} |"
        )
    lines += [
        "",
        "- Δ 는 **스키마에 기록된 v2 32차원 노트북 지표** 대비입니다(양수 = 25차원이 열세).",
        "- 배포본(25차원)·v1 32차원·v2 32차원과의 **동일 프레임 4-way 비교**는 정규 하네스로 수행합니다:",
    ]
    if export_dir is not None and written:
        rel = export_dir.relative_to(ROOT).as_posix()
        lines.append(f"  `python benchmarks/evaluate_models.py --model tuned_25d={rel}`")
    else:
        lines.append("  `python benchmarks/retrain_25d.py --export` 로 ONNX 반출 후 위 명령 실행")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n[저장] {json_path.relative_to(ROOT).as_posix()}")
    print(f"[저장] {md_path.relative_to(ROOT).as_posix()}")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="동일 v2 파라미터 + 25차원 서브셋 재학습(차원 효과 분리)"
    )
    parser.add_argument("--csv", default=str(CSV_PATH), help="원천 CSV 경로")
    parser.add_argument("--schema", default=None, help="피처 스키마(SSoT) 경로 — 미지정 시 자동 탐색")
    parser.add_argument("--params", default=None, help="고정 파라미터 JSON(스키마 대신 사용)")
    parser.add_argument("--out-dir", default=None, help="ONNX 반출 폴더(기본 benchmarks/<실행일>/tuned_25d)")
    parser.add_argument("--export", action="store_true", help="ONNX 3종 + 25차원 스키마 반출")
    args = parser.parse_args()

    schema_path = resolve_schema_path(args.schema)
    schema = load_schema(args.schema)
    if schema_path is not None:
        print(f"[schema] {schema_path.as_posix()} | {len(schema_feature_cols(schema))}차원")
    verify_feature_schema(args.schema)  # 정규 하네스와 동일한 순서·타깃·분할 검증

    frozen = frozen_params(schema, Path(args.params) if args.params else None)
    for mode, params in frozen.items():
        print(f"[params] {mode:6s} {params}")

    df = load_and_engineer(Path(args.csv))
    results = train_25d(df, frozen, schema)

    export_dir = Path(args.out_dir) if args.out_dir else (
        BENCH_DIR / datetime.now().strftime("%Y-%m-%d") / "tuned_25d"
    )
    written = export_assets(results, export_dir, schema) if args.export else []

    try:
        csv_display = Path(args.csv).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        csv_display = args.csv
    meta = {
        "csv": csv_display,
        "legacy_indices": list(range(17)) + [21, 22, 23, 24, 25, 26, 30, 31],
        "params_source": str(schema_path or args.params),
        "schema_model_version": (schema or {}).get("model_version"),
        "export_dir": export_dir.relative_to(ROOT).as_posix() if written else None,
    }
    write_report(results, meta, export_dir if written else None, written)


if __name__ == "__main__":
    main()