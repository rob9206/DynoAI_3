#!/usr/bin/env python3
"""
Test suite for preflight_csv.py

Tests the CSV preflight validation tool to ensure it properly:
- Detects schema compliance
- Validates data values
- Detects CSV format
- Parses different CSV formats
"""

import json
import os
import sys
import unittest
from pathlib import Path

import preflight_csv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPreflightCSV(unittest.TestCase):
    """Test CSV preflight validation functionality"""

    def test_run_preflight_with_valid_winpep_csv(self):
        """Test preflight with a valid WinPEP CSV file"""
        # Use an actual sample file from the repository
        csv_path = Path(__file__).parent.parent / "tables" / "WinPEP_Sample.csv"

        if csv_path.exists():
            result = preflight_csv.run_preflight(csv_path)

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("schema_ok", result)
            self.assertIn("missing_columns", result)
            self.assertIn("values_ok", result)
            self.assertIn("values_msg", result)
            self.assertIn("value_stats", result)
            self.assertIn("file_format", result)
            self.assertIn("parse_ok", result)
            self.assertIn("parse_msg", result)
            self.assertIn("records_parsed", result)
            self.assertIn("overall_ok", result)

            # Verify types
            self.assertIsInstance(result["schema_ok"], bool)
            self.assertIsInstance(result["missing_columns"], list)
            self.assertIsInstance(result["values_ok"], bool)
            self.assertIsInstance(result["values_msg"], str)
            self.assertIsInstance(result["value_stats"], dict)
            self.assertIsInstance(result["file_format"], str)
            self.assertIsInstance(result["parse_ok"], bool)
            self.assertIsInstance(result["parse_msg"], str)
            self.assertIsInstance(result["records_parsed"], int)
            self.assertIsInstance(result["overall_ok"], bool)

    def test_run_preflight_with_missing_columns(self):
        """Test preflight with CSV missing required columns"""
        # Create a temporary CSV file missing required columns in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "test_missing_cols.csv"

        with open(temp_path, "w") as f:
            f.write("col1,col2,col3\n")
            f.write("1,2,3\n")

        try:
            result = preflight_csv.run_preflight(temp_path)

            # Should detect schema issue
            self.assertFalse(result["schema_ok"])
            self.assertGreater(len(result["missing_columns"]), 0)

            # Should still attempt format detection
            self.assertIn(
                result["file_format"], ["winpep", "generic", "powervision", "unknown"]
            )

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_run_preflight_with_valid_columns(self):
        """Test preflight with CSV that has required columns"""
        # Create a temporary CSV file with required columns in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "test_valid_cols.csv"

        with open(temp_path, "w") as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("2000,50,100\n")
            f.write("3000,60,120\n")

        try:
            result = preflight_csv.run_preflight(temp_path)

            # Should pass schema check
            self.assertTrue(result["schema_ok"])
            self.assertEqual(len(result["missing_columns"]), 0)

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_format_detection(self):
        """Test that format detection works"""
        # Create a simple CSV that should be detected as generic in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "test_format.csv"

        with open(temp_path, "w") as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("2000,50,100\n")

        try:
            result = preflight_csv.run_preflight(temp_path)

            # Should detect a format
            self.assertIsNotNone(result["file_format"])
            self.assertIsInstance(result["file_format"], str)

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_overall_ok_logic(self):
        """Test that overall_ok is computed correctly"""
        # Create a CSV with all required columns and valid values in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "test_overall.csv"

        with open(temp_path, "w") as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("2000,50,100\n")
            f.write("3000,60,120\n")

        try:
            result = preflight_csv.run_preflight(temp_path)

            # overall_ok should be combination of schema_ok, values_ok, and parse_ok
            expected_overall = (
                result["schema_ok"] and result["values_ok"] and result["parse_ok"]
            )
            self.assertEqual(result["overall_ok"], expected_overall)

        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestPreflightCLI(unittest.TestCase):
    """Test command-line interface functionality"""

    def test_cli_with_json_output(self):
        """Test CLI with JSON output option"""
        import subprocess

        # Create a test CSV in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_csv = temp_dir / "test_cli_json.csv"

        with open(temp_csv, "w") as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("2000,50,100\n")

        try:
            result = subprocess.run(
                [sys.executable, "preflight_csv.py", str(temp_csv), "--json"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
            )

            # Should output valid JSON
            if result.stdout:
                output_data = json.loads(result.stdout)
                self.assertIsInstance(output_data, dict)
                self.assertIn("overall_ok", output_data)

        finally:
            if temp_csv.exists():
                temp_csv.unlink()

    def test_cli_with_file_output(self):
        """Test CLI with file output option"""
        import subprocess

        # Create test files in project directory
        temp_dir = Path(__file__).parent.parent / "temp_selftest"
        temp_dir.mkdir(exist_ok=True)
        temp_csv = temp_dir / "test_cli_file.csv"
        temp_output = temp_dir / "test_output.json"

        with open(temp_csv, "w") as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("2000,50,100\n")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "preflight_csv.py",
                    str(temp_csv),
                    "--output",
                    str(temp_output),
                ],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
            )

            # Should create output file
            self.assertTrue(temp_output.exists())

            # Output file should contain valid JSON
            if temp_output.exists():
                with open(temp_output, "r") as f:
                    output_data = json.load(f)
                self.assertIsInstance(output_data, dict)
                self.assertIn("overall_ok", output_data)

        finally:
            if temp_csv.exists():
                temp_csv.unlink()
            if temp_output.exists():
                temp_output.unlink()


if __name__ == "__main__":
    unittest.main()
