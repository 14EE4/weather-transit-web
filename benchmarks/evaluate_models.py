# -*- coding: utf-8 -*-
"""
benchmarks/evaluate_models.py
================================================================================
기존에 존재하는 ONNX 모델만으로 공정 비교 분석을 수행하는 독립 평가 스크립트.

- 데이터 전처리/피처 엔지니어링은 `benchmarks/CastTransit.ipynb` [Cell 3]~[Cell 5]를
  그대로 재현합니다(Data Leakage 차단을 위한 Temporal Split 포함).
- 비교 대상:
    * baseline(25차원, 배포본) : benchmarks/original/lgb_{mode}_demand.onnx
    * candidate(32차원, 튜닝본): benchmarks/2026-10-12/tuned/lgb_{mode}_demand.onnx
- 각 모델은 자신이 기대하는 입력 차원(25 or 32)에 맞는 테스트 피처 행렬로 추론합니다.
    * 25차원 = FEATURE_COLS (노트북 [Cell 5])
    * 32차원 = FEATURE_COLS + infra_dummy_0..6 (노트북 [Cell 7-1] 방식, 상수 0)
- 산출: R2 / RMSE / MAE / MAPE(실측 0 제외) + ONNX 단건 추론 레이턴시(ms)
- 결과: benchmarks/results/ 하위에 JSON + Markdown 로 저장.

실행:  python benchmarks/evaluate_models.py
================================================================================
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import onnxruntime as ort

# ------------------------------------------------------------------ 경로 정의
ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "2025_서울25개구_시간대별_교통_날씨_통합_01-23시.csv"
BENCH_DIR = ROOT / "benchmarks"
RESULTS_DIR = BENCH_DIR / "results"

# 비교할 모델 세트 (라벨 -> 폴더)
MODEL_SETS = {
    "baseline_25d_production": BENCH_DIR / "original",
    "candidate_32d_tuned": BENCH_DIR / "2026-10-12" / "tuned",
}

# 타깃(수단) -> CSV 타깃 컬럼
TARGETS = {
    "bike": "따릉이_대여",
    "bus": "버스_승차",
    "subway": "지하철_승차",
}

# 노트북 [Cell 5] FEATURE_COLS (25차원)
FEATURE_COLS = [
    "month_sin", "month_cos", "hour_sin", "hour_cos", "dayofweek", "is_weekend", "is_holiday", "is_rush_hour",
    "기온(°C)", "풍속(m/s)", "습도(%)", "강수량(mm)", "is_raining", "rain_intensity", "sensible_temp", "discomfort_index",
    "district_code",
    "따릉이_대여_lag_1h", "버스_승차_lag_1h", "지하철_승차_lag_1h",
    "따릉이_대여_roll_3h", "버스_승차_roll_3h", "지하철_승차_roll_3h",
    "temp_diff_1h", "rain_diff_1h",
]

# Temporal Split 경계 (docs/AI_INFERENCE_MODEL_SPEC.md §6.2)
TRAIN_END = "2025-09-30"
VAL_END = "2025-11-15"

# 레이턴시 측정 반복 횟수(웜업 제외)
LATENCY_ITERS = 200


def load_and_engineer() -> tuple[pd.DataFrame, list[str]]:
    """노트북 [Cell 3] 전처리 + [Cell 4] 피처 엔지니어링을 재현하고 df와 32차원 컬럼목록을 반환."""
    df = pd.read_csv(CSV_PATH)
    print(f"[load] 원천 데이터: {df.shape}")

    # ---- [Cell 3] 정제 ----
    df.loc[df["시간"].isin([1, 2, 3, 4, 5]), ["지하철_승차", "지하철_하차"]] = 0
    df["강수량(mm)"] = df["강수량(mm)"].fillna(0.0)
    df["기온(°C)"] = df["기온(°C)"].interpolate(method="linear")
    df["풍속(m/s)"] = df["풍속(m/s)"].interpolate(method="linear")
    df["습도(%)"] = df["습도(%)"].interpolate(method="linear")
    df["버스_승차"] = df["버스_승차"].interpolate(method="linear").bfill().ffill()
    df["따릉이_대여"] = df["따릉이_대여"].fillna(0)

    # ---- [Cell 4] 파생 변수 ----
    df["기준_날짜"] = pd.to_datetime(df["기준_날짜"])
    df["month"] = df["기준_날짜"].dt.month
    df["dayofweek"] = df["기준_날짜"].dt.dayofweek
    df["is_weekend"] = df["dayofweek"].apply(lambda x: 1 if x in [5, 6] else 0)
    df["is_rush_hour"] = df["시간"].apply(lambda x: 1 if x in [8, 9, 18, 19] else 0)

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["hour_sin"] = np.sin(2 * np.pi * df["시간"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["시간"] / 24.0)
    df["is_holiday"] = 0

    df["is_raining"] = (df["강수량(mm)"] > 0).astype(int)
    df["rain_intensity"] = pd.cut(
        df["강수량(mm)"], bins=[-np.inf, 0, 3, 10, np.inf], labels=[0, 1, 2, 3]
    ).astype(int)
    df["sensible_temp"] = (
        13.12 + 0.6215 * df["기온(°C)"] - 11.37 * (df["풍속(m/s)"] ** 0.16)
        + 0.3965 * df["기온(°C)"] * (df["풍속(m/s)"] ** 0.16)
    )
    df["discomfort_index"] = (
        1.8 * df["기온(°C)"] - 0.55 * (1 - df["습도(%)"] / 100.0)
        * (1.8 * df["기온(°C)"] - 26) + 32
    )

    districts = sorted(df["구"].unique())
    district_map = {name: idx for idx, name in enumerate(districts)}
    df["district_code"] = df["구"].map(district_map)

    df = df.sort_values(by=["구", "기준_날짜", "시간"]).reset_index(drop=True)
    for col in ["따릉이_대여", "버스_승차", "지하철_승차"]:
        df[f"{col}_lag_1h"] = df.groupby("구")[col].shift(1).bfill()
        df[f"{col}_roll_3h"] = df.groupby("구")[col].transform(
            lambda x: x.rolling(3, min_periods=1).mean()
        )
    df["temp_diff_1h"] = df.groupby("구")["기온(°C)"].diff().fillna(0)
    df["rain_diff_1h"] = df.groupby("구")["강수량(mm)"].diff().fillna(0)

    # ---- [Cell 7-1] 방식의 32차원 구성 (25 + 상수 0 더미 7) ----
    num_dummies = 32 - len(FEATURE_COLS)
    dummy_cols = [f"infra_dummy_{i}" for i in range(num_dummies)]
    for col in dummy_cols:
        df[col] = 0.0
    final_feature_cols = FEATURE_COLS + dummy_cols

    print(f"[feat] 피처 엔지니어링 완료 | 25차원={len(FEATURE_COLS)} | 32차원={len(final_feature_cols)}")
    return df, final_feature_cols


# ------------------------------------------------------------------ 지표 계산
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """R2 / RMSE / MAE / MAPE(실측 0 제외) 계산."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    residual = y_true - y_pred
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    nz = y_true != 0  # MAPE 는 실측 0 을 제외(0 나눗셈 왜곡 방지)
    mape = float(np.mean(np.abs(residual[nz] / y_true[nz])) * 100.0) if nz.any() else float("nan")
    return {"r2": r2, "rmse": rmse, "mae": mae, "mape_pct_nonzero": mape, "n": int(y_true.size)}


