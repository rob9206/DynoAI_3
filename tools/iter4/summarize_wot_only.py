"""Summarize peak HP from DWRT pulls, restricted to true WOT samples only.

A 'true WOT sample' requires MAP >= 85 kPa AND TPS >= 80% so we don't mistake
decel/overrun moments (closed throttle, drum spinning bike) for engine power.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

DEFAULT_DIR = Path(
    r"vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_4\pulls"
)

COL_TIME = "Time"
COL_POWER = "(DWRT CPU) Power"
COL_TORQUE = "(DWRT CPU) Torque"
COL_RPM = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_GEAR = "(DWRT CPU) Gear Ratio"

MIN_MAP_KPA = 85.0
MIN_TPS_PCT = 80.0


def f(value) -> float:
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


def summarize(path: Path) -> dict:
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    best: dict | None = None
    lc2_in_wot: list[float] = []
    afr_at_peak_rpm_band: list[float] = []
    n_wot = 0
    n_total = 0

    for row in df.to_dict(orient="records"):
        n_total += 1
        power = f(row.get(COL_POWER))
        rpm_k = f(row.get(COL_RPM))
        map_k = f(row.get(COL_MAP))
        tps = f(row.get(COL_TPS))
        lc2 = f(row.get(COL_LC2))
        torque = f(row.get(COL_TORQUE))
        gear = f(row.get(COL_GEAR))

        is_wot = (
            (not math.isnan(map_k) and map_k >= MIN_MAP_KPA)
            and (not math.isnan(tps) and tps >= MIN_TPS_PCT)
        )
        if not is_wot:
            continue
        n_wot += 1

        if not math.isnan(lc2):
            lc2_in_wot.append(lc2)
            if not math.isnan(rpm_k) and 3.0 <= rpm_k <= 5.5:
                afr_at_peak_rpm_band.append(lc2)

        if math.isnan(power):
            continue
        if best is None or power > best["power"]:
            best = {
                "power": power,
                "rpm_k": rpm_k,
                "map_kpa": map_k,
                "tps_pct": tps,
                "lc2": lc2,
                "torque": torque,
                "gear": gear,
            }

    if best is None:
        return {"name": path.name, "ok": False, "n_wot": n_wot, "n_total": n_total}

    lc2_clean = [v for v in lc2_in_wot if 5.0 < v < 22.38]
    afr_band_clean = [v for v in afr_at_peak_rpm_band if 5.0 < v < 22.38]
    return {
        "name": path.name,
        "ok": True,
        "peak_hp_wot": best["power"],
        "peak_tq_wot": best["torque"],
        "peak_rpm": best["rpm_k"] * 1000.0 if not math.isnan(best["rpm_k"]) else math.nan,
        "peak_map": best["map_kpa"],
        "peak_tps": best["tps_pct"],
        "peak_lc2": best["lc2"],
        "lc2_wot_mean": (sum(lc2_clean) / len(lc2_clean)) if lc2_clean else math.nan,
        "lc2_3k_5k5_mean": (sum(afr_band_clean) / len(afr_band_clean))
        if afr_band_clean
        else math.nan,
        "n_wot": n_wot,
        "n_total": n_total,
        "avg_gear_ratio": best["gear"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = ap.parse_args()

    files = sorted(args.dir.glob("*.txt"))
    if not files:
        print(f"No .txt pulls in {args.dir}")
        return 1

    print(f"WOT-only summary ({len(files)} files in {args.dir.name})")
    print(f"  filter: MAP>={MIN_MAP_KPA} kPa AND TPS>={MIN_TPS_PCT}%")
    print()

    summaries = [summarize(f_) for f_ in files]
    ok = [s for s in summaries if s.get("ok") and s["n_wot"] >= 10]
    skipped = [s for s in summaries if not (s.get("ok") and s["n_wot"] >= 10)]

    ok.sort(key=lambda s: s["peak_hp_wot"], reverse=True)
    for s in ok:
        print(
            f"  {s['name']:42s} HP={s['peak_hp_wot']:5.2f} @ RPM={s['peak_rpm']:.0f} "
            f"MAP={s['peak_map']:.0f} TPS={s['peak_tps']:.0f} "
            f"LC2@peak={s['peak_lc2']:5.2f} "
            f"LC2_WOT_avg={s['lc2_wot_mean']:5.2f} "
            f"LC2_3-5.5k={s['lc2_3k_5k5_mean']:5.2f} "
            f"gear~{s['avg_gear_ratio']:.1f} n_wot={s['n_wot']}"
        )

    if skipped:
        print()
        print(f"Skipped {len(skipped)} files (no/few WOT samples):")
        for s in skipped:
            print(f"  {s['name']}  n_wot={s.get('n_wot', 0)} n_total={s.get('n_total', 0)}")

    if ok:
        hps = [s["peak_hp_wot"] for s in ok]
        lc2s = [s["lc2_3k_5k5_mean"] for s in ok if not math.isnan(s["lc2_3k_5k5_mean"])]
        print()
        print(f"WOT peak HP across {len(hps)} clean pulls:")
        print(f"  min={min(hps):.2f}  median={sorted(hps)[len(hps) // 2]:.2f}  max={max(hps):.2f}")
        if lc2s:
            print(f"WOT LC2 3000-5500 RPM band across {len(lc2s)} pulls:")
            print(
                f"  min={min(lc2s):.2f}  median={sorted(lc2s)[len(lc2s) // 2]:.2f}  "
                f"max={max(lc2s):.2f}  (target ~12.8)"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
