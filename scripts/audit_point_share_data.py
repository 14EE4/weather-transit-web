#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 0 — 지점 점유율 데이터셋 감사 (이슈 #116, docs/MODEL_RETRAINING_PLAN.md)

`data/통합데이터/{23,24,25}_통합데이터/정류장_대여소_역_별_퍼센트데이터/` 의 75개 CSV(약 18.7GB)를
청크 단위로 스캔해 학습 설계에 필요한 사실만 수치로 확정한다.

확인 항목
  A. 내부 정합: 점유율 그룹 합계≈100, 시간대총이용량==이용량 합, 연간 점유율 합계≈100
  B. 검증 보고서 JSON 과의 재집계 대조 (관측일수·매핑성공 이용량)
  C. 연도 간 지점ID 연속성 및 2025 이용량의 학습구간 커버리지 (콜드스타트 비중)
  D. 라벨 정합: 지점 합계 vs 기존 자치구 단위 통합데이터 라벨 (R7)
  E. 집중도(상위 K 지점 누적 비중) 및 밀집화 규모 추정

산출물: benchmarks/results/point_share_audit_<timestamp>.{json,md}
실행:   python scripts/audit_point_share_data.py [--years 2025] [--limit-files 1]
의존성: pandas, numpy 만 사용 (운영 requirements.txt 변경 없음)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "통합데이터")
POINT_SUBDIR = "정류장_대여소_역_별_퍼센트데이터"
YEAR_DIRS = {2023: "23_통합데이터", 2024: "24_통합데이터", 2025: "25_통합데이터"}

# 현행 모델 분할(feature_schema.json::split)과 동일한 학습 구간 종료일
TRAIN_END = "2024-09-30"

MODES = ["따릉이", "버스", "지하철"]
LABEL_COL = {"따릉이": "따릉이_대여", "버스": "버스_승차", "지하철": "지하철_승차"}

USECOLS = [
    "기준_날짜", "시간", "행정구", "교통수단", "지점ID", "이용량",
    "행정구_시간대총이용량", "시간대_점유율(%)",
    "행정구_연간총이용량", "지점_연간총이용량", "연간_점유율(%)",
]
HOUR_KEYS = ["기준_날짜", "시간", "행정구", "교통수단"]
DUP_KEYS = HOUR_KEYS + ["지점ID"]


def rel(path: str) -> str:
    """저장소 밖(다른 드라이브 포함) 경로도 안전하게 표시."""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def to_native(obj):
    """numpy/pandas 스칼라를 JSON 직렬화 가능 형태로 변환."""
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


# ─────────────────────────────────────────────────────────────
# 1. 스캔 (파일 → 청크 → 부분 집계)
# ─────────────────────────────────────────────────────────────
def scan_file(path: str, chunksize: int):
    """한 개 CSV를 스캔해 (시간대 그룹 집계, 지점 집계, 품질 카운터)를 반환."""
    hourly_parts, point_parts = [], []
    quality = {"rows": 0, "dup_chunk_local": 0, "nonpositive_usage": 0, "null_usage": 0}

    reader = pd.read_csv(
        path, usecols=USECOLS, dtype={"지점ID": str}, encoding="utf-8", chunksize=chunksize
    )
    for chunk in reader:
        quality["rows"] += len(chunk)
        quality["dup_chunk_local"] += int(chunk.duplicated(DUP_KEYS).sum())
        quality["nonpositive_usage"] += int((chunk["이용량"] <= 0).sum())
        quality["null_usage"] += int(chunk["이용량"].isna().sum())

        hourly_parts.append(
            chunk.groupby(HOUR_KEYS, sort=False)
            .agg(
                usage=("이용량", "sum"),
                share=("시간대_점유율(%)", "sum"),
                n=("이용량", "size"),
                tot_max=("행정구_시간대총이용량", "max"),
                tot_min=("행정구_시간대총이용량", "min"),
            )
            .reset_index()
        )

        chunk = chunk.assign(tw=np.where(chunk["기준_날짜"] <= TRAIN_END, chunk["이용량"], 0))
        point_parts.append(
            chunk.groupby(["행정구", "교통수단", "지점ID"], sort=False)
            .agg(
                usage=("이용량", "sum"),
                tw=("tw", "sum"),
                n=("이용량", "size"),
                ann_share=("연간_점유율(%)", "first"),
                ann_total=("지점_연간총이용량", "first"),
                dist_ann_total=("행정구_연간총이용량", "first"),
            )
            .reset_index()
        )

    hourly = (
        pd.concat(hourly_parts, ignore_index=True)
        .groupby(HOUR_KEYS, sort=False)
        .agg(usage=("usage", "sum"), share=("share", "sum"), n=("n", "sum"),
             tot_max=("tot_max", "max"), tot_min=("tot_min", "min"))
        .reset_index()
    )
    points = (
        pd.concat(point_parts, ignore_index=True)
        .groupby(["행정구", "교통수단", "지점ID"], sort=False)
        .agg(usage=("usage", "sum"), tw=("tw", "sum"), n=("n", "sum"),
             ann_share=("ann_share", "first"), ann_total=("ann_total", "first"),
             dist_ann_total=("dist_ann_total", "first"))
        .reset_index()
    )
    return hourly, points, quality


