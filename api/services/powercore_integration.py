"""
Power Core / WinPEP8 Integration Module for DynoAI

This module provides integration with Dynojet Power Core software:
1. Parse Power Vision CSV log files
2. Parse/generate PVV tune files (XML format)
3. Connect to LiveLinkService for real-time data (requires Power Core running)
4. Export TuneLab-compatible scripts

Integration paths:
- File-based: Import/export CSV logs and PVV tune files
- Script-based: Generate TuneLab Python scripts for Power Core
- Real-time: Connect via WCF named pipe to LiveLinkService
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from defusedxml import ElementTree as DefusedET

# NOTE: We don't use safe_path here because Power Core files are in user Documents,
# outside the project directory. These functions only READ files, never write.


def _resolve_path(path: str) -> Path:
    """Resolve path, allowing external files for Power Core integration."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return p


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SignalDefinition:
    """Power Vision log signal definition."""

    index: int
    driver: str
    signal_id: str
    name: str
    units: str
    description: str
    color: str = "#FFFFFF"


@dataclass
class PowerVisionLog:
    """Parsed Power Vision CSV log file."""

    format_version: str
    signals: dict[int, SignalDefinition]
    data: pd.DataFrame  # Columns: Time_ms, plus one column per signal name
    source_path: Optional[str] = None


@dataclass
class TuneTable:
    """A 2D tune table from PVV file."""

    name: str
    units: str
    row_axis: list[float]  # Y-axis values (e.g., RPM)
    row_units: str
    col_axis: list[float]  # X-axis values (e.g., MAP kPa)
    col_units: str
    values: np.ndarray  # 2D array of cell values


@dataclass
class TuneFile:
    """Parsed PVV tune file."""

    tables: dict[str, TuneTable] = field(default_factory=dict)
    scalars: dict[str, float] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    source_path: Optional[str] = None


# =============================================================================
# Power Vision CSV Log Parser
# =============================================================================


def parse_powervision_log(csv_path: str) -> PowerVisionLog:
    """
    Parse a Dynojet Power Vision Pro-XY CSV log file.

    Format:
    - Line 1: "Dynojet Power Vision Log File"
    - Line 3: "Format:","Pro-XY CSV 1.0.0"
    - Lines 5+: Signal definitions with index, driver, ID, name, units, description, color
    - After blank line: "Time(ms)","Signal","Value" header
    - Data rows: timestamp, signal_index, value

    Returns a PowerVisionLog with signals dict and pivoted DataFrame.
    """
    path = _resolve_path(csv_path)

    signals: dict[int, SignalDefinition] = {}
    format_version = "Unknown"
    data_rows: list[tuple[int, int, float]] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    in_data_section = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse format version
        if line.startswith('"Format:"'):
            match = re.search(r'"Format:","([^"]+)"', line)
            if match:
                format_version = match.group(1)
            continue

        # Detect data section start
        if line.startswith('"Time(ms)"'):
            in_data_section = True
            continue

        if in_data_section:
            # Parse data row: time_ms, signal_index, value
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    time_ms = int(parts[0])
                    signal_idx = int(parts[1])
                    # Value might be hex (e.g., "26D") or float
                    val_str = parts[2].strip()
                    if val_str.replace(".", "").replace("-", "").isdigit():
                        value = float(val_str)
                    else:
                        # Try hex
                        try:
                            value = float(int(val_str, 16))
                        except ValueError:
                            continue
                    data_rows.append((time_ms, signal_idx, value))
                except (ValueError, IndexError):
                    continue
        else:
            # Parse signal definition
            # Format: index,"driver","id","name","units","description","color"
            match = re.match(
                r'^(\d+),"([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)"',
                line,
            )
            if match:
                idx = int(match.group(1))
                signals[idx] = SignalDefinition(
                    index=idx,
                    driver=match.group(2),
                    signal_id=match.group(3),
                    name=match.group(4),
                    units=match.group(5),
                    description=match.group(6),
                    color=match.group(7),
                )

    # Convert sparse data to pivoted DataFrame
    if data_rows:
        raw_df = pd.DataFrame(data_rows, columns=["Time_ms", "Signal", "Value"])

        # Create column names from signal definitions
        signal_names = {idx: sig.name for idx, sig in signals.items()}
        raw_df["Channel"] = raw_df["Signal"].map(signal_names)

        # Pivot to wide format - one column per signal
        pivoted = raw_df.pivot_table(
            index="Time_ms",
            columns="Channel",
            values="Value",
            aggfunc="first",
        ).reset_index()

        # Forward-fill missing values (signals don't all update at same rate)
        pivoted = pivoted.ffill()
    else:
        pivoted = pd.DataFrame()

    return PowerVisionLog(
        format_version=format_version,
        signals=signals,
        data=pivoted,
        source_path=str(path),
    )


