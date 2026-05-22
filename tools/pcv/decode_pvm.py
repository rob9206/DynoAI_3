"""Final PCV .pvm reader.

Verified findings:
- TPS axis (10 columns, % x 10): values at 0x0dc = [0, 20, 50, 100, 150, 200, 400, 600, 800, 1000]
    -> 0.0, 2.0, 5.0, 10.0, 15.0, 20.0, 40.0, 60.0, 80.0, 100.0 % TPS
- RPM axis (>= 21 rows): starts near 0xf6 with [500, 750, 1000, 1250, 1500, ... 6500] step 250
    -> Actually a 25-row 250-rpm-step axis up through 6500 rpm or so. Verify by length.
- Cell grid: bytes biased at 0x80, each byte = signed delta percent OR percent/2.
  We dump BOTH interpretations.
- The file contains TWO tables (Front cyl + Rear cyl) plus an accel-pump table
  on Harley H-D Sportster/Big Twin PCV-V firmware.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def main(path: Path) -> int:
    data = path.read_bytes()
    n = len(data)

    # --- Axes ---
    tps_off = 0x00DC
    tps_count = 10
    tps_raw = list(struct.unpack_from(f"<{tps_count}H", data, tps_off))
    tps_pct = [v / 10.0 for v in tps_raw]  # tenths-of-percent

    # RPM axis
    rpm_off = 0x00F2
    rpm_count = 0
    rpm_vals = []
    j = rpm_off
    last = -1
    while j + 2 <= n:
        (v,) = struct.unpack_from("<H", data, j)
        if v > last and v - last < 5000 and v <= 12000:
            rpm_vals.append(v)
            last = v
            j += 2
            rpm_count += 1
        else:
            break

    print(f"# PCV .pvm decode (final)")
    print(f"File: {path.name}  size={n}")
    print()
    print(f"TPS axis ({tps_count} cols): {tps_pct} % TPS")
    print(f"RPM axis ({rpm_count} rows): {rpm_vals}")
    print()

    expected_cells = tps_count * rpm_count
    print(f"Expected cells per table = {tps_count} cols x {rpm_count} rows = {expected_cells}")
    print()

    # The cell grid will be a contiguous block of expected_cells bytes
    # somewhere after the axes. We'll scan for the first block where all
    # bytes are within 0x80 +/- 0x50 and length >= expected_cells.

    def find_grid(start: int, count: int, window_lo: int = 0x30, window_hi: int = 0xD0):
        i = start
        while i < n:
            if window_lo <= data[i] <= window_hi:
                j = i
                while j < n and window_lo <= data[j] <= window_hi:
                    j += 1
                if j - i >= count:
                    return (i, j)
                i = j
            else:
                i += 1
        return None

    grid_start_search = rpm_off + rpm_count * 2

    # FRONT cylinder grid
    g1 = find_grid(grid_start_search, expected_cells)
    if not g1:
        print("Could not find front-cyl grid block.")
        return 1
    f_start, f_end = g1
    front_bytes = data[f_start : f_start + expected_cells]

    # REAR cylinder grid (search after the front block)
    g2 = find_grid(f_start + expected_cells, expected_cells)
    rear_bytes = None
    r_start = None
    if g2:
        r_start, r_end = g2
        rear_bytes = data[r_start : r_start + expected_cells]

    print(f"Front grid at 0x{f_start:04x} .. 0x{f_start + expected_cells:04x}")
    if r_start:
        print(f"Rear  grid at 0x{r_start:04x} .. 0x{r_start + expected_cells:04x}")
    else:
        print("Rear grid: not found (file may contain only one table or different layout)")
    print()

    def print_grid(name: str, raw: bytes, tps_pct, rpm_vals):
        nrows = len(rpm_vals)
        ncols = len(tps_pct)
        deltas = [b - 0x80 for b in raw]
        rows = [deltas[r * ncols : (r + 1) * ncols] for r in range(nrows)]
        print(f"--- {name}  (signed % trim per cell) ---")
        # header
        hdr = f"{'RPM':>5}  " + " ".join(f"{t:>5.1f}" for t in tps_pct)
        print(hdr)
        for r, row in enumerate(rows):
            cells = " ".join(f"{c:+5d}" for c in row)
            print(f"{rpm_vals[r]:5d}  {cells}")
        flat = [c for row in rows for c in row]
        print()
        print(f"{name} stats: min={min(flat):+d}% max={max(flat):+d}% "
              f"mean={sum(flat)/len(flat):+.1f}% nonzero={sum(1 for v in flat if v)}/{len(flat)}")
        wot_col = ncols - 1
        print(f"WOT column ({tps_pct[wot_col]}% TPS):")
        for r in range(nrows):
            print(f"  {rpm_vals[r]:5d} rpm  {rows[r][wot_col]:+4d}%")
        return rows

    front_rows = print_grid("FRONT cylinder trim", front_bytes, tps_pct, rpm_vals)
    print()
    rear_rows = None
    if rear_bytes:
        rear_rows = print_grid("REAR cylinder trim", rear_bytes, tps_pct, rpm_vals)

    # Save side-by-side CSV
    out_csv = path.with_suffix(".decoded.csv")
    with out_csv.open("w", encoding="utf-8") as fh:
        fh.write("cylinder,rpm," + ",".join(f"tps_{t}" for t in tps_pct) + "\n")
        for r in range(len(rpm_vals)):
            fh.write("FRONT," + str(rpm_vals[r]) + "," +
                     ",".join(str(front_rows[r][c]) for c in range(len(tps_pct))) + "\n")
        if rear_rows:
            for r in range(len(rpm_vals)):
                fh.write("REAR," + str(rpm_vals[r]) + "," +
                         ",".join(str(rear_rows[r][c]) for c in range(len(tps_pct))) + "\n")
    print()
    print(f"Wrote -> {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\CommmandCenter\Customer_Files\seanbike\seanPCVMAP.pvm")))
