# -*- coding: utf-8 -*-
"""
Stage 2 지점 점유율 서빙 번들 생성 스크립트 (`models/point_share_priors.json.gz`)

`benchmarks/cache_point_share_v3/stage2_priors_cache.pkl` (학습 구간 ~2024-09-30 산출)을
FastAPI 백엔드 컨테이너가 `pyarrow`/`pandas` 의존성 없이 표준 라이브러리(`gzip`, `json`)만으로
0.1초 이내에 로드해 서빙할 수 있는 경량 JSON.gz 번들로 변환합니다.
"""
from __future__ import annotations

import gzip
import json
import math
import pickle
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_PKL = ROOT_DIR / "benchmarks" / "cache_point_share_v3" / "stage2_priors_cache.pkl"
OUT_GZ = ROOT_DIR / "models" / "point_share_priors.json.gz"

MODE_KO_TO_EN = {
    "지하철": "subway",
    "버스": "bus",
    "따릉이": "bike",
}


def normalize_subway_name(raw: str) -> str:
    """역명에서 괄호 부제·선두/후행 공백·접미어 '역'을 제거해 정규화."""
    s = str(raw or "").strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\s+", "", s)
    if s.endswith("역") and len(s) > 1:
        s = s[:-1]
    return s


def extract_paren_aliases(raw: str) -> list[str]:
    """'삼성(무역센터)' 같은 괄호 부제에서 별칭 토큰 추출."""
    aliases: list[str] = []
    for inner in re.findall(r"\(([^)]+)\)", str(raw or "")):
        for tok in re.split(r"[·,/.\s]+", inner.strip()):
            tok = tok.strip()
            if len(tok) >= 2:
                if tok.endswith("역") and len(tok) > 1:
                    tok = tok[:-1]
                aliases.append(tok)
    return aliases


