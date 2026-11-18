#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
로컬 PC에서 `benchmarks/CastTransit_PointShare_v3.ipynb` 를 그대로 순차 실행하는 러너.
노트북 코드 셀을 수정 없이 exec 하므로 Colab과 로컬 간 코드 드리프트가 0% 입니다.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_PATH = ROOT / "benchmarks" / "CastTransit_PointShare_v3.ipynb"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-optuna", action="store_true", help="Optuna 튜닝 건너뛰고 기본/v2.1 파라미터로 실행")
    ap.add_argument("--n-trials-s1", type=int, default=20, help="Stage 1 Optuna 탐색 횟수")
    ap.add_argument("--n-trials-s2", type=int, default=20, help="Stage 2 Optuna 탐색 횟수")
    ap.add_argument("--force-rebuild-cache", action="store_true", help="중간 캐시 무시하고 원천 CSV부터 재구축")
    args = ap.parse_args()

    os.chdir(ROOT)
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]

    ns: dict = {"__name__": "__main__", "__file__": str(NB_PATH)}
    t_total = time.time()

    for idx, cell in enumerate(code_cells, 1):
        cid = cell.get("metadata", {}).get("id", f"cell_{idx}")
        src = "".join(cell["source"])
        print(f"\n==================== [{idx}/{len(code_cells)}] {cid} 시작 ====================", flush=True)
        t_c = time.time()
        exec(compile(src, f"<CastTransit_PointShare_v3:{cid}>", "exec"), ns)

        # Cell 1 직후 CLI 인자 오버라이드 주입
        if idx == 1:
            if args.no_optuna:
                ns["RUN_OPTUNA"] = False
            ns["N_TRIALS_STAGE1"] = args.n_trials_s1
            ns["N_TRIALS_STAGE2"] = args.n_trials_s2
            ns["FORCE_REBUILD_CACHE"] = bool(args.force_rebuild_cache)
            print(
                f"[Runner Config] RUN_OPTUNA={ns['RUN_OPTUNA']} | S1_TRIALS={ns['N_TRIALS_STAGE1']} | "
                f"S2_TRIALS={ns['N_TRIALS_STAGE2']} | FORCE_CACHE={ns['FORCE_REBUILD_CACHE']}",
                flush=True,
            )

        print(f"-------------------- [{idx}/{len(code_cells)}] {cid} 완료 ({time.time() - t_c:.1f}s) --------------------", flush=True)

    print(f"\n🏁 전체 파이프라인 실행 완료! 총 소요: {time.time() - t_total:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
