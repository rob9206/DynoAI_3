#!/usr/bin/env python3
"""
CSV Preflight Tool for DynoAI

Validates CSV files before processing by checking:
- Schema compliance (required columns present)
- Data value validity (ranges, types)
- Format detection and parsing capability
"""

import argparse
import json
import sys
from pathlib import Path

from ai_tuner_toolkit_dyno_v1_2 import (
    detect_csv_format,
    load_generic_csv,
    load_winpep_csv,
)
from io_contracts import csv_schema_check, safe_path, validate_input_values


def run_preflight(csv_path: Path) -> dict:
    """
    Run comprehensive preflight checks on a CSV file.

    Args:
        csv_path: Path to the CSV file to validate

    Returns:
        Dictionary with validation results including:
        - schema_ok: Whether required columns are present
        - missing_columns: List of missing required columns
        - values_ok: Whether values are within valid ranges
        - values_msg: Message about value validation
        - value_stats: Statistics about value validation
        - file_format: Detected CSV format (winpep/generic/powervision/unknown)
        - parse_ok: Whether file could be parsed
        - parse_msg: Message about parsing
        - records_parsed: Number of records successfully parsed
        - overall_ok: Overall validation status
    """
    # Step 1: Schema check
    input_info = csv_schema_check(str(csv_path))
    schema_ok = bool(input_info.get("required_columns_present", False))
    missing_columns = list(input_info.get("missing_columns", []))

    # Step 2: Validate values
    values_ok, values_msg, value_stats = validate_input_values(str(csv_path))

    # Step 3: Detect format and attempt parsing
    file_format = detect_csv_format(str(csv_path))
    parse_ok = False
    parse_msg = ""
    records_parsed = 0

    if file_format == "winpep":
        try:
            recs = load_winpep_csv(str(csv_path))
            records_parsed = len(recs)
            parse_ok = True
            parse_msg = f"Parsed {records_parsed} records as winpep"
        except Exception as e:
            parse_ok = False
            parse_msg = f"Failed to parse as winpep: {e}"
    elif file_format in ("generic", "powervision"):
        try:
            recs = load_generic_csv(str(csv_path))
            records_parsed = len(recs)
            parse_ok = True
            parse_msg = f"Parsed {records_parsed} records as {file_format}"
        except Exception as e:
            parse_ok = False
            parse_msg = f"Failed to parse as {file_format}: {e}"
    else:
        parse_ok = False
        parse_msg = "Unknown CSV format"
        records_parsed = 0

    # Step 4: Compute overall status
    overall_ok = bool(schema_ok and values_ok and parse_ok)

    # Step 5: Build result dictionary
    result = {
        "schema_ok": schema_ok,
        "missing_columns": missing_columns,
        "values_ok": values_ok,
        "values_msg": values_msg,
        "value_stats": value_stats,
        "file_format": file_format,
        "parse_ok": parse_ok,
        "parse_msg": parse_msg,
        "records_parsed": records_parsed,
        "overall_ok": overall_ok,
    }

    return result


def main():
    """Command-line interface for CSV preflight checks."""
    parser = argparse.ArgumentParser(
        description="Validate CSV files for DynoAI processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv
  %(prog)s input.csv --json
  %(prog)s input.csv --output results.json
        """,
    )

    parser.add_argument("csv_path", type=str, help="Path to CSV file to validate")

    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    parser.add_argument("--output", type=str, help="Write JSON results to file")

    args = parser.parse_args()

    try:
        # Validate and resolve path
        csv_path = safe_path(args.csv_path)

        # Run preflight checks
        result = run_preflight(csv_path)

        # Output results
        if args.output:
            output_path = safe_path(args.output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"Results written to: {output_path}")
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            # Human-readable output
            print(f"CSV Preflight Results for: {csv_path}")
            print("=" * 60)
            print(f"Schema OK: {result['schema_ok']}")
            if result["missing_columns"]:
                print(f"  Missing columns: {', '.join(result['missing_columns'])}")
            print(f"Values OK: {result['values_ok']}")
            print(f"  Message: {result['values_msg']}")
            print(f"  Stats: {result['value_stats']}")
            print(f"File format: {result['file_format']}")
            print(f"Parse OK: {result['parse_ok']}")
            print(f"  Message: {result['parse_msg']}")
            print(f"  Records parsed: {result['records_parsed']}")
            print("=" * 60)
            print(f"Overall OK: {result['overall_ok']}")

        # Exit with appropriate code
        sys.exit(0 if result["overall_ok"] else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