def scan_year(year: int, chunksize: int, limit_files: int | None):
    folder = os.path.join(DATA_DIR, YEAR_DIRS[year], POINT_SUBDIR)
    files = sorted(glob.glob(os.path.join(folder, f"{year}_*.csv")))
    if limit_files:
        files = files[:limit_files]
    if not files:
        raise SystemExit(f"[{year}] CSV 파일을 찾지 못했습니다: {folder}")

    hourly_all, points_all = [], []
    quality = {"files": len(files), "rows": 0, "dup_chunk_local": 0,
               "nonpositive_usage": 0, "null_usage": 0}
    t0 = time.time()
    for i, f in enumerate(files, 1):
        h, p, q = scan_file(f, chunksize)
        hourly_all.append(h)
        points_all.append(p)
        for k in ("rows", "dup_chunk_local", "nonpositive_usage", "null_usage"):
            quality[k] += q[k]
        log(f"  [{year}] {i:>2}/{len(files)} {os.path.basename(f)} rows={q['rows']:,} "
            f"(누적 {time.time() - t0:,.0f}s)")
    return pd.concat(hourly_all, ignore_index=True), pd.concat(points_all, ignore_index=True), quality


# ─────────────────────────────────────────────────────────────
# 2. 분석
# ─────────────────────────────────────────────────────────────
def analyze_internal(hourly: pd.DataFrame, points: pd.DataFrame) -> dict:
    """A. 내부 정합 + 관측일/시간 범위."""
    out = {}
    for mode in MODES:
        h = hourly[hourly["교통수단"] == mode]
        p = points[points["교통수단"] == mode]
        if h.empty:
            continue
        dev = (h["share"] - 100.0).abs()
        tot_const = int((h["tot_max"] != h["tot_min"]).sum())
        tot_vs_sum = (h["tot_max"] - h["usage"]).abs()
        by_dm = p.groupby("행정구").agg(
            ann_share_sum=("ann_share", "sum"),
            usage_sum=("usage", "sum"),
            dist_ann_total=("dist_ann_total", "first"),
        )
        out[mode] = {
            "rows": int(h["n"].sum()),
            "volume": float(h["usage"].sum()),
            "observed_dates": int(h["기준_날짜"].nunique()),
            "hours": sorted(int(x) for x in h["시간"].unique()),
            "points": int(p["지점ID"].nunique()),
            "multi_district_points": int((p.groupby("지점ID")["행정구"].nunique() > 1).sum()),
            "hour_groups": int(len(h)),
            "share_sum_abs_dev_max": float(dev.max()),
            "share_sum_abs_dev_p99": float(dev.quantile(0.99)),
            "share_groups_dev_gt_0.01": int((dev > 0.01).sum()),
            "tot_not_constant_groups": tot_const,
            "tot_vs_usage_sum_max_abs_diff": float(tot_vs_sum.max()),
            "tot_vs_usage_sum_groups_diff_gt_0": int((tot_vs_sum > 0).sum()),
            "annual_share_sum_min": float(by_dm["ann_share_sum"].min()),
            "annual_share_sum_max": float(by_dm["ann_share_sum"].max()),
            "annual_total_vs_usage_max_abs_diff": float((by_dm["usage_sum"] - by_dm["dist_ann_total"]).abs().max()),
        }
    return out


