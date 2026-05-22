"""READ-ONLY audit of the three relevant PVV tunes: v3 (flashed), v4, v5 (staged).
Reports injector_size, engine_displacement scalars, VE table extents (front+rear),
count of cells at/over the soft cap, and per-cell delta vs the baked baseline (v3).
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from pathlib import Path

TUNES = {
    "baked": r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_baked.pvv",
    "v3_flashed": r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_emergency_rich_v3_conservative.pvv",
    "v4_staged": r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_emergency_rich_v4_stepup.pvv",
    "v5_staged": r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_emergency_rich_v5_stepup.pvv",
}

SCALARS = ["tbl_injector_size", "tbl_engine_displacement"]
VE_TABLES = ["tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"]


def find(root, item_id):
    for it in root.findall("Item"):
        if it.get("id") == item_id:
            return it
    return None


def scalar(root, item_id):
    it = find(root, item_id)
    if it is None:
        return None
    cell = it.find("./Rows/Row/Cell")
    return float(cell.get("value")) if cell is not None else None


def table(root, item_id):
    it = find(root, item_id)
    if it is None:
        return None
    cols = [float(c.get("label", "0")) for c in it.findall("./Columns/Col")]
    grid = []
    rows = []
    for r in it.findall("./Rows/Row"):
        rows.append(float(r.get("label", "0")))
        grid.append([float(c.get("value", "0")) for c in r.findall("Cell")])
    return rows, cols, grid


def summarise(name, path):
    if not Path(path).exists():
        print(name, "MISSING", path)
        return None
    root = ET.parse(path).getroot()
    inj = scalar(root, "tbl_injector_size")
    cid = scalar(root, "tbl_engine_displacement")
    print()
    print(f"=== {name} :: {Path(path).name} ===")
    print(f"  injector_size: {inj}    engine_displacement(CID): {cid}")
    tables = {}
    for tid in VE_TABLES:
        t = table(root, tid)
        if t is None:
            print(f"  {tid}: MISSING")
            continue
        rows, cols, grid = t
        flat = [v for row in grid for v in row]
        # Loaded region: rpm row label * 1000 >= 3000 and tps column >= 50
        loaded = []
        for ri, r in enumerate(rows):
            rpm = r * 1000.0
            for ci, c in enumerate(cols):
                if rpm >= 3000 and c >= 50:
                    loaded.append(grid[ri][ci])
        # cap candidates
        cap_candidates = [115, 120, 125, 130, 135, 140, 145, 150, 155]
        max_v = max(flat)
        min_v = min(flat)
        # nearest cap = ceiling of max
        suspect_cap = next((cap for cap in cap_candidates if max_v <= cap + 0.01), None)
        count_at_max = sum(1 for v in flat if v >= max_v - 0.01)
        loaded_at_max = sum(1 for v in loaded if v >= max_v - 0.01)
        print(
            f"  {tid}: max={max_v:.2f} min={min_v:.2f}  cells={len(flat)}  "
            f"loaded_cells={len(loaded)}  loaded_at_max={loaded_at_max}/{len(loaded)}  total_at_max={count_at_max}"
        )
        tables[tid] = (rows, cols, grid)
    return inj, cid, tables


by_name = {}
for n, p in TUNES.items():
    by_name[n] = summarise(n, p)

# Delta of v4 vs v3 (cell-by-cell), v5 vs v3, v5 vs v4 in loaded region
def diff(label, ref_name, new_name):
    ref = by_name.get(ref_name)
    new = by_name.get(new_name)
    if not ref or not new:
        return
    _, _, ref_tab = ref
    _, _, new_tab = new
    print()
    print(f"=== Delta {new_name} vs {ref_name} (loaded region rpm>=3000 & tps>=50) ===")
    for tid in VE_TABLES:
        rows, cols, rg = ref_tab[tid]
        _, _, ng = new_tab[tid]
        diffs = []
        pct_diffs = []
        worst_pct = 0.0
        worst_at = None
        for ri, r in enumerate(rows):
            rpm = r * 1000.0
            for ci, c in enumerate(cols):
                if rpm >= 3000 and c >= 50:
                    rv = rg[ri][ci]
                    nv = ng[ri][ci]
                    d = nv - rv
                    diffs.append(d)
                    p = (d / rv) * 100 if rv > 0 else float("nan")
                    pct_diffs.append(p)
                    if abs(p) > abs(worst_pct):
                        worst_pct = p
                        worst_at = (int(rpm), c)
        if diffs:
            max_d = max(diffs)
            min_d = min(diffs)
            over10 = sum(1 for p in pct_diffs if abs(p) > 10.0)
            over15 = sum(1 for p in pct_diffs if abs(p) > 15.0)
            over25 = sum(1 for p in pct_diffs if abs(p) > 25.0)
            print(
                f"  {tid}: cells={len(diffs)}  max_delta={max_d:+.2f}  min_delta={min_d:+.2f}  worst_pct={worst_pct:+.1f}% at rpm={worst_at[0]} tps={worst_at[1]}"
            )
            print(f"    Per-cell pct over thresholds: >10% n={over10}  >15% n={over15}  >25% n={over25}")


diff("delta_v3_vs_baked", "baked", "v3_flashed")
diff("delta_v4_vs_v3", "v3_flashed", "v4_staged")
diff("delta_v5_vs_v3", "v3_flashed", "v5_staged")
diff("delta_v5_vs_v4", "v4_staged", "v5_staged")
