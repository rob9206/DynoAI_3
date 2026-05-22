"""Analyze cruise samples binned to VE-table (RPM_idx, TPS_idx) cells.

Loads steady-state cruise samples from given indices, snaps each sample to the
closest VE-table row (RPM_k) and column (TPS_pct), and computes mean LC2 vs
target AFR (from MAP) per cell. Writes a CSV of corrections suitable for
generate_iter11_patch.py.

Usage:
    python tools/iter11/analyze_by_ve_cell.py --indices 46 47 48 --out path.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_iter2_patch as g2  # noqa: E402
from iter9.analyze_cruise_logs import (  # noqa: E402
    FOLDER,
    _afr_target_for_map,
    load_log,
    steady_state_mask,
)

ITER9_PATCH = (
    g2.SESSION_DIR / "iterations" / "iter_9" / "patch" / "iter_9_patched.pvv"
)


def _closest_idx(value: float, axis: list[float]) -> int:
    best = 0
    best_d = abs(value - axis[0])
    for i, ax in enumerate(axis):
        d = abs(value - ax)
        if d < best_d:
            best_d = d
            best = i
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--indices", type=int, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import xml.etree.ElementTree as ET

    root = ET.parse(str(ITER9_PATCH)).getroot()
    ve_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    rpm_axis, tps_axis, _ = g2.read_table(ve_item)
    unique_rpm_idx = sorted({_closest_idx(rpm_axis[i], rpm_axis) for i in range(len(rpm_axis))})
    unique_tps_idx = sorted({_closest_idx(tps_axis[i], tps_axis) for i in range(len(tps_axis))})
    print(f"VE axes -- rpm_k: {[rpm_axis[i] for i in unique_rpm_idx]}")
    print(f"VE axes -- tps_pct: {[tps_axis[i] for i in unique_tps_idx]}")

    rows: list[pd.DataFrame] = []
    for idx in args.indices:
        p = FOLDER / f"PV_Logfile_5.csv_{idx}.txt"
        if not p.exists():
            print(f"MISSING: {p.name}")
            continue
        df = load_log(p)
        m = steady_state_mask(df)
        sub = df[m].copy()
        if sub.empty:
            continue
        sub["_target"] = sub["_map"].apply(_afr_target_for_map)
        sub["_correction"] = sub["_lc2"] / sub["_target"]
        sub["_rpm_idx"] = (
            sub["_rpm"].apply(lambda v: _closest_idx(v / 1000.0, rpm_axis))
        )
        sub["_tps_idx"] = sub["_tps"].apply(lambda v: _closest_idx(v, tps_axis))
        rows.append(sub)
        print(f"  {p.name}: steady_samples={len(sub)}")

    if not rows:
        print("no data")
        return 1
    all_data = pd.concat(rows, ignore_index=True)
    print(f"\nTotal steady-state samples: {len(all_data)}")

    grid = (
        all_data.groupby(["_rpm_idx", "_tps_idx"])
        .agg(
            n=("_lc2", "count"),
            lc2_avg=("_lc2", "mean"),
            target_avg=("_target", "mean"),
            corr_avg=("_correction", "mean"),
            map_avg=("_map", "mean"),
            rpm_avg=("_rpm", "mean"),
            tps_avg=("_tps", "mean"),
        )
        .reset_index()
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rpm_idx",
                "tps_idx",
                "rpm_k",
                "tps_pct",
                "n",
                "lc2_avg",
                "target_avg",
                "corr_avg",
                "map_avg",
                "rpm_meas_avg",
                "tps_meas_avg",
            ]
        )
        for _, r in grid.iterrows():
            ri = int(r["_rpm_idx"])
            ti = int(r["_tps_idx"])
            w.writerow(
                [
                    ri,
                    ti,
                    f"{rpm_axis[ri]:g}",
                    f"{tps_axis[ti]:g}",
                    int(r["n"]),
                    f"{r['lc2_avg']:.3f}",
                    f"{r['target_avg']:.3f}",
                    f"{r['corr_avg']:.4f}",
                    f"{r['map_avg']:.1f}",
                    f"{r['rpm_avg']:.0f}",
                    f"{r['tps_avg']:.1f}",
                ]
            )

    print(f"\nWrote per-cell corrections: {args.out}")
    print("\nTop cells by richness (corr < 1.0 = rich):")
    top = grid.sort_values("corr_avg").head(20)
    print(
        f"  {'rpm_k':>6} {'tps':>5} {'n':>4} {'LC2':>5} {'tgt':>5} {'corr':>6}"
        f" {'map':>5} {'tps_meas':>9}"
    )
    for _, r in top.iterrows():
        ri = int(r["_rpm_idx"])
        ti = int(r["_tps_idx"])
        print(
            f"  {rpm_axis[ri]:>6g} {tps_axis[ti]:>5g} "
            f"{int(r['n']):>4d} {r['lc2_avg']:>5.2f} {r['target_avg']:>5.2f} "
            f"{r['corr_avg']:>6.3f} {r['map_avg']:>5.1f} {r['tps_avg']:>9.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
