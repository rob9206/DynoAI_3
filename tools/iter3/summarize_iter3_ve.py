"""Quick human-readable summary for iter_3 VE deltas."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_3\patch\ve_correction_delta.csv"
)


def tps_zone(tps: float) -> str:
    if tps <= 30:
        return "cruise_tps(<=30)"
    if tps <= 70:
        return "part_tps(30-70]"
    return "wot_tps(>70)"


def rpm_zone(rpm: float) -> str:
    if rpm <= 2500:
        return "low_rpm(<=2500)"
    if rpm <= 4000:
        return "mid_rpm(2500-4000]"
    return "upper_rpm(>4000)"


def main() -> int:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    print(f"rows: {len(rows)}")

    by_tps = defaultdict(list)
    by_rpm = defaultdict(list)
    for row in rows:
        d = float(row["delta_pct"])
        by_tps[tps_zone(float(row["tps_pct"]))].append(d)
        by_rpm[rpm_zone(float(row["RPM"]))].append(d)

    print("\nBy TPS zone:")
    for key in ("cruise_tps(<=30)", "part_tps(30-70]", "wot_tps(>70)"):
        vals = by_tps.get(key, [])
        if not vals:
            continue
        print(
            f"  {key:20s} n={len(vals):2d} avg={statistics.fmean(vals):+7.3f}% "
            f"min={min(vals):+7.3f}% max={max(vals):+7.3f}%"
        )

    print("\nBy RPM zone:")
    for key in ("low_rpm(<=2500)", "mid_rpm(2500-4000]", "upper_rpm(>4000)"):
        vals = by_rpm.get(key, [])
        if not vals:
            continue
        print(
            f"  {key:20s} n={len(vals):2d} avg={statistics.fmean(vals):+7.3f}% "
            f"min={min(vals):+7.3f}% max={max(vals):+7.3f}%"
        )

    print("\nTop 12 absolute deltas:")
    rows_sorted = sorted(rows, key=lambda r: abs(float(r["delta_pct"])), reverse=True)
    for row in rows_sorted[:12]:
        print(
            f"  {row['cylinder']:5s} RPM={row['RPM']:>4s} TPS={row['tps_pct']:>5s} "
            f"delta={float(row['delta_pct']):+7.3f}% n={row['n_samples']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
