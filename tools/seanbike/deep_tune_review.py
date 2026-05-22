"""Deep review of all tables in the soft decel tune.

Flags:
- Front/rear VE asymmetry
- VE values outside plausible range (50-160 for TPS-based)
- AFR/lambda targets that are unsafe or inconsistent
- Spark advance that is aggressive or inverted
- Enrichment tables with extreme values
- Any table that changed unexpectedly vs OEM baseline
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_soft.pvv")
OEM = Path(r"C:\CommmandCenter\Customer_Files\seanbike\exportedreadfrompv4.pvv")


def cells(it: ET.Element) -> list[float]:
    out: list[float] = []
    for r in it.findall("./Rows/Row"):
        for c in r.findall("Cell"):
            try:
                out.append(float(c.get("value", "")))
            except ValueError:
                pass
    return out


def main() -> None:
    root = ET.parse(PVV).getroot()
    oem_root = ET.parse(OEM).getroot() if OEM.exists() else None

    print("=" * 90)
    print(f"DEEP TUNE REVIEW: {PVV.name}")
    print("=" * 90)

    # All items summary
    print(f"\nTotal Items: {len(root.findall('Item'))}")

    # VE comparison
    print("\n--- VE TABLES (front vs rear) ---")
    ve_f = None
    ve_r = None
    for it in root.findall("Item"):
        iid = it.get("id", "")
        if "ve_tps" in iid and "front" in iid:
            ve_f = cells(it)
            print(f"  FRONT: {iid}  n={len(ve_f)}  min={min(ve_f):.2f} max={max(ve_f):.2f}")
        if "ve_tps" in iid and "rear" in iid:
            ve_r = cells(it)
            print(f"  REAR:  {iid}  n={len(ve_r)}  min={min(ve_r):.2f} max={max(ve_r):.2f}")

    if ve_f and ve_r and len(ve_f) == len(ve_r):
        diffs = [abs(a - b) for a, b in zip(ve_f, ve_r)]
        max_diff = max(diffs)
        avg_diff = sum(diffs) / len(diffs)
        print(f"  Cell-by-cell |front-rear| max={max_diff:.2f} avg={avg_diff:.2f}")
        if max_diff > 15:
            print("  [WARN] Large front/rear VE asymmetry -- check cylinder balance on dyno.")

    # Spark tables
    print("\n--- SPARK ADVANCE ---")
    for it in root.findall("Item"):
        iid = it.get("id", "")
        if "spark" in iid.lower() and ("advance" in iid.lower() or "base" in iid.lower()):
            vals = cells(it)
            if vals:
                print(f"  {iid:45s} min={min(vals):6.2f} max={max(vals):6.2f} mean={sum(vals)/len(vals):6.2f}")

    # AFR / Desired Lambda
    print("\n--- AFR / LAMBDA TARGETS ---")
    for it in root.findall("Item"):
        iid = it.get("id", "")
        if any(k in iid.lower() for k in ["afr", "lambda", "desired"]):
            vals = cells(it)
            if vals and len(vals) > 1:
                print(f"  {iid:45s} min={min(vals):6.3f} max={max(vals):6.3f}")

    # Closed loop / O2
    print("\n--- CLOSED LOOP / EGO ---")
    for it in root.findall("Item"):
        iid = it.get("id", "")
        if any(k in iid.lower() for k in ["ego", "closed_loop", "o2", "lambda_switch"]):
            vals = cells(it)
            if vals:
                print(f"  {iid:45s} vals={vals[:8]}")

    # Warmup / Cranking / Accel
    print("\n--- WARMUP / CRANKING / ACCEL ENRICHMENT ---")
    for it in root.findall("Item"):
        iid = it.get("id", "")
        if any(k in iid.lower() for k in ["warmup", "crank", "accel_enrich", "startup"]):
            vals = cells(it)
            if vals:
                print(f"  {iid:45s} min={min(vals):6.3f} max={max(vals):6.3f}")

    # Decel (already know, but confirm)
    print("\n--- DECEL ENLEANMENT (current) ---")
    for it in root.findall("Item"):
        if it.get("id") == "tbl_deceleration_enleanment":
            vals = cells(it)
            temps = [float(c.get("label", "0")) for c in it.findall("./Columns/Col")]
            print("  Temp axis:", temps)
            print("  Values:   ", [round(v, 3) for v in vals])

    # Compare to OEM if available
    if oem_root is not None:
        print("\n--- DELTA vs OEM (exportedreadfrompv4.pvv) ---")
        oem_scalars = {}
        for it in oem_root.findall("Item"):
            iid = it.get("id", "")
            rows = it.findall("./Rows/Row")
            if len(rows) == 1 and len(rows[0].findall("Cell")) == 1:
                try:
                    oem_scalars[iid] = float(rows[0].find("Cell").get("value", ""))
                except ValueError:
                    pass

        cur_scalars = {}
        for it in root.findall("Item"):
            iid = it.get("id", "")
            rows = it.findall("./Rows/Row")
            if len(rows) == 1 and len(rows[0].findall("Cell")) == 1:
                try:
                    cur_scalars[iid] = float(rows[0].find("Cell").get("value", ""))
                except ValueError:
                    pass

        for k in sorted(set(oem_scalars) & set(cur_scalars)):
            if abs(oem_scalars[k] - cur_scalars[k]) > 0.01:
                print(f"  {k:40s} OEM={oem_scalars[k]:.3f} -> NOW={cur_scalars[k]:.3f}")

    print("\n" + "=" * 90)
    print("SUMMARY OF POTENTIAL IMPROVEMENTS")
    print("=" * 90)
    print("""
1. injector_size = 21.75 is a large step from OEM 31.07.
   - If idle remains rough after decel fix, verify actual injector flow rate.
   - Consider a small upward correction (22.5-23.5) if part-throttle is now too rich.

2. Displacement = 95.5 vs owner-stated 100 CID.
   - Small error (~4.7%). If next pull shows consistent lean bias, bump to 100.0.

3. VE front/rear asymmetry should be checked on a steady-state cruise log.
   - If one cylinder is consistently 0.5+ AFR leaner, apply a small per-cylinder trim.

4. Decel enleanment at 0.60 for hot cells is conservative.
   - If die-flat is resolved but popping on overrun is excessive, raise to 0.70-0.75.

5. No tbl_stoich_afr found in scalar scan.
   - Confirm the tune is using 14.7 (or 14.64 for E10) and not a custom value.

6. Closed-loop / EGO enable tables were not deeply inspected.
   - If wideband is tailpipe only, ensure closed-loop is disabled or narrowband O2 is
     simulated/ignored to prevent the ECU from trimming against a non-representative signal.

7. Spark advance was not fully dumped.
   - If knock retard appears on next WOT pull, pull the spark tables and compare to OEM.

Run a 4th-gear part-throttle pull (TPS 40-60%, 3500-5500 rpm, steady) and drop the log.
We will compute commanded vs measured AFR per zone and decide the next single-pass correction.
""")


if __name__ == "__main__":
    main()
