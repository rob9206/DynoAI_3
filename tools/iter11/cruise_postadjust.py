"""Cruise AFR analysis on the post-retorque/post-sniffer 5th-gear cruise log."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iter9.analyze_cruise_logs import (  # noqa: E402
    FOLDER,
    MAP_BINS,
    RPM_BINS,
    _afr_target_for_map,
    _bin_label,
    load_log,
    steady_state_mask,
)


def main() -> int:
    p = FOLDER / "5th gear 11 probe adjusted crusiing.txt"
    if not p.exists():
        print(f"missing: {p}")
        return 1
    df = load_log(p)
    m = steady_state_mask(df)
    sub = df[m].copy()
    sub["_rpm_bin"] = sub["_rpm"].apply(lambda x: _bin_label(x, RPM_BINS))
    sub["_map_bin"] = sub["_map"].apply(lambda x: _bin_label(x, MAP_BINS))
    sub = sub.dropna(subset=["_rpm_bin", "_map_bin"])
    sub["_target"] = sub["_map"].apply(_afr_target_for_map)
    sub["_afr_err"] = sub["_lc2"] - sub["_target"]

    print(f"file: {p.name}")
    print(f"rows={len(df)}  steady_samples={len(sub)}")
    if sub.empty:
        return 0
    print(f"RPM range: {sub['_rpm'].min():.0f}-{sub['_rpm'].max():.0f}")
    print(f"MAP range: {sub['_map'].min():.1f}-{sub['_map'].max():.1f}")
    print(f"TPS range: {sub['_tps'].min():.1f}-{sub['_tps'].max():.1f}")

    grid = (
        sub.groupby(["_rpm_bin", "_map_bin"])
        .agg(
            n=("_lc2", "count"),
            lc2_avg=("_lc2", "mean"),
            tgt=("_target", "mean"),
            err=("_afr_err", "mean"),
            tps=("_tps", "mean"),
        )
        .reset_index()
    )
    grid = grid[grid["n"] >= 3]

    def _cell(r: int, m: int, key: str, fmt: str) -> str:
        v = grid[(grid["_rpm_bin"] == r) & (grid["_map_bin"] == m)][key]
        if len(v):
            return f"{v.iloc[0]:{fmt}}"
        return "  -  "

    print("\nLC2 (measured AFR):")
    print("  rpm   |  " + "  |  ".join(f"{m:>3}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells = [_cell(r, m, "lc2_avg", ">5.2f") for m in MAP_BINS]
        print(f"  {r:>5}  |  " + "  |  ".join(cells))

    print("\nAFR error (LC2 - target ; - = rich, + = lean):")
    print("  rpm   |  " + "  |  ".join(f"{m:>3}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells = [_cell(r, m, "err", ">+5.2f") for m in MAP_BINS]
        print(f"  {r:>5}  |  " + "  |  ".join(cells))

    print("\nSample count per cell:")
    print("  rpm   |  " + "  |  ".join(f"{m:>3}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells = [_cell(r, m, "n", ">5.0f") for m in MAP_BINS]
        print(f"  {r:>5}  |  " + "  |  ".join(cells))

    biggest = grid.reindex(grid["err"].abs().sort_values(ascending=False).index)
    print("\nTop 12 cells by |AFR error|:")
    print("  rpm   map   n   LC2avg  target   err     tps")
    for _, row in biggest.head(12).iterrows():
        print(
            f"  {int(row['_rpm_bin']):>4}  {int(row['_map_bin']):>4}  "
            f"{int(row['n']):>3}  {row['lc2_avg']:>6.2f}  {row['tgt']:>6.2f}  "
            f"{row['err']:>+5.2f}   {row['tps']:>4.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