def compare_report(year: int, internal: dict, partial: bool = False) -> dict:
    """B. 검증 보고서 JSON 과의 대조 (연도별 스키마 차이 흡수).

    partial=True(표본 모드)이면 일부 자치구만 읽은 것이므로 이용량 총합 비교는 생략한다.
    """
    folder = os.path.join(DATA_DIR, YEAR_DIRS[year], POINT_SUBDIR)
    report_path = None
    for pat in ("**/*validation_report.json", "**/*검증_보고서.json", "**/*데이터_검증_보고서.json"):
        found = glob.glob(os.path.join(folder, pat), recursive=True)
        if found:
            report_path = found[0]
            break
    if not report_path:
        return {"available": False}

    with open(report_path, encoding="utf-8") as f:
        rep = json.load(f)

    out = {"available": True, "file": rel(report_path), "modes": {}}
    if "교통수단별" in rep:  # 2025 스타일
        for item in rep["교통수단별"]:
            mode = item["교통수단"]
            out["modes"][mode] = {
                "report_observed_days": item.get("날짜_관측일수"),
                "report_missing_days": item.get("미관측_날짜", []),
                "report_mapped_volume": item.get("서울25구_매핑성공이용량"),
            }
    else:  # 2023/2024 스타일
        cov = rep.get("date_coverage", {})
        totals = rep.get("annual_district_mode_total", {})
        for mode in MODES:
            mapped = sum(v.get(mode, 0) for v in totals.values()) if totals else None
            out["modes"][mode] = {
                "report_observed_days": cov.get(mode, {}).get("days"),
                "report_missing_days": cov.get(mode, {}).get("missing_days", []),
                "report_mapped_volume": mapped,
            }
    for mode, r in out["modes"].items():
        mine = internal.get(mode)
        if not mine:
            continue
        r["recount_observed_days"] = mine["observed_dates"]
        r["recount_volume"] = mine["volume"]
        r["observed_days_match"] = (r["report_observed_days"] == mine["observed_dates"])
        if r["report_mapped_volume"] and not partial:
            r["volume_rel_diff"] = float(abs(mine["volume"] - r["report_mapped_volume"]) / r["report_mapped_volume"])
    return out


def analyze_concentration(points: pd.DataFrame, observed_dates: dict) -> dict:
    """E. 자치구·수단별 집중도 및 상위 K 밀집화 규모 추정 (1개 연도 기준)."""
    out = {}
    for mode in MODES:
        p = points[points["교통수단"] == mode]
        if p.empty:
            continue
        k90, k95, top1, top10, top50, npts = [], [], [], [], [], []
        for _, g in p.groupby("행정구"):
            u = np.sort(g["usage"].to_numpy(dtype=float))[::-1]
            tot = u.sum()
            if tot <= 0:
                continue
            cum = np.cumsum(u) / tot
            k90.append(int(np.searchsorted(cum, 0.90) + 1))
            k95.append(int(np.searchsorted(cum, 0.95) + 1))
            top1.append(float(cum[0]))
            top10.append(float(cum[min(9, len(cum) - 1)]))
            top50.append(float(cum[min(49, len(cum) - 1)]))
            npts.append(len(u))
        hours = 18 if mode == "지하철" else 23
        days = observed_dates.get(mode, 365)
        out[mode] = {
            "districts": len(k90),
            "points_total": int(sum(npts)),
            "points_per_district_median": float(np.median(npts)),
            "k90_median": float(np.median(k90)), "k90_max": int(max(k90)), "k90_sum": int(sum(k90)),
            "k95_median": float(np.median(k95)), "k95_max": int(max(k95)), "k95_sum": int(sum(k95)),
            "top1_cum_median": float(np.median(top1)),
            "top10_cum_median": float(np.median(top10)),
            "top50_cum_median": float(np.median(top50)),
            "dense_rows_per_year_k90": int(sum(k90)) * days * hours,
            "dense_rows_per_year_k95": int(sum(k95)) * days * hours,
            "dense_rows_per_year_all": int(sum(npts)) * days * hours,
        }
    return out


