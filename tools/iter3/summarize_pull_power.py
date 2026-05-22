"""Summarize peak power/torque and AFR-channel health from DWRT TXT pulls."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

DEFAULT_PULLS_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_3\pulls"
)

COL_TIME = "Time"
COL_POWER = "(DWRT CPU) Power"
COL_TORQUE = "(DWRT CPU) Torque"
COL_RPM = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_GEAR = "(DWRT CPU) Gear Ratio"


def _to_float(value) -> float:
    try:
        if value is None:
            return math.nan
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return math.nan
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def summarize_file(path: Path) -> dict:
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    rows = df.to_dict(orient="records")
    best: dict | None = None
    lc2_total = 0
    lc2_pegged = 0
    gear_values: list[float] = []

    for row in rows:
        power = _to_float(row.get(COL_POWER))
        time_s = _to_float(row.get(COL_TIME))
        torque = _to_float(row.get(COL_TORQUE))
        rpm_k = _to_float(row.get(COL_RPM))
        map_kpa = _to_float(row.get(COL_MAP))
        lc2 = _to_float(row.get(COL_LC2))
        gear = _to_float(row.get(COL_GEAR))

        if not math.isnan(gear):
            gear_values.append(gear)

        if not math.isnan(lc2):
            lc2_total += 1
            if lc2 >= 22.38:
                lc2_pegged += 1

        if math.isnan(power):
            continue
        if best is None or power > best["power"]:
            best = {
                "power": power,
                "time_s": time_s,
                "torque": torque,
                "rpm_k": rpm_k,
                "map_kpa": map_kpa,
                "lc2": lc2,
            }

    if best is None:
        return {"name": path.name, "ok": False}

    return {
        "name": path.name,
        "ok": True,
        "peak_hp": best["power"],
        "peak_tq": best["torque"],
        "peak_time_s": best["time_s"],
        "peak_rpm": best["rpm_k"] * 1000.0 if not math.isnan(best["rpm_k"]) else math.nan,
        "peak_map_kpa": best["map_kpa"],
        "peak_lc2": best["lc2"],
        "lc2_pegged_pct": (lc2_pegged / lc2_total * 100.0) if lc2_total else 0.0,
        "avg_gear_ratio": (sum(gear_values) / len(gear_values)) if gear_values else math.nan,
        "samples": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_PULLS_DIR)
    args = parser.parse_args()

    files = sorted(args.dir.glob("*.txt"))
    if not files:
        print(f"No .txt pulls found in {args.dir}")
        return 1

    print(f"Found {len(files)} txt pull files in {args.dir}")
    print("")

    summaries = [summarize_file(f) for f in files]
    summaries = [s for s in summaries if s["ok"]]
    summaries.sort(key=lambda s: s["peak_hp"], reverse=True)

    for s in summaries:
        print(
            f"{s['name']}: "
            f"HP={s['peak_hp']:.2f}, TQ={s['peak_tq']:.2f}, "
            f"RPM={s['peak_rpm']:.0f}, MAP={s['peak_map_kpa']:.1f}, "
            f"LC2@peak={s['peak_lc2']:.3f}, LC2_peg={s['lc2_pegged_pct']:.1f}%, "
            f"gear~{s['avg_gear_ratio']:.2f}, n={s['samples']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
