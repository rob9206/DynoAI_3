"""Converter for Jetstream data to DynoAI CSV format."""

import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from io_contracts import safe_path

# Add parent directory to path for io_contracts import
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Required columns for DynoAI processing
REQUIRED_COLUMNS = ("rpm", "map_kpa", "torque")

# Column mapping from Jetstream format to DynoAI format
# Keys are Jetstream column names, values are DynoAI column names
COLUMN_MAPPING: Dict[str, str] = {
    # RPM variations
    "RPM": "rpm",
    "Engine_RPM": "rpm",
    "engine_rpm": "rpm",
    "Rpm": "rpm",
    # MAP/kPa variations
    "MAP": "map_kpa",
    "MAP_kPa": "map_kpa",
    "Manifold_Pressure": "map_kpa",
    "manifold_pressure": "map_kpa",
    "map_kpa": "map_kpa",
    "Boost_kPa": "map_kpa",
    # Torque variations
    "Torque": "torque",
    "Torque_Nm": "torque",
    "torque_nm": "torque",
    "Engine_Torque": "torque",
    # AFR variations
    "AFR_Front": "afr_meas_f",
    "AFR_Rear": "afr_meas_r",
    "AFR_F": "afr_meas_f",
    "AFR_R": "afr_meas_r",
    "AFR_Cmd_F": "afr_cmd_f",
    "AFR_Cmd_R": "afr_cmd_r",
    "Lambda_Front": "lambda_f",
    "Lambda_Rear": "lambda_r",
    # Spark variations
    "Spark_Front": "spark_f",
    "Spark_Rear": "spark_r",
    "Spark_F": "spark_f",
    "Spark_R": "spark_r",
    "Ignition_Front": "spark_f",
    "Ignition_Rear": "spark_r",
    # Other common columns
    "TPS": "tps",
    "Throttle_Position": "tps",
    "IAT": "iat",
    "Intake_Air_Temp": "iat",
    "ECT": "ect",
    "Coolant_Temp": "ect",
    "VBatt": "vbatt",
    "Battery_Voltage": "vbatt",
    "Time": "time",
    "Timestamp": "time",
}

# Unit conversions (from_unit -> to_unit -> multiplier)
UNIT_CONVERSIONS: Dict[str, Dict[str, float]] = {
    "psi_to_kpa": {"multiplier": 6.89476},
    "bar_to_kpa": {"multiplier": 100.0},
    "inhg_to_kpa": {"multiplier": 3.38639},
    "nm_to_ftlb": {"multiplier": 0.737562},
    "ftlb_to_nm": {"multiplier": 1.35582},
}


def _detect_column_mapping(header: List[str]) -> Dict[str, str]:
    """
    Detect the column mapping for the input CSV.

    Args:
        header: List of column names from the input CSV

    Returns:
        Dictionary mapping input column names to output column names
    """
    mapping = {}
    for col in header:
        # First try exact match
        if col in COLUMN_MAPPING:
            mapping[col] = COLUMN_MAPPING[col]
        else:
            # Try case-insensitive match
            col_lower = col.lower().strip()
            for jetstream_col, dynoai_col in COLUMN_MAPPING.items():
                if jetstream_col.lower() == col_lower:
                    mapping[col] = dynoai_col
                    break
            else:
                # Keep unmapped columns as-is (lowercase)
                mapping[col] = col_lower
    return mapping


def _detect_unit_conversion(col_name: str, sample_values: List[str]) -> Optional[float]:
    """
    Detect if unit conversion is needed based on column name and sample values.

    Args:
        col_name: Column name
        sample_values: Sample values from the column

    Returns:
        Conversion multiplier if needed, None otherwise
    """
    col_lower = col_name.lower()

    # Check for pressure columns that might need conversion
    if "psi" in col_lower:
        return UNIT_CONVERSIONS["psi_to_kpa"]["multiplier"]
    if "bar" in col_lower and "map" in col_lower:
        return UNIT_CONVERSIONS["bar_to_kpa"]["multiplier"]
    if "inhg" in col_lower:
        return UNIT_CONVERSIONS["inhg_to_kpa"]["multiplier"]

    # Check for torque columns
    if "ftlb" in col_lower or "ft-lb" in col_lower or "ft_lb" in col_lower:
        return UNIT_CONVERSIONS["ftlb_to_nm"]["multiplier"]

    return None


