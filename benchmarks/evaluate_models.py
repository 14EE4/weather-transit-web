# -*- coding: utf-8 -*-
"""
benchmarks/evaluate_models.py
================================================================================
**실제 32차원 피처** 기준 ONNX 모델 공정 비교 평가 스크립트 (v2).

v1 → v2 핵심 변경
  1. 원천 데이터   : data/2025_서울25개구_교통날씨_전처리_2.csv (209,875행 × 33열)
  2. 피처          : "25차원 + 상수 0 더미 7" 폐기 → **실제 32차원**
                     (공간 인프라 4 + same_day_last_week 3 을 실측값으로 채움)
  3. 분할          : 사양서 §6.1 Temporal Split (train ≤ 09-30 / valid ≤ 11-15 / test ≥ 11-16)
                     — 전처리 CSV `분할` 컬럼(valid 10-01~10-31 / test 11-01~)은 사용하지 않음
  4. is_holiday    : 2025 대한민국 실제 공휴일 캘린더(19일) 적용 — `is_weekend` 와 분리
  5. 단일 소스     : district_code / 인프라 4종 / 공휴일 캘린더를 `main.py` 에서 직접 import
                     → 학습↔서빙 피처 정의 드리프트 원천 차단
  6. 레거시 참고치 : 25차원 배포 모델은 학습 당시 분포(is_holiday 상수 0) 결과를 1행 더 병기

비교 대상 (기본값, `--model LABEL=PATH` 로 추가/덮어쓰기 가능)
    * production_25d : benchmarks/original/lgb_{mode}_demand.onnx   (배포본, 25차원)
    * tuned_32d_real : benchmarks/2026-10-14/lgb_{mode}_demand.onnx (v2 32차원 실피처 · 2026-10-14 학습/반입)
      → Colab(`benchmarks/CastTransit.ipynb` [Cell 7]) 산출 3종이 `benchmarks/2026-10-14/` 에 반입되어 있습니다.
      (구 배치 위치 `benchmarks/2026-10-12/tuned_real/` 은 안내 README 만 남은 종료 폴더)

  ⚠️ 이전 세대 `benchmarks/2026-10-12/tuned` 의 32차원 모델은 v1 배치
     (25차원 8/8/1/3/3/2 + 상수 0 더미 7)로 학습되어, v2 실피처 배치(8/8/5/11)와
     **컬럼 순서가 다릅니다.** 그대로 먹이면 인덱스 16 이후가 전부 어긋나므로
     기본 비교에서 제외했습니다(필요 시 `--model` 로 명시 평가하되 수치 해석 주의).

산출물: benchmarks/results/comparison_{timestamp}.json / .md
        (R² / RMSE / MAE / MAPE(실측 0 제외) / 단건 ONNX 추론 레이턴시(ms))

실행:
    python benchmarks/evaluate_models.py
    python benchmarks/evaluate_models.py --model tuned_32d_real=benchmarks/2026-10-14
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import onnxruntime as ort

# ------------------------------------------------------------------ 경로 정의
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 피처 정의의 유일한 소스 = 서빙 코드(main.py)
from main import DISTRICT_CODE_MAP, DISTRICT_INFRA, KR_HOLIDAYS  # noqa: E402

CSV_PATH = ROOT / "data" / "2025_서울25개구_교통날씨_전처리_2.csv"
BENCH_DIR = ROOT / "benchmarks"
RESULTS_DIR = BENCH_DIR / "results"

# 평가 대상(수단) -> CSV 타깃 컬럼 (ONNX 파일명 접두사와 동일)
TARGETS = {
    "bike": "따릉이_대여",
    "bus": "버스_승차",
    "subway": "지하철_승차",
}

# 래그/이동통계 계산용 (노트북 [Cell 4-B] LAG_TARGETS 와 키 이름까지 동일)
LAG_TARGETS = {
    "bike": "따릉이_대여",
    "bus": "버스_승차",
    "sub": "지하철_승차",
}

# same_day_last_week 접미사 (노트북 [Cell 4-B] 와 동일한 명명 규칙)
SAME_DAY_SUFFIX = {
    "따릉이_대여": "bike",
    "버스_승차": "bus",
    "지하철_승차": "sub",
}

# Temporal Split 경계 (docs/AI_MODEL_SPEC.md §6.1 · 공식)
TRAIN_END = "2025-09-30"
VAL_END = "2025-11-15"

# 32차원 피처 순서 (main.py::build_feature_vector 인덱스 0~31 과 완전 일치)
FEATURE_COLS_32 = [
    # [0..7] 시계열 및 캘린더 피처
    "month_sin", "month_cos", "hour_sin", "hour_cos",
    "dayofweek", "is_weekend", "is_holiday", "is_rush_hour",
    # [8..15] 기상 관측 및 파생 피처
    "temperature", "wind_speed", "humidity", "precipitation",
    "is_raining", "rain_intensity", "sensible_temp", "discomfort_index",
    # [16..20] 공간(위치) 인코딩 피처
    "district_code", "district_subway_stations", "district_bus_stops",
    "district_bike_racks", "commercial_density",
    # [21..31] 시계열 래그 및 이동통계 피처
    "따릉이_대여_lag_1h", "버스_승차_lag_1h", "지하철_승차_lag_1h",
    "따릉이_대여_roll_3h", "버스_승차_roll_3h", "지하철_승차_roll_3h",
    "same_day_last_week_bike", "same_day_last_week_bus", "same_day_last_week_sub",
    "temp_diff_1h", "rain_diff_1h",
]

# main.py::prepare_session_input 이 25차원 세션에 전달하는 인덱스와 동일한 서브셋
LEGACY_25D_INDICES = list(range(17)) + [21, 22, 23, 24, 25, 26, 30, 31]
FEATURE_COLS_25 = [FEATURE_COLS_32[i] for i in LEGACY_25D_INDICES]
IS_HOLIDAY_INDEX = FEATURE_COLS_32.index("is_holiday")

# 기본 모델 세트 (라벨 -> 폴더). CLI `--model LABEL=PATH` 로 덮어쓸 수 있다.
# 주의: 이전 세대 `2026-10-12/tuned` 는 v1 피처 배치(더미 7)로 학습되어 v2 배치와
#       컬럼 순서가 다르므로 기본 비교에서 제외한다(위 docstring 참조).
MODEL_SETS = {
    "production_25d": BENCH_DIR / "original",
    # 2026-10-14 Colab 학습 산출물(v2 실제 32차원 실피처, feature_schema.json 동봉)
    "tuned_32d_real": BENCH_DIR / "2026-10-14",
}

# 레이턴시 측정 반복 횟수(웜업 20회 제외)
LATENCY_ITERS = 200


# ------------------------------------------------------------ 피처 엔지니어링
def load_and_engineer(csv_path: Path) -> pd.DataFrame:
    """노트북 [Cell 3] 정제 + [Cell 4-A]·[Cell 4-B] 피처 엔지니어링을 재현한다.

    반환값은 실제 32차원 피처(더미 없음)가 모두 채워진 DataFrame 이며,
    컬럼 순서는 `main.py::build_feature_vector` 의 인덱스 0~31 과 일치한다.
    """
    df = pd.read_csv(csv_path)
    print(f"[load] 원천 데이터: {df.shape} | 파일: {csv_path.name}")

    # ---- [Cell 3] 결측치 도메인 정제 ----
    # 지하철 심야 운휴(01~05시)는 결측이 아니라 구조적 0
    df.loc[df["시간"].isin([1, 2, 3, 4, 5]), ["지하철_승차", "지하철_하차"]] = 0
    df["강수량(mm)"] = df["강수량(mm)"].fillna(0.0)
    for c in ["기온(°C)", "풍속(m/s)", "습도(%)"]:
        df[c] = df[c].interpolate(method="linear")
    df["버스_승차"] = df["버스_승차"].interpolate(method="linear").bfill().ffill()
    df["따릉이_대여"] = df["따릉이_대여"].fillna(0)

    # ---- 정렬 (래그·이동통계 산출의 전제) ----
    df["기준_날짜"] = pd.to_datetime(df["기준_날짜"])
    df["기준_일시"] = pd.to_datetime(df["기준_일시"])
    df = df.sort_values(["구", "기준_일시"]).reset_index(drop=True)

    # ---- 블록 1. 시계열 및 캘린더 피처 (8) ----
    df["month"] = df["기준_날짜"].dt.month
    df["dayofweek"] = df["기준_날짜"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    # is_holiday = 실제 대한민국 공휴일(주말과 별개 지표). main.py::KR_HOLIDAYS 단일 소스.
    holiday_dates = {pd.Timestamp(d) for days in KR_HOLIDAYS.values() for d in days}
    df["is_holiday"] = df["기준_날짜"].isin(holiday_dates).astype(int)
    df["is_rush_hour"] = df["시간"].isin([8, 9, 18, 19]).astype(int)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["hour_sin"] = np.sin(2 * np.pi * df["시간"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["시간"] / 24.0)

    # ---- 블록 2. 기상 관측 및 파생 피처 (8) ----
    df["temperature"] = df["기온(°C)"]
    df["wind_speed"] = df["풍속(m/s)"].clip(lower=0.1)   # 서빙: max(wind, 0.1)
    df["humidity"] = df["습도(%)"]
    df["precipitation"] = df["강수량(mm)"]
    df["is_raining"] = (df["precipitation"] > 0.0).astype(int)
    # 서빙과 동일한 경계: <=0 → 0, <3 → 1, <=10 → 2, 그 외 → 3
    df["rain_intensity"] = np.select(
        [df["precipitation"] <= 0.0, df["precipitation"] < 3.0, df["precipitation"] <= 10.0],
        [0, 1, 2], default=3,
    ).astype(int)
    _v = df["wind_speed"] ** 0.16
    df["sensible_temp"] = (
        13.12 + 0.6215 * df["temperature"] - 11.37 * _v
        + 0.3965 * df["temperature"] * _v
    )
    df["discomfort_index"] = (
        1.8 * df["temperature"] - 0.55 * (1 - df["humidity"] / 100.0)
        * (1.8 * df["temperature"] - 26.0) + 32.0
    )

    # ---- 블록 3. 공간(위치) 인코딩 피처 (5) — main.py 단일 소스 ----
    unknown = sorted(set(df["구"].unique()) - set(DISTRICT_CODE_MAP))
    assert not unknown, f"main.py::DISTRICT_CODE_MAP 에 없는 지역: {unknown}"
    df["district_code"] = df["구"].map(DISTRICT_CODE_MAP).astype(int)
    infra = (
        pd.DataFrame(DISTRICT_INFRA).T
        .rename(columns={
            "subway_stations": "district_subway_stations",
            "bus_stops": "district_bus_stops",
            "bike_racks": "district_bike_racks",
        })[["district_subway_stations", "district_bus_stops",
            "district_bike_racks", "commercial_density"]]
    )
    n_rows = len(df)
    df = df.merge(infra, left_on="구", right_index=True, how="left")
    assert len(df) == n_rows, "인프라 조인으로 행 수가 변했습니다."
    assert df["district_subway_stations"].notna().all(), "인프라 조인 누락(main.py::DISTRICT_INFRA 확인)"
    df = df.sort_values(["구", "기준_일시"]).reset_index(drop=True)

    # ---- 블록 4. 시계열 래그 및 이동통계 피처 (11) ----
    for col in LAG_TARGETS.values():
        df[f"{col}_lag_1h"] = df.groupby("구")[col].shift(1)
        df[f"{col}_roll_3h"] = df.groupby("구")[col].transform(
            lambda x: x.rolling(3, min_periods=1).mean()
        )
    # 구별 첫 관측치(01-01 01시)의 lag 결측 → 3시간 이동평균으로 보정
    for col in LAG_TARGETS.values():
        df[f"{col}_lag_1h"] = df[f"{col}_lag_1h"].fillna(df[f"{col}_roll_3h"])
    df["temp_diff_1h"] = df.groupby("구")["temperature"].diff().fillna(0.0)
    df["rain_diff_1h"] = df.groupby("구")["precipitation"].diff().fillna(0.0)

    # same_day_last_week: 하루 23개 시간대(01~23시)이므로 행 shift(168) 이 아니라
    #                     7일 전 타임스탬프 기준 self-merge 로 계산한다.
    prev = df[["구", "기준_일시"] + list(LAG_TARGETS.values())].copy()
    prev["기준_일시"] = prev["기준_일시"] + pd.Timedelta(days=7)
    prev = prev.rename(columns={
        "따릉이_대여": "same_day_last_week_bike",
        "버스_승차": "same_day_last_week_bus",
        "지하철_승차": "same_day_last_week_sub",
    })
    n_rows = len(df)
    df = df.merge(prev, on=["구", "기준_일시"], how="left")
    assert len(df) == n_rows, "same_day_last_week 조인으로 행 수가 변했습니다(키 중복 확인)."
    # 2025-01-01~01-07 구간은 7일 전 데이터가 없으므로 lag_1h 로 프록시 대체
    for col in LAG_TARGETS.values():
        dst = f"same_day_last_week_{SAME_DAY_SUFFIX[col]}"
        df[dst] = df[dst].fillna(df[f"{col}_lag_1h"]).fillna(0.0)

    # ---- 무결성 검증 ----
    assert len(FEATURE_COLS_32) == 32, f"32차원이 아닙니다: {len(FEATURE_COLS_32)}"
    assert len(FEATURE_COLS_25) == 25, f"25차원 서브셋이 아닙니다: {len(FEATURE_COLS_25)}"
    missing = df[FEATURE_COLS_32].isna().sum()
    assert int(missing.sum()) == 0, f"피처 결측 잔존:\n{missing[missing > 0]}"
    assert np.isfinite(df[FEATURE_COLS_32].to_numpy(dtype=np.float64)).all(), "피처에 inf/NaN 존재"
    print(
        f"[feat] 실제 32차원 확정 | 결측 0 | 공휴일 {int(df['is_holiday'].sum()):,}행 "
        f"({df['is_holiday'].mean() * 100:.2f}%) | 인프라 4종·same_day 3종 실측 조인 완료"
    )
    return df


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
    nz = y_true != 0  # MAPE 는 실측 0(심야 운휴 등) 제외
    mape = float(np.mean(np.abs(residual[nz] / y_true[nz])) * 100.0) if nz.any() else float("nan")
    return {"r2": r2, "rmse": rmse, "mae": mae, "mape_pct_nonzero": mape, "n": int(y_true.size)}


def onnx_input_dim(session: ort.InferenceSession) -> int:
    return int(session.get_inputs()[0].shape[1])


def measure_latency(session: ort.InferenceSession, x_row: np.ndarray, iters: int = LATENCY_ITERS) -> float:
    """단건(1행) 추론 평균 레이턴시(ms). 웜업 20회 후 iters 회 측정."""
    name = session.get_inputs()[0].name
    for _ in range(20):
        session.run(None, {name: x_row})
    t0 = time.perf_counter()
    for _ in range(iters):
        session.run(None, {name: x_row})
    t1 = time.perf_counter()
    return (t1 - t0) / iters * 1000.0


# ---------------------------------------------------------------- 결과 포매팅
def _md_table(results: dict) -> str:
    lines = [
        "| 모델 | 수단 | 입력차원 | R² | RMSE | MAE | MAPE(실측0제외) | 레이턴시(ms) | 파일(byte) |",
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


def _md_reference_section(results: dict) -> list[str]:
    """25차원 레거시 모델의 `is_holiday = 0` 참고치 섹션을 만든다.

    레거시 모델은 `is_holiday` 가 상수 0 인 데이터로 학습되었기 때문에 실제 공휴일을
    넣어도 예측이 바뀌지 않을 수 있다. 이 경우 표 대신 진단 한 줄만 남긴다.
    """
    rows, identical = [], []
    for label, blk in results["models"].items():
        for mode, m in blk["targets"].items():
            ref = m.get("reference_ih0")
            if not ref:
                continue
            same = abs(ref["r2"] - m["r2"]) < 5e-5 and abs(ref["rmse"] - m["rmse"]) < 5e-3
            if same:
                identical.append(f"{label}/{mode}")
            else:
                rows.append(
                    f"| {label} | {mode} | {ref['r2']:.4f} | {ref['rmse']:.3f} | "
                    f"{ref['mae']:.3f} | {ref['mape_pct_nonzero']:.2f}% |"
                )
    if not rows:
        if not identical:
            return []
        return [
            "## 25차원 레거시 모델 `is_holiday = 0` 참고치",
            "",
            f"- `{', '.join(identical)}`: 값 동일 — 레거시 모델은 `is_holiday` 가 상수 0 인 "
            "데이터로 학습되어 해당 피처를 전혀 사용하지 않습니다(주말 정보는 `is_weekend` 로 별도 존재).",
            "",
        ]
    return [
        "## 25차원 레거시 모델 `is_holiday = 0` 참고치 (학습 당시 분포)",
        "",
        "| 모델 | 수단 | R² | RMSE | MAE | MAPE(실측0제외) |",
        "| :--- | :---: | ---: | ---: | ---: | ---: |",
        *rows,
        "",
    ]


def parse_model_overrides(pairs: list[str]) -> dict[str, Path]:
    """`--model LABEL=PATH` 인자를 (라벨 -> 절대경로) 딕셔너리로 변환."""
    out: dict[str, Path] = {}
    for raw in pairs:
        label, sep, path = raw.partition("=")
        assert sep and path.strip(), f"--model 형식은 LABEL=PATH 입니다: {raw}"
        out[label.strip()] = (ROOT / path.strip()).resolve()
    return out


# ------------------------------------------------------------------- 엔트리
def main() -> None:
    parser = argparse.ArgumentParser(
        description="실제 32차원 피처 기준 ONNX 모델 공정 비교 평가 (v2)"
    )
    parser.add_argument("--csv", default=str(CSV_PATH), help="원천 CSV 경로")
    parser.add_argument(
        "--model", action="append", default=[], metavar="LABEL=PATH",
        help="평가할 모델 폴더를 라벨=경로로 추가/덮어쓰기 (반복 가능)",
    )
    args = parser.parse_args()

    model_sets = dict(MODEL_SETS)
    model_sets.update(parse_model_overrides(args.model))

    csv_path = Path(args.csv)
    try:  # 로그/산출물에는 가능한 한 레포 상대경로를 남긴다
        csv_display = str(csv_path.resolve().relative_to(ROOT))
    except ValueError:
        csv_display = str(csv_path)

    df = load_and_engineer(csv_path)

    # ---- 사양서 §6.1 Temporal Split ----
    train_mask = df["기준_날짜"] <= TRAIN_END
    val_mask = (df["기준_날짜"] > TRAIN_END) & (df["기준_날짜"] <= VAL_END)
    test_mask = df["기준_날짜"] > VAL_END
    test_dates = df.loc[test_mask, "기준_날짜"]
    print(
        f"[split] train={int(train_mask.sum()):,} val={int(val_mask.sum()):,} "
        f"test={int(test_mask.sum()):,} | test {test_dates.min().date()} ~ {test_dates.max().date()}"
    )

    # 두 모델군이 **동일한 피처 프레임**에서 만들어지므로 차이는 피처 구성뿐이다.
    X32 = df.loc[test_mask, FEATURE_COLS_32].astype(np.float32).to_numpy()
    X25 = df.loc[test_mask, FEATURE_COLS_25].astype(np.float32).to_numpy()
    # 레거시 25차원 모델은 학습 당시 is_holiday 가 상수 0 이었으므로,
    # 자기 학습 분포 기준 참고치를 위해 is_holiday 열만 0 으로 둔 변형을 준비한다.
    X25_ih0 = X25.copy()
    X25_ih0[:, IS_HOLIDAY_INDEX] = 0.0

    y_true = {mode: df.loc[test_mask, col].to_numpy() for mode, col in TARGETS.items()}

    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "csv": csv_display,
        "evaluator": "benchmarks/evaluate_models.py (v2 · 실제 32차원 실피처)",
        "feature_spec": {
            "version": "v2-32d-real (상수 0 더미 7 폐기)",
            "n_features": len(FEATURE_COLS_32),
            "feature_cols_32": FEATURE_COLS_32,
            "feature_cols_25_subset": FEATURE_COLS_25,
            "holiday_calendar": sorted({d for days in KR_HOLIDAYS.values() for d in days}),
            "source_of_truth": "main.py (DISTRICT_CODE_MAP / DISTRICT_INFRA / KR_HOLIDAYS)",
        },
        "split": {
            "source": "docs/AI_MODEL_SPEC.md §6.1 (spec_dates)",
            "train": f"2025-01-01 ~ {TRAIN_END}",
            "val": f"2025-10-01 ~ {VAL_END}",
            "test": "2025-11-16 ~ 2025-12-31",
        },
        "n_test": int(test_mask.sum()),
        "models": {},
    }

    for label, folder in model_sets.items():
        folder = Path(folder)
        block: dict = {"dir": str(folder), "targets": {}}
        results["models"][label] = block
        for mode in TARGETS:
            onnx_path = folder / f"lgb_{mode}_demand.onnx"
            if not onnx_path.exists():
                print(f"[skip] 파일 없음: {onnx_path}")
                continue
            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            dim = onnx_input_dim(sess)
            if dim == 32:
                X = X32
            elif dim == 25:
                X = X25
            else:
                print(f"[skip] 미지원 차원 {dim}: {onnx_path}")
                continue
            ins = sess.get_inputs()[0].name
            pred = np.clip(sess.run(None, {ins: X})[0].reshape(-1), 0.0, None)
            m = regression_metrics(y_true[mode], pred)
            m["input_dim"] = dim
            m["file_size_bytes"] = onnx_path.stat().st_size
            m["latency_ms_1row"] = round(measure_latency(sess, X[:1]), 4)
            if dim == 25:
                pred0 = np.clip(sess.run(None, {ins: X25_ih0})[0].reshape(-1), 0.0, None)
                m["reference_ih0"] = regression_metrics(y_true[mode], pred0)
            block["targets"][mode] = m
            print(
                f"[eval] {label:26s} {mode:6s} R2={m['r2']:.4f} RMSE={m['rmse']:8.3f} "
                f"MAE={m['mae']:7.3f} MAPE={m['mape_pct_nonzero']:6.2f}% dim={dim} "
                f"{m['latency_ms_1row']:.3f}ms"
            )

    # ---- 저장 ----
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"comparison_{stamp}.json"
    md_path = RESULTS_DIR / f"comparison_{stamp}.md"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# ONNX 모델 비교 분석 결과 (실제 32차원 피처 기준)",
        "",
        f"- 생성시각: {results['generated_at']}",
        f"- 평가 데이터: `{results['csv']}`",
        f"- Test 구간: {results['split']['test']} (n={results['n_test']:,}, source={results['split']['source']})",
        f"- 피처: {results['feature_spec']['version']} — 32차원 실피처(더미 0 없음), 공휴일 캘린더 19일 적용",
        "- MAPE 는 실측 0(심야 운휴 등) 제외.",
        "",
        _md_table(results),
        "",
    ]
    md += _md_reference_section(results)
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"\n[저장] {json_path.relative_to(ROOT)}")
    print(f"[저장] {md_path.relative_to(ROOT)}")
    print("\n" + _md_table(results))


if __name__ == "__main__":
    main()