def analyze_id_continuity(per_year_points: dict) -> dict:
    """C. 연도 간 지점ID 연속성과 2025 이용량의 학습구간 커버리지(콜드스타트 비중)."""
    out = {}
    years = sorted(per_year_points)
    for mode in MODES:
        sets = {
            y: set(per_year_points[y].loc[per_year_points[y]["교통수단"] == mode, "지점ID"])
            for y in years
        }
        res = {"points": {y: len(s) for y, s in sets.items()}, "jaccard": {}}
        for a, b in zip(years, years[1:]):
            union = sets[a] | sets[b]
            res["jaccard"][f"{a}-{b}"] = float(len(sets[a] & sets[b]) / len(union)) if union else None

        train_ids = set()
        for y in years:
            if y <= 2024:
                p = per_year_points[y]
                train_ids |= set(p[(p["교통수단"] == mode) & (p["tw"] > 0)]["지점ID"])
        res["train_window_points"] = len(train_ids)

        if 2025 in per_year_points:
            p25 = per_year_points[2025]
            p25 = p25[p25["교통수단"] == mode]
            total = float(p25["usage"].sum())
            seen = p25[p25["지점ID"].isin(train_ids)]
            res["test2025_points"] = int(p25["지점ID"].nunique())
            res["test2025_points_unseen_in_train"] = int((~p25["지점ID"].isin(train_ids)).sum())
            res["test2025_volume_coverage_by_train_points"] = float(seen["usage"].sum() / total) if total else None
        out[mode] = res
    return out


def analyze_label_alignment(year: int, hourly: pd.DataFrame) -> dict:
    """D. 지점 합계 vs 기존 자치구 단위 통합데이터 라벨 (시간 단위).

    표본 모드(--limit-files)에서도 의미가 유지되도록 점 데이터에 존재하는 자치구만 비교한다.
    라벨>0 이지만 지점 행이 없는 셀은 두 부류로 분리한다.
      - 미관측일(해당 수단 원천에 날짜 자체가 없음) → 기존 라벨이 보간/대체한 셀 (R4)
      - 관측일인데 행 없음 → 실제 무이용(0)이거나 매핑 누락
    """
    files = sorted(glob.glob(os.path.join(DATA_DIR, YEAR_DIRS[year], "*통합데이터_*.csv")))
    if not files:
        return {"available": False}
    lab = pd.concat(
        [pd.read_csv(f, usecols=["기준_날짜", "시간", "구", "따릉이_대여", "버스_승차", "지하철_승차"], encoding="utf-8")
         for f in files],
        ignore_index=True,
    ).rename(columns={"구": "행정구"})
    lab = lab[lab["행정구"].isin(set(hourly["행정구"].unique()))]
    out = {"available": True, "label_files": [os.path.basename(f) for f in files], "modes": {}}
    for mode in MODES:
        h = hourly[hourly["교통수단"] == mode][["기준_날짜", "시간", "행정구", "usage"]]
        col = LABEL_COL[mode]
        merged = h.merge(lab[["기준_날짜", "시간", "행정구", col]], on=["기준_날짜", "시간", "행정구"], how="inner")
        merged = merged.dropna(subset=[col])
        merged = merged[merged[col] > 0]
        if merged.empty:
            out["modes"][mode] = {"matched_cells": 0}
            continue
        a = merged["usage"].to_numpy(dtype=float)
        b = merged[col].to_numpy(dtype=float)
        ratio = a / b
        rel = np.abs(a - b) / b

        lab_pos = lab[lab[col] > 0][["기준_날짜", "시간", "행정구"]]
        joined = lab_pos.merge(h[["기준_날짜", "시간", "행정구"]].drop_duplicates(), how="left", indicator=True)
        left_only = joined[joined["_merge"] == "left_only"]
        observed_dates = set(h["기준_날짜"].unique())
        on_unobserved = int((~left_only["기준_날짜"].isin(observed_dates)).sum())

        out["modes"][mode] = {
            "matched_cells": int(len(merged)),
            "label_positive_cells_on_unobserved_dates": on_unobserved,
            "label_positive_cells_observed_date_without_rows": int(len(left_only)) - on_unobserved,
            "pearson_r": float(np.corrcoef(a, b)[0, 1]),
            "sum_ratio_point_over_label": float(a.sum() / b.sum()),
            "median_ratio": float(np.median(ratio)),
            "median_abs_rel_diff": float(np.median(rel)),
            "p90_abs_rel_diff": float(np.quantile(rel, 0.90)),
            "share_cells_within_5pct": float((rel <= 0.05).mean()),
            "share_cells_exact": float((rel == 0).mean()),
        }
    return out