def powervision_log_to_dynoai_format(pv_log: PowerVisionLog) -> pd.DataFrame:
    """
    Convert Power Vision log to DynoAI standard format.

    Maps common Power Vision channels to DynoAI column names.
    """
    df = pv_log.data.copy()

    # Channel mapping: Power Vision name -> DynoAI name
    channel_map = {
        "RPM": "Engine RPM",
        "MAP": "MAP kPa",
        "TP": "TPS",
        "ET": "Engine Temp",
        "IAT": "IAT F",
        "WBO2 F": "AFR Meas F",
        "WBO2 R": "AFR Meas R",
        "VE Front": "VE F",
        "VE Rear ": "VE R",
        "Advance F": "Spark Adv F",
        "Advance R": "Spark Adv R",
        "Spark Knock F": "Knock F",
        "Spark Knock R": "Knock R",
        "VSS": "Vehicle Speed",
        "B+": "VBatt",
        "Set Lambda": "Lambda Target",
        "INJ PW F": "Inj PW F",
        "INJ PW R": "Inj PW R",
    }

    # Rename columns that exist
    rename_map = {}
    for pv_name, dynoai_name in channel_map.items():
        if pv_name in df.columns:
            rename_map[pv_name] = dynoai_name

    df = df.rename(columns=rename_map)

    # Convert Lambda to AFR if present
    if "Lambda Target" in df.columns:
        df["AFR Target"] = df["Lambda Target"] * 14.7

    # Convert time to seconds
    if "Time_ms" in df.columns:
        df["Time_s"] = df["Time_ms"] / 1000.0

    return df


# =============================================================================
# PVV Tune File Parser
# =============================================================================


def parse_pvv_tune(pvv_path: str) -> TuneFile:
    """
    Parse a Dynojet PVV (Power Vision Values) XML tune file.

    Format:
    <PVV>
      <Item name="Table Name" units="">
        <Columns units="MAP (KPa)">
          <Col label="20"/>...
        </Columns>
        <Rows units="RPM">
          <Row label="750">
            <Cell value="13.0"/>...
          </Row>
        </Rows>
      </Item>
    </PVV>
    """
    path = _resolve_path(pvv_path)
    # Use defusedxml to prevent XXE attacks
    tree = DefusedET.parse(str(path))
    root = tree.getroot()

    tune = TuneFile(source_path=str(path))

    for item in root.findall("Item"):
        name = item.get("name", "Unknown")
        units = item.get("units", "")

        cols_elem = item.find("Columns")
        rows_elem = item.find("Rows")

        if cols_elem is None or rows_elem is None:
            continue

        col_units = cols_elem.get("units", "")
        row_units = rows_elem.get("units", "")

        # Parse column axis values
        col_axis: list[float] = []
        for col in cols_elem.findall("Col"):
            label = col.get("label", "0")
            try:
                col_axis.append(float(label) if label else 0.0)
            except ValueError:
                col_axis.append(0.0)

        # Parse row axis and cell values
        row_axis: list[float] = []
        values: list[list[float]] = []
        for row in rows_elem.findall("Row"):
            label = row.get("label", "0")
            try:
                row_axis.append(float(label) if label else 0.0)
            except ValueError:
                row_axis.append(0.0)

            row_values: list[float] = []
            for cell in row.findall("Cell"):
                val = cell.get("value", "0")
                try:
                    row_values.append(float(val))
                except ValueError:
                    row_values.append(0.0)
            values.append(row_values)

        # Determine if this is a scalar, flag, or table
        if len(row_axis) == 1 and len(col_axis) == 1:
            # Single value - check if it's a flag
            val = values[0][0] if values and values[0] else 0.0
            if "Flag" in col_units or val in (0, 1):
                tune.flags[name] = val == 1
            else:
                tune.scalars[name] = val
        else:
            # Multi-dimensional table
            tune.tables[name] = TuneTable(
                name=name,
                units=units,
                row_axis=row_axis,
                row_units=row_units,
                col_axis=col_axis,
                col_units=col_units,
                values=np.array(values),
            )

    return tune


