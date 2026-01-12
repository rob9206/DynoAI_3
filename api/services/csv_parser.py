"""
CSV Parsing Utilities

Centralized CSV parsing functions to eliminate code duplication and ensure
consistent error handling across the application.
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.errors import CSVParsingError, ValidationError


def parse_ve_delta_csv(
    file_path: Path,
) -> Tuple[List[int], List[int], List[List[float]]]:
    """
    Parse VE delta CSV file with RPM rows and kPa columns.

    Format expected:
        RPM, 35, 45, 55, 65, 75
        1500, +2.5, +3.1, ...
        2000, +1.8, +2.3, ...

    Args:
        file_path: Path to the VE delta CSV file

    Returns:
        Tuple of (rpm_points, load_points, corrections)
        - rpm_points: List of RPM values (from first column)
        - load_points: List of kPa values (from header row)
        - corrections: 2D list of correction values (floats)

    Raises:
        CSVParsingError: If file cannot be parsed or has invalid format
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)

            # Read header row (contains kPa bins)
            try:
                header = next(reader)
            except StopIteration:
                raise CSVParsingError(
                    "CSV file is empty",
                    file_path=str(file_path),
                    line_number=1,
                )

            # Extract kPa bins from header (skip first "RPM" column)
            try:
                load_points = [int(h) for h in header[1:]]
            except ValueError as e:
                raise CSVParsingError(
                    f"Invalid header values (expected integers): {e}",
                    file_path=str(file_path),
                    line_number=1,
                )

            rpm_points = []
            corrections = []

            for line_num, row in enumerate(reader, start=2):
                if not row:
                    continue  # Skip empty rows

                try:
                    # First column is RPM
                    rpm = int(row[0])
                    rpm_points.append(rpm)

                    # Remaining columns are correction values
                    # Remove '+' prefix and any quotes, then convert to float
                    row_corrections = [
                        float(val.replace("+", "").replace("'", "").strip())
                        for val in row[1:]
                    ]
                    corrections.append(row_corrections)

                except (ValueError, IndexError) as e:
                    raise CSVParsingError(
                        f"Invalid data in row: {e}",
                        file_path=str(file_path),
                        line_number=line_num,
                    )

                # Validate row length matches header
                if len(row_corrections) != len(load_points):
                    raise CSVParsingError(
                        f"Row has {len(row_corrections)} values but header has {len(load_points)} columns",
                        file_path=str(file_path),
                        line_number=line_num,
                    )

        return rpm_points, load_points, corrections

    except FileNotFoundError:
        raise CSVParsingError(
            f"File not found: {file_path}",
            file_path=str(file_path),
        )
    except CSVParsingError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise CSVParsingError(
            f"Unexpected error parsing CSV: {e}",
            file_path=str(file_path),
        )


def parse_dyno_run_csv(
    file_path: Path,
    required_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Parse dyno run CSV file using DictReader.

    Args:
        file_path: Path to the CSV file
        required_columns: Optional list of column names that must be present

    Returns:
        List of dictionaries, one per row

    Raises:
        CSVParsingError: If file cannot be parsed or missing required columns
    """
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)

            # Validate required columns if specified
            if required_columns and reader.fieldnames:
                missing = set(required_columns) - set(reader.fieldnames)
                if missing:
                    raise CSVParsingError(
                        f"Missing required columns: {', '.join(missing)}",
                        file_path=str(file_path),
                        line_number=1,
                    )

            rows = []
            for line_num, row in enumerate(reader, start=2):
                if not row or all(v == "" or v is None for v in row.values()):
                    continue  # Skip empty rows
                rows.append(row)

            return rows

    except FileNotFoundError:
        raise CSVParsingError(
            f"File not found: {file_path}",
            file_path=str(file_path),
        )
    except CSVParsingError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise CSVParsingError(
            f"Unexpected error parsing CSV: {e}",
            file_path=str(file_path),
        )


def parse_csv_with_validation(
    file_path: Path,
    validator_func: Optional[callable] = None,
    skip_invalid: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse CSV with optional per-row validation.

    Args:
        file_path: Path to the CSV file
        validator_func: Optional function to validate each row.
                       Should return True if valid, False if invalid.
                       Signature: validator_func(row: Dict[str, Any]) -> bool
        skip_invalid: If True, skip invalid rows and collect errors.
                     If False, raise on first invalid row.

    Returns:
        Tuple of (valid_rows, error_messages)

    Raises:
        CSVParsingError: If file cannot be parsed or validation fails (when skip_invalid=False)
    """
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            valid_rows = []
            errors = []

            for line_num, row in enumerate(reader, start=2):
                if not row or all(v == "" or v is None for v in row.values()):
                    continue  # Skip empty rows

                # Apply validation if provided
                if validator_func:
                    try:
                        is_valid = validator_func(row)
                        if not is_valid:
                            error_msg = f"Line {line_num}: Row failed validation"
                            if skip_invalid:
                                errors.append(error_msg)
                                continue
                            else:
                                raise CSVParsingError(
                                    error_msg,
                                    file_path=str(file_path),
                                    line_number=line_num,
                                )
                    except Exception as e:
                        error_msg = f"Line {line_num}: Validation error: {e}"
                        if skip_invalid:
                            errors.append(error_msg)
                            continue
                        else:
                            raise CSVParsingError(
                                error_msg,
                                file_path=str(file_path),
                                line_number=line_num,
                            )

                valid_rows.append(row)

            return valid_rows, errors

    except FileNotFoundError:
        raise CSVParsingError(
            f"File not found: {file_path}",
            file_path=str(file_path),
        )
    except CSVParsingError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise CSVParsingError(
            f"Unexpected error parsing CSV: {e}",
            file_path=str(file_path),
        )


def safe_float_conversion(value: str, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert string to float, handling common issues.

    Handles:
    - Empty strings
    - Whitespace
    - Plus signs
    - Quotes
    - Invalid values

    Args:
        value: String value to convert
        default: Default value to return if conversion fails

    Returns:
        Float value or default
    """
    if not value or not isinstance(value, str):
        return default

    try:
        # Remove common formatting characters
        cleaned = value.replace("+", "").replace("'", "").replace('"', "").strip()
        if not cleaned:
            return default
        return float(cleaned)
    except (ValueError, AttributeError):
        return default


def safe_int_conversion(value: str, default: Optional[int] = None) -> Optional[int]:
    """
    Safely convert string to int, handling common issues.

    Args:
        value: String value to convert
        default: Default value to return if conversion fails

    Returns:
        Integer value or default
    """
    if not value or not isinstance(value, str):
        return default

    try:
        cleaned = value.strip()
        if not cleaned:
            return default
        return int(float(cleaned))  # Handle "123.0" -> 123
    except (ValueError, AttributeError):
        return default
