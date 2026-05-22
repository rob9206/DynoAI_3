"""Print iter_4 WOT VE trims for review."""

import csv
from pathlib import Path

P = Path(
    r"vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_4\patch\ve_correction_delta.csv"
)

rows = list(csv.DictReader(open(P)))
wot = [r for r in rows if r["cylinder"] == "front" and float(r["tps_pct"]) >= 60]
wot.sort(key=lambda r: (int(r["RPM"]), float(r["tps_pct"])))

print(f"Front WOT trims ({len(wot)} cells, rear mirrors front):")
print(f"{'RPM':>6} {'TPS':>6} {'n':>4} {'err%':>8} {'ve_old':>8} {'ve_new':>8} {'delta%':>8}")
for r in wot:
    print(
        f"{r['RPM']:>6} {r['tps_pct']:>6} {r['n_samples']:>4} "
        f"{r['median_err_pct']:>8} {r['ve_base_pct']:>8} {r['ve_new_pct']:>8} "
        f"{r['delta_pct']:>8}"
    )

all_trims = [
    float(r["delta_pct"]) for r in rows if r["cylinder"] == "front"
]
if all_trims:
    print()
    print(
        f"All-cell trim range: min={min(all_trims):+.2f}%, "
        f"median={sorted(all_trims)[len(all_trims) // 2]:+.2f}%, "
        f"max={max(all_trims):+.2f}%, count={len(all_trims)}"
    )