def tune_table_to_dataframe(table: TuneTable) -> pd.DataFrame:
    """Convert a TuneTable to a pandas DataFrame with labeled axes."""
    df = pd.DataFrame(
        table.values,
        index=pd.Index(table.row_axis, name=table.row_units),
        columns=pd.Index(table.col_axis, name=table.col_units),
    )
    return df


def generate_pvv_xml(tune: TuneFile) -> str:
    """Generate PVV XML from a TuneFile object."""
    root = ET.Element("PVV")

    # Write flags
    for flag_name, flag_val in tune.flags.items():
        item = ET.SubElement(root, "Item", name=flag_name, units="")
        cols = ET.SubElement(item, "Columns", units="Flag (0=Off,1=On)")
        ET.SubElement(cols, "Col", label="")
        rows = ET.SubElement(item, "Rows", units="RowLabel")
        row = ET.SubElement(rows, "Row", label="")
        ET.SubElement(row, "Cell", value=str(int(flag_val)))

    # Write scalars
    for scalar_name, scalar_val in tune.scalars.items():
        item = ET.SubElement(root, "Item", name=scalar_name, units="")
        cols = ET.SubElement(item, "Columns", units="")
        ET.SubElement(cols, "Col", label="")
        rows = ET.SubElement(item, "Rows", units="")
        row = ET.SubElement(rows, "Row", label="")
        ET.SubElement(row, "Cell", value=str(scalar_val))

    # Write tables
    for table in tune.tables.values():
        item = ET.SubElement(root, "Item", name=table.name, units=table.units)
        cols = ET.SubElement(item, "Columns", units=table.col_units)
        for col_val in table.col_axis:
            col_label = str(int(col_val) if col_val == int(col_val) else col_val)
            ET.SubElement(cols, "Col", label=col_label)

        rows = ET.SubElement(item, "Rows", units=table.row_units)
        for i, row_val in enumerate(table.row_axis):
            row_label = str(int(row_val) if row_val == int(row_val) else row_val)
            row = ET.SubElement(rows, "Row", label=row_label)
            for j in range(len(table.col_axis)):
                cell_val = table.values[i, j]
                ET.SubElement(row, "Cell", value=f"{cell_val:.2f}")

    # Pretty print
    ET.indent(root, space="\t")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        root, encoding="unicode"
    )


# =============================================================================
# TuneLab Script Generator
# =============================================================================


def generate_tunelab_script(
    correction_table: str = "Volumetric Efficiency",
    afr_channel: str = "Air/Fuel Ratio 1",
    smoothing: float = 500.0,
    min_afr: float = 10.0,
    max_afr: float = 19.0,
) -> str:
    """
    Generate a TuneLab Python script for Power Core.

    This script can be loaded in Power Core's TuneLab to apply
    corrections based on logged AFR data.
    """
    return f'''"""
DynoAI Generated TuneLab Script
Applies VE corrections based on logged AFR data
"""
import tunelab
from tunelab import ConfigurableChannelProvider
import tlfilters


class DynoAICorrection(ConfigurableChannelProvider):

    # Configuration (adjust as needed)
    correction_table = "{correction_table}"
    afr_channel = "{afr_channel}"
    requested_afr_channel = "Requested AFR"

    # Filtering parameters
    smoothing = {smoothing}
    do_afr_smoothing = True
    do_afr_trimming = True
    min_afr = {min_afr}
    max_afr = {max_afr}
    min_requested_afr = 0
    max_requested_afr = 14.7

    show_plot = True

    def __init__(self):
        self.afr_channel = context.AFR1

    def calc_error_channel(self, fileHandle):
        """Calculate AFR error channel for correction."""
        if callable(self.afr_channel):
            afr1 = self.afr_channel(fileHandle)
        else:
            afr1 = channels.GetChannelByName(self.afr_channel, fileHandle)

        if self.do_afr_smoothing:
            filter1 = tlfilters.LowpassFilter(self.smoothing)
            filter1.do_filter(None, None, afr1.GetAllSamples())

        if self.do_afr_trimming:
            filter2 = tlfilters.TimeMinMaxZFilter(self.min_afr, self.max_afr)
            filter2.do_filter(None, None, afr1.GetAllSamples())

        plotCancelled = False
        if self.show_plot:
            plotCancelled = not context.Plot(
                afr1.GetAllSamples(),
                text="Review AFR data from %s" % afr1.GetSourceFileName(),
                yAxisText=afr1.GetName()
            )

        requested = channels.GetChannelByName(self.requested_afr_channel, fileHandle)
        filter_req = tlfilters.BasicMinMaxZFilter(self.min_requested_afr, self.max_requested_afr)
        filter_req.do_filter(None, None, requested.GetAllSamples())

        if not plotCancelled:
            return afr1 / requested
        return None

    def _do_correction(self):
        """Apply VE correction based on AFR error."""
        error = tunelab.generate_sample_table(
            context.GetTable(self.correction_table),
            self
        )

        if error is not None:
            error = tunelab.edit(error)
            if error is not None:
                corrected = context.GetTable(self.correction_table) * error
                context.PutTable(corrected)

    def Run(self):
        """Main entry point - called by Power Core."""
        if context.EnsureFiles():
            try:
                self._do_correction()
            finally:
                context.FreeFiles()


# Register with TuneLab
correction = DynoAICorrection()
'''