# ─────────────────────────────────────────────────────────────
# 3. 판정 및 리포트
# ─────────────────────────────────────────────────────────────
def verdict_g0(result: dict) -> dict:
    """게이트 G0 (초기 기준). 기준 자체도 이번 실측 후 재확정한다."""
    v = {"criteria": {
        "label_pearson_r_min": 0.98, "label_sum_ratio_range": [0.90, 1.10],
        "train_coverage_min": 0.95, "share_dev_p99_max": 0.01}, "items": []}
    for mode in MODES:
        for year, yr in result["years"].items():
            la = (yr.get("label_alignment") or {}).get("modes", {}).get(mode)
            if la and la.get("matched_cells"):
                ok = la["pearson_r"] >= 0.98 and 0.90 <= la["sum_ratio_point_over_label"] <= 1.10
                v["items"].append({"check": "label_alignment", "year": year, "mode": mode,
                                   "pearson_r": la["pearson_r"],
                                   "sum_ratio": la["sum_ratio_point_over_label"],
                                   "status": "PASS" if ok else "WARN"})
        cont = (result.get("id_continuity") or {}).get(mode, {})
        cov = cont.get("test2025_volume_coverage_by_train_points")
        if cov is not None:
            v["items"].append({"check": "train_coverage_2025", "mode": mode, "coverage": cov,
                               "status": "PASS" if cov >= 0.95 else "WARN"})
    for year, yr in result["years"].items():
        for mode, m in yr["internal"].items():
            v["items"].append({"check": "share_sum_p99_dev", "year": year, "mode": mode,
                               "p99_dev": m["share_sum_abs_dev_p99"],
                               "status": "PASS" if m["share_sum_abs_dev_p99"] <= 0.01 else "WARN"})
    statuses = {i["status"] for i in v["items"]}
    v["overall"] = "PASS" if statuses == {"PASS"} else "REVIEW"
    if result.get("limit_files"):
        # 표본 모드는 일부 자치구만 읽은 결과이므로 게이트 판정 근거가 될 수 없다.
        v["overall"] = "SAMPLE_ONLY(판정 불가)"
    return v


