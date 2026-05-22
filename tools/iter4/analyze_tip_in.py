"""Analyze throttle tip-in transients from DynoWare RT pulls.

Detects each tip-in event (TPS rising from <10% to >=80% within ~0.5s), then
extracts the LC2 AFR trace in the 1.5-second window starting at the trigger.
Flags lean spikes (>14.5), rich overshoots (<11.0), and the post-event tail.
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
COL_RPM = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"

TPS_LOW = 10.0
TPS_HIGH = 80.0
TIP_IN_MAX_DURATION_S = 0.6
WINDOW_AFTER_S = 1.5
PEG_VOLTS = 22.38


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


def find_tip_in_events(df: pd.DataFrame) -> list[tuple[int, int, float, float]]:
    """Return list of (start_idx, trigger_idx, t_start, t_trigger) tuples."""
    events: list[tuple[int, int, float, float]] = []
    rows = df.to_dict(orient="records")
    n = len(rows)
    i = 0
    while i < n:
        tps_i = f(rows[i].get(COL_TPS))
        t_i = f(rows[i].get(COL_TIME))
        if math.isnan(tps_i) or math.isnan(t_i) or tps_i >= TPS_LOW:
            i += 1
            continue
        start_idx = i
        t_start = t_i
        j = i + 1
        triggered = False
        while j < n:
            t_j = f(rows[j].get(COL_TIME))
            tps_j = f(rows[j].get(COL_TPS))
            if math.isnan(t_j) or math.isnan(tps_j):
                j += 1
                continue
            if t_j - t_start > TIP_IN_MAX_DURATION_S:
                break
            if tps_j >= TPS_HIGH:
                events.append((start_idx, j, t_start, t_j))
                triggered = True
                break
            j += 1
        if triggered:
            i = j + 1
            while i < n:
                tps_k = f(rows[i].get(COL_TPS))
                if not math.isnan(tps_k) and tps_k < TPS_LOW:
                    break
                i += 1
        else:
            i += 1
    return events


def analyze_event(df: pd.DataFrame, trigger_idx: int) -> dict:
    rows = df.to_dict(orient="records")
    t_trigger = f(rows[trigger_idx].get(COL_TIME))
    lc2_trace: list[tuple[float, float]] = []
    rpm_at_trigger = f(rows[trigger_idx].get(COL_RPM))
    map_at_trigger = f(rows[trigger_idx].get(COL_MAP))
    pegged_in_window = False
    for k in range(trigger_idx, len(rows)):
        t_k = f(rows[k].get(COL_TIME))
        if math.isnan(t_k) or t_k - t_trigger > WINDOW_AFTER_S:
            break
        lc2 = f(rows[k].get(COL_LC2))
        if math.isnan(lc2):
            continue
        if lc2 >= PEG_VOLTS:
            pegged_in_window = True
            continue
        lc2_trace.append((t_k - t_trigger, lc2))

    if not lc2_trace:
        return {"ok": False, "n": 0, "pegged": pegged_in_window}

    lc2_vals = [v for _, v in lc2_trace]
    early = [v for t, v in lc2_trace if t <= 0.3]
    mid = [v for t, v in lc2_trace if 0.3 < t <= 0.8]
    late = [v for t, v in lc2_trace if t > 0.8]
    return {
        "ok": True,
        "n": len(lc2_trace),
        "rpm_k_at_trigger": rpm_at_trigger,
        "map_at_trigger": map_at_trigger,
        "min_lc2": min(lc2_vals),
        "max_lc2": max(lc2_vals),
        "lc2_0_300ms": (sum(early) / len(early)) if early else math.nan,
        "lc2_300_800ms": (sum(mid) / len(mid)) if mid else math.nan,
        "lc2_800_1500ms": (sum(late) / len(late)) if late else math.nan,
        "pegged": pegged_in_window,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = ap.parse_args()

    files = sorted(args.dir.glob("*.txt"))
    if not files:
        print(f"No .txt pulls in {args.dir}")
        return 1

    print(f"Tip-in analysis ({len(files)} files in {args.dir.name})")
    print(
        f"  detection: TPS<{TPS_LOW}% -> >={TPS_HIGH}% within {TIP_IN_MAX_DURATION_S}s; "
        f"window {WINDOW_AFTER_S}s; pegged>={PEG_VOLTS}V"
    )
    print()

    all_events: list[dict] = []
    for p in files:
        df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        events = find_tip_in_events(df)
        if not events:
            continue
        print(f"{p.name}: {len(events)} tip-in event(s)")
        for k, (_, trig, t_start, t_trig) in enumerate(events):
            res = analyze_event(df, trig)
            res["file"] = p.name
            res["event_idx"] = k
            res["t_trigger_s"] = t_trig
            res["tip_in_duration_s"] = t_trig - t_start
            all_events.append(res)
            if not res.get("ok"):
                print(
                    f"  [{k}] t={t_trig:.2f}s dur={res.get('tip_in_duration_s', 0):.2f}s  "
                    f"-- no valid LC2 in window (pegged={res.get('pegged')})"
                )
                continue
            rpm = (
                f"{res['rpm_k_at_trigger'] * 1000:.0f}"
                if not math.isnan(res["rpm_k_at_trigger"])
                else "n/a"
            )
            map_v = (
                f"{res['map_at_trigger']:.0f}"
                if not math.isnan(res["map_at_trigger"])
                else "n/a"
            )
            print(
                f"  [{k}] t={t_trig:5.2f}s dur={res['tip_in_duration_s']:.2f}s "
                f"rpm={rpm:>5s} map={map_v:>3s} "
                f"min={res['min_lc2']:5.2f} max={res['max_lc2']:5.2f}  "
                f"0-300ms={res['lc2_0_300ms']:5.2f}  "
                f"300-800ms={res['lc2_300_800ms']:5.2f}  "
                f"800-1500ms={res['lc2_800_1500ms']:5.2f}  "
                f"pegged={'Y' if res['pegged'] else 'n'}"
            )

    valid = [e for e in all_events if e.get("ok")]
    if not valid:
        print("\nNo valid tip-in events found.")
        return 2

    print(f"\nAggregate over {len(valid)} valid tip-in events:")
    for k in ("lc2_0_300ms", "lc2_300_800ms", "lc2_800_1500ms"):
        vals = [e[k] for e in valid if not math.isnan(e[k])]
        if not vals:
            continue
        vals_s = sorted(vals)
        print(
            f"  {k}: n={len(vals)}  min={min(vals):.2f}  "
            f"median={vals_s[len(vals_s) // 2]:.2f}  max={max(vals):.2f}"
        )

    leans = [e for e in valid if e["max_lc2"] >= 14.5]
    riches = [e for e in valid if e["min_lc2"] <= 11.0]
    pegged = [e for e in all_events if e.get("pegged")]
    print()
    print(f"  events with lean spike (max LC2 >= 14.5): {len(leans)} / {len(valid)}")
    print(f"  events with rich overshoot (min LC2 <= 11.0): {len(riches)} / {len(valid)}")
    print(f"  events with LC2 pegging in window: {len(pegged)} / {len(all_events)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