def onnx_input_dim(session: ort.InferenceSession) -> int:
    return int(session.get_inputs()[0].shape[1])


def measure_latency(session: ort.InferenceSession, x_row: np.ndarray, iters: int = LATENCY_ITERS) -> float:
    """단건(1행) 추론 평균 레이턴시(ms). 워밍업 20회 후 iters 회 측정."""
    name = session.get_inputs()[0].name
    for _ in range(20):
        session.run(None, {name: x_row})
    t0 = time.perf_counter()
    for _ in range(iters):
        session.run(None, {name: x_row})
    t1 = time.perf_counter()
    return (t1 - t0) / iters * 1000.0


def _md_table(results: dict) -> str:
    lines = [
        "| 모델 | 수단 | 입력차원 | R² | RMSE | MAE | MAPE(≠0) | 레이턴시(ms) | 파일(byte) |",
        "| :--- | :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, blk in results["models"].items():
        for mode, m in blk["targets"].items():
            lines.append(
                f"| {label} | {mode} | {m['input_dim']} | {m['r2']:.4f} | {m['rmse']:.3f} | "
                f"{m['mae']:.3f} | {m['mape_pct_nonzero']:.2f}% | {m['latency_ms_1row']:.3f} | "
                f"{m['file_size_bytes']} |"
            )
    return "\n".join(lines)


def main() -> None:
    df, final_feature_cols = load_and_engineer()

    train_mask = df["기준_날짜"] <= TRAIN_END
    val_mask = (df["기준_날짜"] > TRAIN_END) & (df["기준_날짜"] <= VAL_END)
    test_mask = df["기준_날짜"] > VAL_END

    X25 = df.loc[test_mask, FEATURE_COLS].astype(np.float32).values
    X32 = df.loc[test_mask, final_feature_cols].astype(np.float32).values
    print(f"[split] train={int(train_mask.sum())} val={int(val_mask.sum())} test={int(test_mask.sum())}")

    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "csv": str(CSV_PATH.relative_to(ROOT)),
        "split": {
            "train": "2025-01-01 ~ 2025-09-30",
            "val": "2025-10-01 ~ 2025-11-15",
            "test": "2025-11-16 ~ 2025-12-31",
        },
        "n_test": int(test_mask.sum()),
        "note": "MAPE 는 실측 0(심야 운휴 등) 제외. 32차원 모델은 노트북 [Cell 7-1] 방식(25 + 상수0 더미7).",
        "models": {},
    }

    for label, folder in MODEL_SETS.items():
        results["models"][label] = {"dir": str(folder.relative_to(ROOT)), "targets": {}}
        for mode, target_col in TARGETS.items():
            onnx_path = folder / f"lgb_{mode}_demand.onnx"
            if not onnx_path.exists():
                print(f"[skip] 파일 없음: {onnx_path}")
                continue
            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            dim = onnx_input_dim(sess)
            if dim == 25:
                X = X25
            elif dim == 32:
                X = X32
            else:
                print(f"[skip] 미지원 차원 {dim}: {onnx_path}")
                continue
            ins = sess.get_inputs()[0].name
            pred = np.clip(sess.run(None, {ins: X})[0].reshape(-1), 0.0, None)
            y = df.loc[test_mask, target_col].to_numpy()
            m = regression_metrics(y, pred)
            m["input_dim"] = dim
            m["file_size_bytes"] = onnx_path.stat().st_size
            m["latency_ms_1row"] = round(measure_latency(sess, X[:1]), 4)
            results["models"][label]["targets"][mode] = m
            print(
                f"[eval] {label:26s} {mode:6s} R2={m['r2']:.4f} RMSE={m['rmse']:8.3f} "
                f"MAE={m['mae']:7.3f} MAPE={m['mape_pct_nonzero']:6.2f}% dim={dim} {m['latency_ms_1row']:.3f}ms"
            )

    # ---- 저장 ----
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"comparison_{stamp}.json"
    md_path = RESULTS_DIR / f"comparison_{stamp}.md"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# ONNX 모델 비교 분석 결과",
        "",
        f"- 생성시각: {results['generated_at']}",
        f"- 평가 데이터: `{results['csv']}`",
        f"- Test 구간: {results['split']['test']} (n={results['n_test']:,})",
        "- MAPE 는 실측 0 제외. 32차원 모델은 노트북 [Cell 7-1] 방식(25 + 상수0 더미7).",
        "",
        _md_table(results),
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"\n[저장] {json_path.relative_to(ROOT)}")
    print(f"[저장] {md_path.relative_to(ROOT)}")
    print("\n" + _md_table(results))


if __name__ == "__main__":
    main()