def render_markdown(result: dict) -> str:
    L = [f"# 📊 지점 점유율 데이터 감사 리포트 (Phase 0 · 이슈 #116)",
         "",
         f"- 생성: `{result['generated_at']}`  ",
         f"- 범위: 연도 `{', '.join(result['years'])}` · 파일 {sum(y['quality']['files'] for y in result['years'].values())}개 · "
         f"행 {sum(y['quality']['rows'] for y in result['years'].values()):,}  ",
         f"- 소요: `{result['elapsed_sec']:.0f}s`  ",
         f"- **G0 종합 판정: `{result['g0']['overall']}`**", ""]

    L += ["## 1. 품질 카운터", "", "| 연도 | 파일 | 행수 | 청크내 중복 | 이용량≤0 | 이용량 NULL |", "| :-: | :-: | -: | -: | -: | -: |"]
    for y, yr in result["years"].items():
        q = yr["quality"]
        L.append(f"| {y} | {q['files']} | {q['rows']:,} | {q['dup_chunk_local']:,} | {q['nonpositive_usage']:,} | {q['null_usage']:,} |")

    L += ["", "## 2. 내부 정합 · 관측 범위", "",
          "| 연도 | 수단 | 행수 | 지점수 | 관측일 | 시간대 | 점유율합 편차 p99 | 총이용량≠합 그룹 | 연간점유율합 범위 |",
          "| :-: | :-: | -: | -: | -: | :-: | -: | -: | :-: |"]
    for y, yr in result["years"].items():
        for mode, m in yr["internal"].items():
            hrs = f"{m['hours'][0]}~{m['hours'][-1]}"
            L.append(f"| {y} | {mode} | {m['rows']:,} | {m['points']:,} | {m['observed_dates']} | `{hrs}` | "
                     f"{m['share_sum_abs_dev_p99']:.6f} | {m['tot_vs_usage_sum_groups_diff_gt_0']:,} | "
                     f"`{m['annual_share_sum_min']:.2f}~{m['annual_share_sum_max']:.2f}` |")

    L += ["", "## 3. 검증 보고서 재집계 대조", "",
          "| 연도 | 수단 | 보고서 관측일 | 재집계 관측일 | 일치 | 이용량 상대오차 |", "| :-: | :-: | -: | -: | :-: | -: |"]
    for y, yr in result["years"].items():
        rc = yr.get("report_check", {})
        for mode, r in rc.get("modes", {}).items():
            diff = r.get("volume_rel_diff")
            L.append(f"| {y} | {mode} | {r.get('report_observed_days')} | {r.get('recount_observed_days')} | "
                     f"{'✅' if r.get('observed_days_match') else '⚠️'} | {('%.4f%%' % (diff * 100)) if diff is not None else '-'} |")

    L += ["", "## 4. 연도 간 지점ID 연속성 (R6)", "",
          "| 수단 | 2023 지점 | 2024 지점 | 2025 지점 | Jaccard 23-24 | Jaccard 24-25 | 2025 학습구간 미관측 지점 | **2025 이용량 커버리지** |",
          "| :-: | -: | -: | -: | -: | -: | -: | -: |"]
    for mode, c in result["id_continuity"].items():
        pts = c["points"]
        j = c["jaccard"]
        cov = c.get("test2025_volume_coverage_by_train_points")
        L.append(f"| {mode} | {pts.get('2023', pts.get(2023, '-'))} | {pts.get('2024', pts.get(2024, '-'))} | {pts.get('2025', pts.get(2025, '-'))} | "
                 f"{j.get('2023-2024', 0) or 0:.3f} | {j.get('2024-2025', 0) or 0:.3f} | "
                 f"{c.get('test2025_points_unseen_in_train', '-')} | "
                 f"{('%.2f%%' % (cov * 100)) if cov is not None else '-'} |")

    L += ["", "## 5. 라벨 정합: 지점 합계 vs 기존 자치구 라벨 (R7 · R4)", "",
          "| 연도 | 수단 | 매칭 셀 | Pearson r | 합계비(지점/라벨) | 중앙 상대오차 | 5% 이내 | 라벨>0 · 미관측일(보간 추정) | 라벨>0 · 관측일인데 지점행 없음 |",
          "| :-: | :-: | -: | -: | -: | -: | -: | -: | -: |"]
    for y, yr in result["years"].items():
        la = yr.get("label_alignment", {})
        for mode, m in la.get("modes", {}).items():
            if not m.get("matched_cells"):
                continue
            L.append(f"| {y} | {mode} | {m['matched_cells']:,} | {m['pearson_r']:.4f} | {m['sum_ratio_point_over_label']:.4f} | "
                     f"{m['median_abs_rel_diff']:.4f} | {m['share_cells_within_5pct'] * 100:.1f}% | "
                     f"{m['label_positive_cells_on_unobserved_dates']:,} | {m['label_positive_cells_observed_date_without_rows']:,} |")

    L += ["", "## 6. 집중도 및 밀집화 규모 (최신 연도 기준)", "",
          "| 수단 | 지점 수 | K90 중앙/최대 | K95 중앙/최대 | K90 합 | K95 합 | 상위1 누적 | 상위10 누적 | 상위50 누적 | 밀집 행수/년 (K95) | 밀집 행수/년 (전체) |",
          "| :-: | -: | :-: | :-: | -: | -: | -: | -: | -: | -: | -: |"]
    for mode, c in result["concentration"].items():
        L.append(f"| {mode} | {c['points_total']:,} | {c['k90_median']:.0f}/{c['k90_max']} | {c['k95_median']:.0f}/{c['k95_max']} | "
                 f"{c['k90_sum']:,} | {c['k95_sum']:,} | {c['top1_cum_median'] * 100:.1f}% | {c['top10_cum_median'] * 100:.1f}% | "
                 f"{c['top50_cum_median'] * 100:.1f}% | {c['dense_rows_per_year_k95']:,} | {c['dense_rows_per_year_all']:,} |")

    L += ["", "## 7. G0 판정 상세", "", "| 검사 | 연도 | 수단 | 값 | 판정 |", "| :-: | :-: | :-: | :-: | :-: |"]
    for it in result["g0"]["items"]:
        val = it.get("pearson_r", it.get("coverage", it.get("p99_dev")))
        extra = f" / 합계비 {it['sum_ratio']:.3f}" if "sum_ratio" in it else ""
        L.append(f"| {it['check']} | {it.get('year', '-')} | {it['mode']} | {val:.4f}{extra} | {it['status']} |")
    return "\n".join(L) + "\n"


