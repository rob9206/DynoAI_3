"""One-shot summary of iter_3 findings for v4 planning."""

from __future__ import annotations

import json
from pathlib import Path

P = Path(
    r"vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_3\analyses\iter3_dwrt_findings.json"
)

data = json.loads(P.read_text(encoding="utf-8"))
grid = data["ve_correction_grid"]
total = data["total_valid_rows_used"]

neg = [c for c in grid if c["ve_delta_pct"] < 0]
pos = [c for c in grid if c["ve_delta_pct"] > 0]

print(f"total cells: {len(grid)}")
print(f"total valid rows: {total}")
print(f"rich (neg ve_delta -> trim fuel): {len(neg)} cells")
print(f"lean (pos ve_delta -> add fuel): {len(pos)} cells")
print()

print("WOT-ish cells (TPS >= 60, sorted by RPM):")
wot = sorted(
    [c for c in grid if c["tps_pct"] >= 60.0],
    key=lambda c: (c["rpm_k"], c["tps_pct"]),
)
for c in wot:
    rpm = int(round(c["rpm_k"] * 1000))
    print(
        f"  RPM={rpm:>5d} TPS={c['tps_pct']:>5.1f}%  n={c['n']:>3d}  "
        f"err={c['median_err_pct']:+6.2f}%  ve_delta={c['ve_delta_pct']:+6.2f}%"
    )
print()

if neg:
    nv = [c["ve_delta_pct"] for c in neg]
    print(
        f"neg stats: min={min(nv):.2f}%, median={sorted(nv)[len(nv) // 2]:.2f}%, max={max(nv):.2f}%"
    )
if pos:
    pv = [c["ve_delta_pct"] for c in pos]
    print(
        f"pos stats: min={min(pv):.2f}%, median={sorted(pv)[len(pv) // 2]:.2f}%, max={max(pv):.2f}%"
    )