def normalize_bike_name(raw: str) -> str:
    """따릉이 대여소명에서 접두어 '따릉이:' 및 공백·특수구분자 정규화."""
    s = str(raw or "").strip()
    s = re.sub(r"^따릉이\s*:\s*", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _safe_float(val, default: float) -> float:
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def main():
    t0 = time.perf_counter()
    if not CACHE_PKL.exists():
        print(f"ERROR: cache pkl not found: {CACHE_PKL}", file=sys.stderr)
        sys.exit(1)

    with open(CACHE_PKL, "rb") as f:
        cache = pickle.load(f)

    sp = cache["static_priors"]
    dhp = cache["dow_hour_priors"]
    cf = cache["cold_fallback"]
    nm = cache.get("dist_name_map", {})

    # (mode_en, pid) -> 48-slot list initialized later with base_share
    dh_lookup: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in dhp.itertuples(index=False):
        mode_en = MODE_KO_TO_EN.get(str(row.교통수단))
        if not mode_en:
            continue
        pid = str(row.지점ID)
        slot = int(row.is_weekend) * 24 + int(row.시간)
        if 0 <= slot < 48:
            val = _safe_float(row.point_prior_dow_hour_share, 0.0)
            dh_lookup[(mode_en, pid)][slot] = round(val, 6)

    points: dict[str, dict[str, dict]] = {"subway": {}, "bus": {}, "bike": {}}
    subway_by_district_name: dict[str, list[str]] = defaultdict(list)
    subway_by_name: dict[str, list[str]] = defaultdict(list)
    bike_by_station_no: dict[str, str] = {}
    bike_by_district_name: dict[str, str] = {}
    bus_by_st_id: dict[str, str] = {}
    dm_points: dict[str, list[tuple[float, str, float]]] = defaultdict(list)

    # First pass: add primary records
    for row in sp.itertuples(index=False):
        mode_en = MODE_KO_TO_EN.get(str(row.교통수단))
        if not mode_en:
            continue
        district = str(row.행정구)
        pid = str(row.지점ID)
        base_s = max(0.0, _safe_float(row.point_prior_base_share, 1.0))
        rush_r = max(0.1, _safe_float(row.point_prior_rush_ratio, 1.0))
        rain_e = max(0.1, _safe_float(row.point_prior_rain_elasticity, 1.0))
        p95 = max(1.0, _safe_float(row.point_p95, 10.0))

        raw_name = nm.get(pid)
        raw_name_str = "" if raw_name is None or (isinstance(raw_name, float) and math.isnan(raw_name)) else str(raw_name).strip()

        slots_map = dh_lookup.get((mode_en, pid), {})
        base_r = round(base_s, 6)
        dh_arr = [slots_map.get(idx, base_r) for idx in range(48)]

        points[mode_en][pid] = {
            "d": district,
            "name": raw_name_str,
            "b": base_r,
            "r": round(rush_r, 6),
            "e": round(rain_e, 6),
            "p95": round(p95, 2),
            "dh": dh_arr,
        }
        dm_points[f"{district}|{mode_en}"].append((base_s, pid, p95))

        if mode_en == "subway" and raw_name_str:
            clean = normalize_subway_name(raw_name_str)
            if clean:
                dk = f"{district}|{clean}"
                if pid not in subway_by_district_name[dk]:
                    subway_by_district_name[dk].append(pid)
                if pid not in subway_by_name[clean]:
                    subway_by_name[clean].append(pid)
        elif mode_en == "bus":
            bus_by_st_id[pid] = pid
        elif mode_en == "bike":
            bike_by_station_no[pid] = pid
            stripped = pid.lstrip("0") or pid
            bike_by_station_no.setdefault(stripped, pid)
            if raw_name_str:
                bn = normalize_bike_name(raw_name_str)
                if bn:
                    bike_by_district_name.setdefault(f"{district}|{bn}", pid)

    # Secondary pass: add subway parenthetical aliases only when primary key absent
    for pid, meta in points["subway"].items():
        raw_name_str = meta["name"]
        district = meta["d"]
        for alias in extract_paren_aliases(raw_name_str):
            dk = f"{district}|{alias}"
            if dk not in subway_by_district_name:
                subway_by_district_name[dk].append(pid)
            if alias not in subway_by_name:
                subway_by_name[alias].append(pid)

    # Cold-start fallbacks & sorted quantile lists per (district, mode)
    cold_map: dict[tuple[str, str], float] = {}
    for row in cf.itertuples(index=False):
        mode_en = MODE_KO_TO_EN.get(str(row.교통수단))
        if mode_en:
            cold_map[(str(row.행정구), mode_en)] = _safe_float(row.point_prior_base_share, 1.0)

    district_mode_stats: dict[str, dict] = {}
    for dm_key, entries in dm_points.items():
        district, mode_en = dm_key.split("|", 1)
        entries_sorted = sorted(entries, key=lambda x: x[0])
        p95_sorted = sorted(x[2] for x in entries_sorted)
        mid = len(p95_sorted) // 2
        median_p95 = p95_sorted[mid] if p95_sorted else 10.0
        cold_b = cold_map.get((district, mode_en), entries_sorted[mid][0] if entries_sorted else 1.0)
        district_mode_stats[dm_key] = {
            "sorted_point_ids": [x[1] for x in entries_sorted],
            "median_p95": round(median_p95, 2),
            "point_count": len(entries_sorted),
            "cold_fallback": {
                "b": round(cold_b, 6),
                "r": 1.0,
                "e": 1.0,
                "p95": round(median_p95, 2),
            },
        }

    bundle = {
        "meta": {
            "model_version": "v3.0-point-share-16d",
            "train_window": "2023-01-01~2024-09-30",
            "total_points": sum(len(v) for v in points.values()),
            "counts": {k: len(v) for k, v in points.items()},
        },
        "points": points,
        "indices": {
            "subway_by_district_name": dict(subway_by_district_name),
            "subway_by_name": dict(subway_by_name),
            "bike_by_station_no": bike_by_station_no,
            "bike_by_district_name": bike_by_district_name,
            "bus_by_st_id": bus_by_st_id,
        },
        "district_mode_stats": district_mode_stats,
    }

    OUT_GZ.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_GZ, "wt", encoding="utf-8", compresslevel=6) as gz:
        json.dump(bundle, gz, ensure_ascii=False, separators=(",", ":"))

    t_save = time.perf_counter() - t0
    size_mb = OUT_GZ.stat().st_size / (1024 * 1024)
    print(f"Saved {OUT_GZ.as_posix()} ({size_mb:.2f} MB) in {t_save:.2f}s")
    print(f"Counts: {bundle['meta']['counts']} (total {bundle['meta']['total_points']})")

    # Verify load speed
    t_load0 = time.perf_counter()
    with gzip.open(OUT_GZ, "rt", encoding="utf-8") as gz:
        loaded = json.load(gz)
    print(f"Reload check: {len(loaded['points']['subway'])} subway, {len(loaded['points']['bus'])} bus, {len(loaded['points']['bike'])} bike in {(time.perf_counter() - t_load0)*1000:.1f}ms")

    # Quick coverage sanity check against frontend catalogs
    sub_ts = ROOT_DIR / "Weather-Transport Recommendation UI" / "src" / "subwayData.ts"
    if sub_ts.exists():
        txt = sub_ts.read_text(encoding="utf-8")
        names = re.findall(r'"name":\s*"([^"]+)"', txt)
        matched = sum(1 for n in names if normalize_subway_name(n) in loaded["indices"]["subway_by_name"])
        print(f"Frontend subwayData.ts name match: {matched}/{len(names)}")

    bus_ts = ROOT_DIR / "Weather-Transport Recommendation UI" / "src" / "busStopData.ts"
    if bus_ts.exists():
        txt = bus_ts.read_text(encoding="utf-8")
        st_ids = re.findall(r"stId:\s*'([^']+)'", txt)
        matched = sum(1 for s in st_ids if s in loaded["indices"]["bus_by_st_id"])
        print(f"Frontend busStopData.ts stId exact match: {matched}/{len(st_ids)}")

    bike_ts = ROOT_DIR / "Weather-Transport Recommendation UI" / "src" / "bikeStopData.ts"
    if bike_ts.exists():
        txt = bike_ts.read_text(encoding="utf-8")
        nos = re.findall(r"stationNo:\s*'([^']+)'", txt)
        matched = sum(1 for s in nos if s in loaded["indices"]["bike_by_station_no"] or s.lstrip("0") in loaded["indices"]["bike_by_station_no"])
        print(f"Frontend bikeStopData.ts stationNo exact match: {matched}/{len(nos)}")


if __name__ == "__main__":
    main()
