# -*- coding: utf-8 -*-
"""
Stage 2 지점 점유율 분해 추론 엔진 (`v3.0-point-share-16d`)

2단계 계층적 수요·혼잡도 예측:
    Stage 1 (32차원 자치구 총수요 ONNX):  Y_hat(district, mode, t)
    Stage 2 (16차원 지점 점유율 ONNX):   s_hat(point_i, mode, t)  [%]
    결합 지점 수요:                      y_hat(i, t) = Y_hat * (s_hat / 100)

`models/point_share_schema.json`과 `models/point_share_priors.json.gz`를 로드해
학습↔서빙 피처 순서(16차원) 정합성을 기동 시 검증하고,
지하철(호선별 합산 포함)·버스(stId)·따릉이(대여소 번호·명칭) 단위의
개별 수요·점유율·혼잡도를 실시간 추론합니다.
"""
from __future__ import annotations

import gzip
import json
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import onnxruntime as ort

logger = logging.getLogger("weather_transit_api.point_share")

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

FEATURE_ORDER_POINT_16 = [
    # [0..7] 시계열 및 캘린더 피처
    "month_sin",
    "month_cos",
    "hour_sin",
    "hour_cos",
    "dayofweek",
    "is_weekend",
    "is_holiday",
    "is_rush_hour",
    # [8..11] 기상 관측 피처 (`point_share_schema.json::stage2_feature_cols` 순서 엄수)
    "temperature",
    "precipitation",
    "wind_speed",
    "humidity",
    # [12..15] 학습 구간(~2024-09-30) 지점 사전통계 피처 (미래 누수 차단)
    "point_prior_base_share",
    "point_prior_dow_hour_share",
    "point_prior_rush_ratio",
    "point_prior_rain_elasticity",
]

SUBWAY_NAME_ALIASES = {
    "뚝섬유원지": "자양",
    "불암산": "당고개",
}


def normalize_subway_name(raw: Optional[str]) -> str:
    """역명에서 괄호 부제·공백·접미어 '역'을 제거해 정규화."""
    s = str(raw or "").strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\s+", "", s)
    if s.endswith("역") and len(s) > 1:
        s = s[:-1]
    return SUBWAY_NAME_ALIASES.get(s, s)


