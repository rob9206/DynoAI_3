#!/usr/bin/env python3
"""Plot HP and torque (ft-lb) vs engine RPM from PowerVision / DynoWare CSV exports.

Torque is computed as 5252 * HP / RPM (rear wheel, same convention as dyno sheets).
Uses column names from the header so 105/106-column variants both work.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def _find_col(header: list[str], name: str) -> int:
    for i, c in enumerate(header):
        if c.strip() == name:
            return i
    raise KeyError(f"column not found: {name!r}")


def _f(row: list[str], idx: int) -> float | None:
    if idx >= len(row):
        return None
    v = (row[idx] or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_series(
    path: Path,
    *,
    min_rpm: float = 2000.0,
    min_tps: float = 40.0,
) -> tuple[list[float], list[float], list[float]]:
    """Return (rpm, hp, tq_ftlb) filtered to meaningful load."""
    rpm_out: list[float] = []
    hp_out: list[float] = []
    tq_out: list[float] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = [c.strip() for c in next(rdr)]
        i_rpm = _find_col(header, "(Harley - ECU Type 14 SW Level 141) Engine Speed")
        i_hp = _find_col(header, "(DWRT CPU) Power")
        i_tps = _find_col(header, "(Harley - ECU Type 14 SW Level 141) Throttle Position")
        for row in rdr:
            rpme = _f(row, i_rpm)
            hp = _f(row, i_hp)
            tps = _f(row, i_tps)
            if rpme is None or hp is None or rpme <= 0:
                continue
            rpm = rpme * 1000.0
            if rpm < min_rpm:
                continue
            if tps is not None and tps < min_tps:
                continue
            if hp <= 0:
                continue
            tq = 5252.0 * hp / rpm
            rpm_out.append(rpm)
            hp_out.append(hp)
            tq_out.append(tq)
    return rpm_out, hp_out, tq_out


def plot_group(
    paths: list[tuple[Path, str]],
    title: str,
    out_path: Path,
) -> None:
    fig, (ax_hp, ax_tq) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for path, label in paths:
        if not path.exists():
            continue
        rpm, hp, tq = load_series(path)
        if not rpm:
            continue
        ax_hp.plot(rpm, hp, label=label, linewidth=1.4, alpha=0.85)
        ax_tq.plot(rpm, tq, label=label, linewidth=1.4, alpha=0.85)

    ax_hp.set_ylabel("Horsepower (rwhp)")
    ax_hp.set_title(title)
    ax_hp.grid(True, alpha=0.3)
    ax_hp.legend(loc="best", fontsize=8)

    ax_tq.set_ylabel("Torque (ft-lb, from HP & RPM)")
    ax_tq.set_xlabel("Engine RPM")
    ax_tq.grid(True, alpha=0.3)
    ax_tq.legend(loc="best", fontsize=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--session-root",
        type=Path,
        default=Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline"),
        help="Session directory under workspace",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: <session>/charts)",
    )
    args = p.parse_args()
    session = args.session_root.resolve()
    out_dir = (args.out_dir or (session / "charts")).resolve()

    iter0 = session / "iterations" / "iter_0" / "pulls"
    iter1 = session / "iterations" / "iter_1" / "pulls"

    plot_group(
        [
            (iter0 / "4thgear_baseline_pull_10.csv", "iter0 pull 10"),
            (iter0 / "4thgear_baseline_pull_12.csv", "iter0 pull 12"),
            (iter0 / "4thgear_baseline_pull_13.csv", "iter0 pull 13"),
        ],
        "Baseline (pre-reflash) — 4th gear WOT — HP & torque vs RPM",
        out_dir / "hp_tq_baseline_iter0.png",
    )
    plot_group(
        [
            (iter1 / "postreflash_pull_14.csv", "iter1 pull 14"),
            (iter1 / "postreflash_pull_15.csv", "iter1 pull 15"),
            (iter1 / "postreflash_pull_16.csv", "iter1 pull 16"),
            (iter1 / "postreflash_pull_17.csv", "iter1 pull 17"),
            (iter1 / "postreflash_5thgear.csv", "iter1 5th gear"),
        ],
        "Post-reflash — 4th + 5th gear — HP & torque vs RPM",
        out_dir / "hp_tq_postreflash_iter1.png",
    )
    # Combined overlay: best representative from each phase
    plot_group(
        [
            (iter0 / "4thgear_baseline_pull_13.csv", "baseline pull 13"),
            (iter1 / "postreflash_pull_17.csv", "post-reflash pull 17 (4th)"),
            (iter1 / "postreflash_5thgear.csv", "post-reflash 5th"),
        ],
        "Overlay — baseline vs post-reflash (selected pulls)",
        out_dir / "hp_tq_overlay_compare.png",
    )

    print(f"Wrote charts to {out_dir}:")
    for name in (
        "hp_tq_baseline_iter0.png",
        "hp_tq_postreflash_iter1.png",
        "hp_tq_overlay_compare.png",
    ):
        fp = out_dir / name
        print(f"  {fp}")


if __name__ == "__main__":
    main()
