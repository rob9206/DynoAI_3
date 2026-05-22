"""Plan a targeted VE smoothing pass on top of iter_6 (annotate-only).

Scope:
    rows: 1.5 <= rpm/1000 <= 5.0          (cruise + part-throttle)
    cols: 0  <= tps_pct  <= 60            (skip 80/100 columns)

Algorithm (per cell):
    1. Skip cells outside scope (locked).
    2. Skip cells inside scope if their col axis is 80 or 100 (locked).
    3. Compute the 3x3 neighbour mean (excluding the center cell). Use only
       neighbours that are themselves inside the scope; locked neighbours can
       still contribute but we never WRITE locked cells.
    4. Compute residual = cell - neighbour_mean.
    5. If |residual| < DEADBAND_PCT * |neighbour_mean|, leave alone.
    6. Otherwise propose new = cell - alpha * residual where alpha = 0.5.
       This nudges spikes halfway toward the local mean.
    7. Hard cap the per-cell change to +/- MAX_CHANGE_PCT * cell_base.

Outputs (annotate-only, NO .pvv written):
    - vehicles/.../iter_8/plan/ve_smoothing_proposal.csv  (cyl, rpm, tps, base, new, delta, delta_pct)
    - vehicles/.../iter_8/plan/ve_smoothing_summary.md    (counts, biggest changes, locks)

This script DOES NOT modify any .pvv. It is for review only. After review,
generate_iter8_patch.py (separate file) will apply the same algorithm and
emit the patched tune.
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"
PLAN_DIR = ITER_DIR / "iter_8" / "plan"

VE_TABLES = ("VE (TPS based/Front Cyl)", "VE (TPS based/Rear Cyl)")

RPM_LO, RPM_HI = 1.5, 5.0
TPS_LO, TPS_HI = 0.0, 60.0
DEADBAND_PCT = 0.015
ALPHA = 0.5
MAX_CHANGE_PCT = 0.03


def read_table(p: Path, name: str) -> tuple[list[float], list[float], list[list[float]]]:
    root = ET.parse(str(p)).getroot()
    item = next(it for it in root.findall("Item") if it.get("name") == name)
    cols = item.find("Columns")
    rows = item.find("Rows")
    col_axis = [float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for row in rows.findall("Row"):
        row_axis.append(float(row.get("label", "0") or "0"))
        grid.append([float(c.get("value", "0") or "0") for c in row.findall("Cell")])
    return row_axis, col_axis, grid


def in_scope(rpm_k: float, tps: float) -> bool:
    return RPM_LO <= rpm_k <= RPM_HI and TPS_LO <= tps <= TPS_HI


def neighbour_mean_3x3(grid: list[list[float]], r: int, c: int) -> float:
    R = len(grid)
    C = len(grid[0])
    s, n = 0.0, 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < R and 0 <= cc < C:
                s += grid[rr][cc]
                n += 1
    return s / n if n else grid[r][c]


def plan_smoothing(
    row_axis: list[float],
    col_axis: list[float],
    grid: list[list[float]],
) -> list[tuple[int, int, float, float, float, float, float, str]]:
    """Return list of (r, c, rpm, tps, base, new, delta, status)."""
    out: list[tuple[int, int, float, float, float, float, float, str]] = []
    R = len(grid)
    C = len(grid[0])
    for r in range(R):
        rpm_k = row_axis[r]
        for c in range(C):
            tps = col_axis[c]
            base = grid[r][c]
            if not in_scope(rpm_k, tps):
                continue
            mean = neighbour_mean_3x3(grid, r, c)
            if abs(mean) < 1e-9:
                continue
            residual = base - mean
            if abs(residual) < DEADBAND_PCT * abs(mean):
                continue
            proposed = base - ALPHA * residual
            cap = MAX_CHANGE_PCT * abs(base)
            change = max(-cap, min(cap, proposed - base))
            new = base + change
            out.append(
                (r, c, rpm_k * 1000.0, tps, base, new, new - base, "smooth")
            )
    return out


def write_csv(path: Path, cyl_rows: dict[str, list[tuple[int, int, float, float, float, float, float, str]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cyl", "row_idx", "col_idx", "rpm", "tps_pct", "ve_base", "ve_new", "delta", "delta_pct"])
        for cyl, rows in cyl_rows.items():
            for r, c, rpm, tps, b, n, d, _ in rows:
                pct = (d / b * 100.0) if abs(b) > 1e-9 else 0.0
                w.writerow([cyl, r, c, int(rpm), tps, f"{b:.2f}", f"{n:.2f}", f"{d:+.3f}", f"{pct:+.2f}"])


def write_summary(
    path: Path,
    cyl_rows: dict[str, list[tuple[int, int, float, float, float, float, float, str]]],
):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# iter_8 VE Smoothing Proposal (annotate-only)",
        "",
        f"Base: iter_6_patched.pvv",
        "",
        "## Scope",
        "",
        f"- rows: RPM {int(RPM_LO * 1000)} -- {int(RPM_HI * 1000)} (cruise + part-throttle)",
        f"- cols: TPS {int(TPS_LO)}% -- {int(TPS_HI)}% (excludes WOT 80/100 columns)",
        "",
        "## Algorithm",
        "",
        f"- 3x3 neighbour mean (center excluded)",
        f"- deadband: |residual| < {DEADBAND_PCT * 100:.1f}% of neighbour mean -- skip",
        f"- nudge: new = cell - {ALPHA} * residual (halfway toward neighbours)",
        f"- per-cell change cap: \u00b1{MAX_CHANGE_PCT * 100:.1f}% of cell base",
        "",
        "## Locks (NOT touched, reasons)",
        "",
        "- TPS 80% / TPS 100% columns: WOT cells, validated by iter_6 dyno data (95 hp, AFR 12.0-12.8). Smoothing breaks AFR ground truth.",
        "- RPM <= 1000: idle / throttle blip area, no measurement evidence.",
        "- RPM >= 5500: top of rev range; 6500 row is hard-clipped at 81/83.5 rev-limit floor.",
        "",
        "## Proposed change counts",
        "",
    ]
    for cyl, rows in cyl_rows.items():
        rows_sorted = sorted(rows, key=lambda x: -abs(x[6]))
        lines.append(f"### {cyl}")
        lines.append("")
        lines.append(f"- cells changed: {len(rows)}")
        if rows:
            avg = sum(abs(d) for _, _, _, _, _, _, d, _ in rows) / len(rows)
            mx = max(abs(d) for _, _, _, _, _, _, d, _ in rows)
            lines.append(f"- avg |delta|: {avg:.2f}  max |delta|: {mx:.2f}")
        lines.append("")
        lines.append("Top 15 changes by |delta|:")
        lines.append("")
        lines.append("| RPM | TPS | base | new | delta | delta_pct |")
        lines.append("|---|---|---|---|---|---|")
        for r, c, rpm, tps, b, n, d, _ in rows_sorted[:15]:
            pct = (d / b * 100.0) if abs(b) > 1e-9 else 0.0
            lines.append(
                f"| {int(rpm)} | {int(tps)} | {b:.2f} | {n:.2f} | {d:+.2f} | {pct:+.2f}% |"
            )
        lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("ANNOTATE ONLY. No .pvv emitted. Review the proposal before running")
    lines.append("`tools/generate_iter8_patch.py`.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    cyl_rows: dict[str, list] = {}
    for tbl in VE_TABLES:
        rax, cax, grid = read_table(ITER6, tbl)
        rows = plan_smoothing(rax, cax, grid)
        cyl_rows[tbl] = rows
        print(f"{tbl}: {len(rows)} cells proposed for smoothing")

    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = PLAN_DIR / "ve_smoothing_proposal.csv"
    md_path = PLAN_DIR / "ve_smoothing_summary.md"
    write_csv(csv_path, cyl_rows)
    write_summary(md_path, cyl_rows)
    print(f"\nplan written:")
    print(f"  {csv_path}")
    print(f"  {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