def normalize_bike_name(raw: Optional[str]) -> str:
    """따릉이 대여소명에서 접두어 '따릉이:' 및 공백을 제거해 정규화."""
    s = str(raw or "").strip()
    s = re.sub(r"^따릉이\s*:\s*", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _station_hash_offset(name: str, spread: int = 2) -> int:
    """문자열 기반 결정적 해시 오프셋 (-spread .. +spread)."""
    if not name or spread <= 0:
        return 0
    h = 0
    for ch in name:
        h = ((h << 5) - h) + ord(ch)
        h &= 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    mod = 2 * spread + 1
    return (abs(h) % mod) - spread


class PointShareEngine:
    """Stage 2 (16차원 LightGBM Point-Share ONNX) 인메모리 추론 및 지점 매핑 엔진."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.sessions: dict[str, ort.InferenceSession] = {}
        self.schema: Optional[dict] = None
        self.schema_status: str = "not-checked"
        self.model_input_dims: dict[str, int] = {}
        self.points: dict[str, dict[str, dict]] = {}
        self.indices: dict[str, Any] = {}
        self.district_mode_stats: dict[str, dict] = {}
        self.bundle_meta: dict[str, Any] = {}
        self.is_loaded: bool = False
        self.load_ms: float = 0.0

    def load(self) -> bool:
        """16차원 ONNX 모델 3종, 스키마, 사전통계 번들(`point_share_priors.json.gz`) 로드 및 웜업."""
        t0 = time.perf_counter()
        schema_path = self.model_dir / "point_share_schema.json"
        priors_path = self.model_dir / "point_share_priors.json.gz"

        model_paths = {
            "bike": self.model_dir / "lgb_bike_point_share.onnx",
            "bus": self.model_dir / "lgb_bus_point_share.onnx",
            "subway": self.model_dir / "lgb_subway_point_share.onnx",
        }

        missing = [str(p) for p in [schema_path, priors_path, *model_paths.values()] if not p.exists()]
        if missing:
            self.schema_status = "assets-missing"
            self.is_loaded = False
            logger.warning(f"[PointShare] Stage 2 자산 일부가 없어 구 평균 추론으로 동작합니다: {missing}")
            return False

        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

        schema_cols = self.schema.get("stage2_feature_cols", [])
        if schema_cols != FEATURE_ORDER_POINT_16:
            raise ValueError(
                f"[PointShare] 16차원 스키마 순서 불일치: "
                f"schema={schema_cols} vs code={FEATURE_ORDER_POINT_16}"
            )
        self.schema_status = "verified"

        with gzip.open(priors_path, "rt", encoding="utf-8") as gz:
            bundle = json.load(gz)

        self.bundle_meta = bundle.get("meta", {})
        self.points = bundle.get("points", {})
        self.indices = bundle.get("indices", {})
        self.district_mode_stats = bundle.get("district_mode_stats", {})

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 4
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        self.sessions = {}
        self.model_input_dims = {}
        for mode, mpath in model_paths.items():
            sess = ort.InferenceSession(
                str(mpath),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            inp_meta = sess.get_inputs()[0]
            dim = int(inp_meta.shape[1]) if len(inp_meta.shape) > 1 and isinstance(inp_meta.shape[1], int) else -1
            if dim != len(FEATURE_ORDER_POINT_16):
                raise ValueError(
                    f"[PointShare] {mode} Stage 2 모델 입력 차원 불일치: {dim} != {len(FEATURE_ORDER_POINT_16)}"
                )
            dummy = np.zeros((1, dim), dtype=np.float32)
            _ = sess.run(None, {inp_meta.name: dummy})
            self.sessions[mode] = sess
            self.model_input_dims[mode] = dim

        self.is_loaded = True
        self.load_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        logger.info(
            f"[PointShare] Stage 2 16d ONNX 3종 및 {self.bundle_meta.get('total_points', 0):,}개 지점 번들 로드 완료 "
            f"({self.load_ms:.1f}ms, schema={self.schema_status})"
        )
        return True

    def status_report(self) -> dict[str, Any]:
        """`/health` 및 `/api/v1/admin/status` 노출용 Stage 2 상태 요약."""
        return {
            "loaded": self.is_loaded,
            "model_version": self.bundle_meta.get("model_version", "v3.0-point-share-16d"),
            "schema_status": self.schema_status,
            "feature_dim": len(FEATURE_ORDER_POINT_16),
            "model_input_dims": dict(self.model_input_dims),
            "point_counts": dict(self.bundle_meta.get("counts", {})),
            "load_ms": self.load_ms,
        }

    def resolve_points(
        self,
        mode: str,
        district: str,
        station_name: Optional[str] = None,
        point_id: Optional[str] = None,
        base_crowd: Optional[int] = None,
    ) -> tuple[list[str], str]:
        """요청된 역/정류소/대여소에 대응하는 `(지점ID 목록, 추론 계층)` 반환."""
        mode_points = self.points.get(mode, {})
        pid_clean = str(point_id).strip() if point_id else ""

        if mode == "subway":
            if pid_clean and pid_clean in mode_points:
                return [pid_clean], "POINT_EXACT_ONNX"

            clean_sub = normalize_subway_name(station_name)
            if clean_sub:
                by_dn = self.indices.get("subway_by_district_name", {})
                by_n = self.indices.get("subway_by_name", {})
                pids = by_dn.get(f"{district}|{clean_sub}") or by_n.get(clean_sub)
                if pids:
                    return list(pids), "POINT_EXACT_ONNX"

        elif mode == "bus":
            bus_idx = self.indices.get("bus_by_st_id", {})
            for cand in (pid_clean, station_name or ""):
                if not cand:
                    continue
                if cand in bus_idx:
                    return [bus_idx[cand]], "POINT_EXACT_ONNX"
                m = re.search(r"\b(\d{9})\b", cand)
                if m and m.group(1) in bus_idx:
                    return [bus_idx[m.group(1)]], "POINT_EXACT_ONNX"

        elif mode == "bike":
            bike_name_idx = self.indices.get("bike_by_district_name", {})
            clean_bike = normalize_bike_name(station_name)
            if clean_bike:
                matched_pid = bike_name_idx.get(f"{district}|{clean_bike}")
                if not matched_pid:
                    prefix = f"{district}|"
                    for k, candidate_pid in bike_name_idx.items():
                        if k.startswith(prefix):
                            key_name = k[len(prefix):]
                            if len(key_name) >= 3 and (clean_bike in key_name or key_name in clean_bike):
                                matched_pid = candidate_pid
                                break
                if matched_pid and matched_pid in mode_points:
                    return [matched_pid], "POINT_EXACT_ONNX"

            bike_no_idx = self.indices.get("bike_by_station_no", {})
            if pid_clean and not pid_clean.startswith("bike-"):
                for k in (pid_clean, pid_clean.lstrip("0") or pid_clean):
                    if k in bike_no_idx:
                        return [bike_no_idx[k]], "POINT_EXACT_ONNX"

            if station_name:
                m = re.match(r"^\s*#?(\d{3,5})(?:\D|$)", station_name)
                if m:
                    num = m.group(1)
                    for k in (num, num.lstrip("0") or num):
                        if k in bike_no_idx:
                            return [bike_no_idx[k]], "POINT_EXACT_ONNX"

        # Tier 2: 데이터셋 직접 매핑 불가 거점은 해당 자치구·수단 내 baseCrowd 백분위 대표 지점으로 Stage 2 ONNX 추론
        dm_stats = (
            self.district_mode_stats.get(f"{district}|{mode}")
            or self.district_mode_stats.get(f"강남구|{mode}")
        )
        if dm_stats and dm_stats.get("sorted_point_ids"):
            sorted_ids: list[str] = dm_stats["sorted_point_ids"]
            default_pct = 55 if mode == "bus" else 50
            pct = max(5, min(95, int(base_crowd) if base_crowd is not None else default_pct))
            base_idx = int(round((pct / 100.0) * (len(sorted_ids) - 1)))
            offset = _station_hash_offset(station_name or pid_clean, spread=min(2, max(0, len(sorted_ids) // 10)))
            idx = max(0, min(len(sorted_ids) - 1, base_idx + offset))
            return [sorted_ids[idx]], "POINT_PERCENTILE_ONNX"

        return [], "DISTRICT_FALLBACK"

    def predict_point(
        self,
        mode: str,
        district: str,
        hour: int,
        temp: float,
        rain: float,
        wind: float,
        humidity: float,
        district_volume: float,
        station_name: Optional[str] = None,
        point_id: Optional[str] = None,
        base_crowd: Optional[int] = None,
        dt: Optional[datetime] = None,
        is_holiday: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Stage 1 자치구 총수요와 Stage 2 16차원 ONNX 점유율 모델을 결합해 개별 지점 수요·혼잡도를 산출."""
        if not self.is_loaded or mode not in self.sessions:
            return None

        matched_ids, tier = self.resolve_points(
            mode=mode,
            district=district,
            station_name=station_name,
            point_id=point_id,
            base_crowd=base_crowd,
        )
        if not matched_ids:
            return None

        if dt is None:
            dt = datetime.now(timezone(timedelta(hours=9)))

        h_norm = 0 if hour == 24 else max(0, min(23, int(hour)))
        month = dt.month
        dayofweek = dt.weekday()
        is_weekend = 1 if dayofweek in (5, 6) else 0
        is_rush_hour = 1 if int(hour) in (8, 9, 18, 19) else 0

        month_sin = math.sin(2.0 * math.pi * month / 12.0)
        month_cos = math.cos(2.0 * math.pi * month / 12.0)
        hour_sin = math.sin(2.0 * math.pi * h_norm / 24.0)
        hour_cos = math.cos(2.0 * math.pi * h_norm / 24.0)

        t_val = float(temp)
        r_val = max(0.0, float(rain))
        w_val = max(0.0, float(wind))
        hum_val = max(0.0, min(100.0, float(humidity)))

        sess = self.sessions[mode]
        inp_name = sess.get_inputs()[0].name
        mode_points = self.points.get(mode, {})
        dh_slot = is_weekend * 24 + h_norm

        total_share_pct = 0.0
        total_p95 = 0.0
        point_districts: list[str] = []

        for pid in matched_ids:
            meta = mode_points.get(pid)
            if not meta:
                continue
            b = float(meta["b"])
            r_ratio = float(meta["r"])
            e_ratio = float(meta["e"])
            dh_arr = meta.get("dh", [])
            dh_share = float(dh_arr[dh_slot]) if dh_slot < len(dh_arr) else b

            vec_16 = [
                month_sin,
                month_cos,
                hour_sin,
                hour_cos,
                float(dayofweek),
                float(is_weekend),
                1.0 if is_holiday else 0.0,
                float(is_rush_hour),
                t_val,
                r_val,
                w_val,
                hum_val,
                b,
                dh_share,
                r_ratio,
                e_ratio,
            ]
            tensor = np.array([vec_16], dtype=np.float32)
            raw_share = float(sess.run(None, {inp_name: tensor})[0].flatten()[0])
            total_share_pct += max(0.005, raw_share)
            total_p95 += float(meta["p95"])
            if meta.get("d"):
                point_districts.append(str(meta["d"]))

        if total_share_pct <= 0.0 or total_p95 <= 0.0:
            return None

        share_pct = min(95.0, total_share_pct)
        dist_vol = max(1.0, float(district_volume))
        pred_vol = max(1, int(round(dist_vol * (share_pct / 100.0))))

        ref_district = point_districts[0] if point_districts else district
        dm_stats = (
            self.district_mode_stats.get(f"{ref_district}|{mode}")
            or self.district_mode_stats.get(f"{district}|{mode}")
            or {}
        )
        median_p95 = float(dm_stats.get("median_p95", total_p95))

        r_self = min(1.0, pred_vol / max(1.0, total_p95))
        r_scale = min(1.35, pred_vol / max(1.0, median_p95))
        raw_crowd = (0.65 * r_self + 0.35 * r_scale) * 100.0
        crowd = int(round(min(99.0, max(5.0, raw_crowd))))

        return {
            "predicted_volume": pred_vol,
            "district_predicted_volume": int(round(dist_vol)),
            "point_share_pct": round(share_pct, 2),
            "point_p95": round(total_p95, 1),
            "crowd": crowd,
            "inference_tier": tier,
            "matched_point_id": ",".join(matched_ids),
            "resolved_district": ref_district,
        }


point_share_engine = PointShareEngine()