# ─────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025])
    ap.add_argument("--limit-files", type=int, default=None, help="연도당 앞 N개 파일만 (빠른 점검용)")
    ap.add_argument("--chunksize", type=int, default=2_000_000)
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "benchmarks", "results"))
    args = ap.parse_args()

    t0 = time.time()
    result = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "limit_files": args.limit_files, "train_end": TRAIN_END, "years": {}}
    per_year_points = {}
    last_year_points = None
    last_dates = {}

    for year in args.years:
        log(f"=== {year} 스캔 시작 ===")
        hourly, points, quality = scan_year(year, args.chunksize, args.limit_files)
        internal = analyze_internal(hourly, points)
        result["years"][str(year)] = {
            "quality": quality,
            "internal": internal,
            "report_check": compare_report(year, internal, partial=bool(args.limit_files)),
            "label_alignment": analyze_label_alignment(year, hourly),
        }
        per_year_points[year] = points
        last_year_points = points
        last_dates = {m: v["observed_dates"] for m, v in internal.items()}
        log(f"=== {year} 완료 (행 {quality['rows']:,}) ===")

    result["id_continuity"] = analyze_id_continuity(per_year_points)
    result["concentration"] = analyze_concentration(last_year_points, last_dates)
    result["g0"] = verdict_g0(result)
    result["elapsed_sec"] = time.time() - t0

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_sample" if args.limit_files else ""
    json_path = os.path.join(args.out_dir, f"point_share_audit_{stamp}{suffix}.json")
    md_path = os.path.join(args.out_dir, f"point_share_audit_{stamp}{suffix}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(to_native(result), f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(to_native(result)))

    log(f"G0 종합 판정: {result['g0']['overall']}")
    log(f"JSON  : {rel(json_path)}")
    log(f"MD    : {rel(md_path)}")
    log(f"총 소요: {result['elapsed_sec']:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
