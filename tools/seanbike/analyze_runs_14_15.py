"""Quick analyzer for runnning_14 / runnning_15 (post inj_minus12pct flash)."""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

FILES = [
    Path(r"C:\CommmandCenter\Customer_Files\seanbike\runnning_14.txt"),
    Path(r"C:\CommmandCenter\Customer_Files\seanbike\runnning_15.txt"),
    Path(r"C:\CommmandCenter\Customer_Files\seanbike\runnning_17.txt"),
]


def percentile(vals: list[float], pct: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def analyze(path: Path) -> dict:
    with open(path, "r", encoding="latin-1") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    hdr = [h.strip() for h in rows[0]]

    def col(*needles: str) -> int | None:
        for needle in needles:
            for i, h in enumerate(hdr):
                if needle == h:
                    return i
            for i, h in enumerate(hdr):
                if needle.lower() in h.lower():
                    return i
        return None

    afr_i = col("(DWRT CPU) LC2 Volts Petrol AFR2", "LC2 Volts Petrol AFR")
    rpm_i = col(
        "(Harley - ECU Type 20 SW Level 357) Engine Speed",
        "(PV) Engine Speed",
        "Engine Speed",
    )
    tps_i = col(
        "(Harley - ECU Type 20 SW Level 357) Throttle Position",
        "(PV) Throttle Position",
        "Throttle Position",
    )
    ipt_f_i = col(
        "(Harley - ECU Type 20 SW Level 357) Injector Time Front",
        "(PV) Injector Time Front",
        "Injector Time Front",
    )
    ipt_r_i = col(
        "(Harley - ECU Type 20 SW Level 357) Injector Time Rear",
        "(PV) Injector Time Rear",
        "Injector Time Rear",
    )
    kr_f_i = col(
        "(Harley - ECU Type 20 SW Level 357) Front Spark Knock Retard",
        "Front Spark Knock Retard",
    )
    kr_r_i = col(
        "(Harley - ECU Type 20 SW Level 357) Rear Spark Knock Retard",
        "Rear Spark Knock Retard",
    )
    des_lam_i = col(
        "(Harley - ECU Type 20 SW Level 357) Desired Lambda",
        "(PV) Desired Lambda",
    )

    def to_float(s: str) -> float | None:
        try:
            return float(s.strip())
        except Exception:
            return None

    data = []
    for r in rows[1:]:
        if len(r) != len(hdr):
            continue
        afr = to_float(r[afr_i]) if afr_i is not None else None
        rpm = to_float(r[rpm_i]) if rpm_i is not None else None
        tps = to_float(r[tps_i]) if tps_i is not None else None
        ipt_f = to_float(r[ipt_f_i]) if ipt_f_i is not None else None
        ipt_r = to_float(r[ipt_r_i]) if ipt_r_i is not None else None
        kr_f = to_float(r[kr_f_i]) if kr_f_i is not None else None
        kr_r = to_float(r[kr_r_i]) if kr_r_i is not None else None
        des_l = to_float(r[des_lam_i]) if des_lam_i is not None else None
        data.append(
            dict(afr=afr, rpm=rpm, tps=tps, ipt_f=ipt_f, ipt_r=ipt_r, kr_f=kr_f, kr_r=kr_r, des_l=des_l)
        )

    loaded = [
        d
        for d in data
        if d["rpm"] is not None
        and d["tps"] is not None
        and d["afr"] is not None
        and d["rpm"] >= 3.0
        and d["tps"] >= 40
        and 7 <= d["afr"] < 22.38
    ]

    bands = {"40-59": [], "60-79": [], "80-100": []}
    for d in loaded:
        if d["tps"] < 60:
            bands["40-59"].append(d)
        elif d["tps"] < 80:
            bands["60-79"].append(d)
        else:
            bands["80-100"].append(d)

    out = {
        "file": path.name,
        "rows_total": len(data),
        "rows_loaded": len(loaded),
        "afr_p50": percentile([d["afr"] for d in loaded], 0.5),
        "afr_p90": percentile([d["afr"] for d in loaded], 0.9),
        "afr_min": min((d["afr"] for d in loaded), default=float("nan")),
        "afr_max": max((d["afr"] for d in loaded), default=float("nan")),
        "ipt_f_p95": percentile([d["ipt_f"] for d in loaded if d["ipt_f"] is not None], 0.95),
        "ipt_r_p95": percentile([d["ipt_r"] for d in loaded if d["ipt_r"] is not None], 0.95),
        "rpm_at_ipt_p95": None,
        "kr_f_max": max((d["kr_f"] for d in loaded if d["kr_f"] is not None), default=float("nan")),
        "kr_r_max": max((d["kr_r"] for d in loaded if d["kr_r"] is not None), default=float("nan")),
        "des_l_p50": percentile([d["des_l"] for d in loaded if d["des_l"] is not None], 0.5),
        "by_band": {},
    }
    if loaded:
        rpms_sorted_by_ipt = sorted(
            (d for d in loaded if d["ipt_f"] is not None),
            key=lambda x: x["ipt_f"],
            reverse=True,
        )
        idx = max(0, int(len(rpms_sorted_by_ipt) * 0.05))
        if rpms_sorted_by_ipt:
            out["rpm_at_ipt_p95"] = rpms_sorted_by_ipt[idx]["rpm"]

    for name, lst in bands.items():
        if not lst:
            continue
        out["by_band"][name] = dict(
            n=len(lst),
            afr_p50=percentile([d["afr"] for d in lst], 0.5),
            afr_p90=percentile([d["afr"] for d in lst], 0.9),
            rpm_p50=percentile([d["rpm"] for d in lst], 0.5),
            ipt_f_p95=percentile([d["ipt_f"] for d in lst if d["ipt_f"] is not None], 0.95),
        )
    return out


def main() -> None:
    print(f"{'file':30s} {'n_load':>7} {'AFR p50':>8} {'AFR p90':>8} {'AFR min':>8} {'IPT_F p95(ms)':>13} {'RPM@p95':>8} {'duty%@p95':>9} {'KR_F max':>8} {'DesL p50':>8}")
    for p in FILES:
        a = analyze(p)
        if a["rows_loaded"] == 0:
            print(f"{a['file']:30s} NO LOADED ROWS (rpm>=3000 & tps>=40 & 7<=AFR<=22.3)")
            print(f"   total rows parsed: {a['rows_total']}")
            continue
        cycle_ms = (60000.0 / (a["rpm_at_ipt_p95"] * 1000)) * 2 if a["rpm_at_ipt_p95"] else None
        duty = (a["ipt_f_p95"] / cycle_ms * 100) if cycle_ms and a["ipt_f_p95"] == a["ipt_f_p95"] else None
        ipt_p95 = a["ipt_f_p95"] if a["ipt_f_p95"] == a["ipt_f_p95"] else float("nan")
        rpm_p95 = a["rpm_at_ipt_p95"] if a["rpm_at_ipt_p95"] else float("nan")
        print(
            f"{a['file']:30s} {a['rows_loaded']:>7d} "
            f"{a['afr_p50']:>8.2f} {a['afr_p90']:>8.2f} {a['afr_min']:>8.2f} "
            f"{ipt_p95:>13.2f} {rpm_p95*1000:>8.0f} "
            f"{(duty if duty else 0):>9.1f} {a['kr_f_max']:>8.2f} {a['des_l_p50']:>8.3f}"
        )
        for band, b in a["by_band"].items():
            print(
                f"   TPS {band:>7s}: n={b['n']:>4d}  AFR p50={b['afr_p50']:6.2f}  "
                f"p90={b['afr_p90']:6.2f}  rpm p50={b['rpm_p50']*1000:5.0f}  "
                f"IPT_F p95={b['ipt_f_p95']:5.2f}ms"
            )


if __name__ == "__main__":
    main()