# =============================================================================
# Live Link Service Connection (WCF Named Pipe)
# =============================================================================

LIVELINK_PIPE_ADDRESS = "net.pipe://localhost/SCT/LiveLinkService"


def check_powercore_running() -> bool:
    """Check if Power Core is running and LiveLink service is available."""
    import subprocess

    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Power Core.exe"],
        capture_output=True,
        text=True,
        check=False,
    )
    return "Power Core.exe" in result.stdout


# =============================================================================
# File Discovery
# =============================================================================


def find_powercore_data_dirs() -> list[Path]:
    """Find common Power Core data directories."""
    import os

    user_docs = Path(os.environ.get("USERPROFILE", "")) / "Documents"
    onedrive_docs = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Documents"

    search_paths = [
        user_docs / "Power Core",
        user_docs / "Power Vision",
        user_docs / "Power Commander 5",
        user_docs / "DynoRuns",
        user_docs / "Log Files",
        onedrive_docs / "Power Core",
        onedrive_docs / "Power Vision",
        onedrive_docs / "Power Commander 5",
        onedrive_docs / "DynoRuns",
        onedrive_docs / "Log Files",
        onedrive_docs / "PowerCoreBackups",
    ]

    return [p for p in search_paths if p.exists()]


def find_log_files(search_dirs: Optional[list[Path]] = None) -> list[Path]:
    """Find Power Vision log files (.csv) in common locations."""
    if search_dirs is None:
        search_dirs = find_powercore_data_dirs()

    log_files: list[Path] = []
    for dir_path in search_dirs:
        log_files.extend(dir_path.rglob("*.csv"))
        log_files.extend(dir_path.rglob("PV_Logfile_*.csv"))

    return sorted(log_files, key=lambda p: p.stat().st_mtime, reverse=True)


def find_tune_files(search_dirs: Optional[list[Path]] = None) -> list[Path]:
    """Find Power Vision tune files (.pvv, .pvm) in common locations."""
    if search_dirs is None:
        search_dirs = find_powercore_data_dirs()

    tune_files: list[Path] = []
    for dir_path in search_dirs:
        tune_files.extend(dir_path.rglob("*.pvv"))
        tune_files.extend(dir_path.rglob("*.pvm"))

    return sorted(tune_files, key=lambda p: p.stat().st_mtime, reverse=True)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Data classes
    "SignalDefinition",
    "PowerVisionLog",
    "TuneTable",
    "TuneFile",
    # Parsers
    "parse_powervision_log",
    "parse_pvv_tune",
    "powervision_log_to_dynoai_format",
    "tune_table_to_dataframe",
    # Generators
    "generate_pvv_xml",
    "generate_tunelab_script",
    # Utilities
    "check_powercore_running",
    "find_powercore_data_dirs",
    "find_log_files",
    "find_tune_files",
    # Constants
    "LIVELINK_PIPE_ADDRESS",
]
