"""
Parse DynoWare RT comma-CSV exports (first row = headers).

Maps Harley ECU + DWRT columns into a normalized DataFrame for iter_3 analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

LC2_COL = "(DWRT CPU) LC2 Volts Petrol AFR2"
LC2_CEILING_V = 22.38

HARLEY_PREFIX = "(Harley - ECU Type 14 SW Level 141) "


@dataclass
class DwrtParseReport:
    path: str
    row_count: int
    time_span_s: float
    lc2_pegged_count: int
    lc2_first_peg_t_s: float | None
    rpm_k_min: float | None
    rpm_k_max: float | None
    map_kpa_max: float | None
    peak_hp: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "row_count": self.row_count,
            "time_span_s": self.time_span_s,
            "lc2_pegged_count": self.lc2_pegged_count,
            "lc2_first_peg_t_s": self.lc2_first_peg_t_s,
            "rpm_k_min": self.rpm_k_min,
            "rpm_k_max": self.rpm_k_max,
            "map_kpa_max": self.map_kpa_max,
            "peak_hp": self.peak_hp,
        }


def parse_dwrt_log(path: Path) -> tuple[pd.DataFrame, DwrtParseReport]:
    """Read a DynoWare RT .txt CSV; return (dataframe, report)."""
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    if "Time" not in df.columns:
        raise ValueError(f"{path}: missing Time column")
    if LC2_COL not in df.columns:
        raise ValueError(f"{path}: missing {LC2_COL}")

    out = pd.DataFrame()
    out["time_s"] = pd.to_numeric(df["Time"], errors="coerce")

    def col(name: str, dest: str) -> None:
        if name in df.columns:
            out[dest] = pd.to_numeric(df[name], errors="coerce")
        else:
            out[dest] = float("nan")

    col(f"{HARLEY_PREFIX}Engine Speed", "rpm_k")
    col(f"{HARLEY_PREFIX}Manifold Absolute Pressure", "map_kpa")
    col(f"{HARLEY_PREFIX}Throttle Position", "tps_pct")
    col(f"{HARLEY_PREFIX}VE Front", "ve_f")
    col(f"{HARLEY_PREFIX}VE Rear", "ve_r")
    col(f"{HARLEY_PREFIX}Spark Advance Front", "spark_f_deg")
    col(f"{HARLEY_PREFIX}Spark Advance Rear", "spark_r_deg")
    col(f"{HARLEY_PREFIX}Front Spark Knock Retard", "knock_f_deg")
    col(f"{HARLEY_PREFIX}Rear Spark Knock Retard", "knock_r_deg")
    col(f"{HARLEY_PREFIX}Engine Temperature", "cht_f")
    col(f"{HARLEY_PREFIX}Intake Air Temperature", "iat_f")
    col(f"{HARLEY_PREFIX}Injector Time Front", "inj_f_ms")
    col(f"{HARLEY_PREFIX}Injector Time Rear", "inj_r_ms")
    col("(DWRT CPU) Power", "hp")

    out["lc2_afr"] = pd.to_numeric(df[LC2_COL], errors="coerce")
    out["lc2_pegged"] = out["lc2_afr"] >= LC2_CEILING_V

    out["rpm_dot_rpm_per_s"] = out["rpm_k"].diff() / out["time_s"].diff() * 1000.0

    pegged = out["lc2_pegged"].fillna(False)
    first_peg: float | None = None
    if bool(pegged.any()):
        peg_times = out.loc[out["lc2_pegged"], "time_s"]
        first_peg = float(peg_times.iloc[0])

    hp = out["hp"]
    peak_hp = float(hp.max()) if hp.notna().any() else None

    report = DwrtParseReport(
        path=str(path),
        row_count=int(len(out)),
        time_span_s=float(out["time_s"].max() - out["time_s"].min())
        if len(out) > 1
        else 0.0,
        lc2_pegged_count=int(pegged.sum()),
        lc2_first_peg_t_s=first_peg,
        rpm_k_min=float(out["rpm_k"].min()) if out["rpm_k"].notna().any() else None,
        rpm_k_max=float(out["rpm_k"].max()) if out["rpm_k"].notna().any() else None,
        map_kpa_max=float(out["map_kpa"].max()) if out["map_kpa"].notna().any() else None,
        peak_hp=peak_hp,
    )
    return out, report