def convert_jetstream_to_dynoai(raw_path: str, output_path: str) -> str:
    """
    Convert Jetstream data format to DynoAI CSV format.

    This is a FORMAT BRIDGE ONLY - it does NOT modify tuning math.
    It maps column names and handles unit conversions as needed.

    Args:
        raw_path: Path to the raw Jetstream data file
        output_path: Path for the converted output file
                     MUST be validated with io_contracts.safe_path

    Returns:
        Path to the converted file

    Raises:
        ValueError: If required columns are missing or path is unsafe
        FileNotFoundError: If input file doesn't exist
    """
    # Validate paths using io_contracts.safe_path
    safe_raw = safe_path(raw_path)
    safe_output = safe_path(output_path)

    if not safe_raw.exists():
        raise FileNotFoundError(f"Input file not found: {raw_path}")

    # Ensure output directory exists
    safe_output.parent.mkdir(parents=True, exist_ok=True)

    # Read the input file
    with open(safe_raw, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input file has no header row")

        # Detect column mapping
        column_map = _detect_column_mapping(list(reader.fieldnames))

        # Read sample values for unit detection
        rows = list(reader)

    if not rows:
        raise ValueError("Input file has no data rows")

    # Detect unit conversions
    conversions: Dict[str, float] = {}
    for orig_col in column_map.keys():
        sample_vals = [row.get(orig_col, "") for row in rows[:10] if row.get(orig_col)]
        multiplier = _detect_unit_conversion(orig_col, sample_vals)
        if multiplier is not None:
            conversions[orig_col] = multiplier

    # Check for required columns
    output_cols = set(column_map.values())
    missing = [col for col in REQUIRED_COLUMNS if col not in output_cols]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # Write the output file
    output_fieldnames = [column_map[col] for col in reader.fieldnames]

    with open(safe_output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()

        for row in rows:
            output_row = {}
            for orig_col, new_col in column_map.items():
                value = row.get(orig_col, "")
                # Apply unit conversion if needed
                if orig_col in conversions and value:
                    try:
                        numeric_val = float(value)
                        value = str(round(numeric_val * conversions[orig_col], 4))
                    except ValueError:
                        pass  # Keep original value if not numeric
                output_row[new_col] = value
            writer.writerow(output_row)

    return str(safe_output)


def validate_converted_output(output_path: str) -> Dict[str, any]:
    """
    Validate that the converted output has the required columns and data.

    Args:
        output_path: Path to the converted CSV file

    Returns:
        Dictionary with validation results
    """
    safe_output = safe_path(output_path)

    result = {
        "valid": False,
        "row_count": 0,
        "columns": [],
        "missing_columns": [],
        "errors": [],
    }

    if not safe_output.exists():
        result["errors"].append(f"File not found: {output_path}")
        return result

    try:
        with open(safe_output, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                result["errors"].append("No header row found")
                return result

            result["columns"] = list(reader.fieldnames)
            result["missing_columns"] = [
                col for col in REQUIRED_COLUMNS if col not in reader.fieldnames
            ]

            # Count rows and check for data
            row_count = 0
            for row in reader:
                row_count += 1
            result["row_count"] = row_count

            if result["missing_columns"]:
                result["errors"].append(
                    f"Missing required columns: {', '.join(result['missing_columns'])}"
                )
            elif row_count == 0:
                result["errors"].append("No data rows found")
            else:
                result["valid"] = True

    except Exception as e:
        result["errors"].append(f"Error reading file: {str(e)}")

    return result
