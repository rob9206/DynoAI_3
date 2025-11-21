#!/usr/bin/env python3
"""
Test suite for FileNotFoundError handling in csv_schema_check

This test validates that the csv_schema_check function properly handles
non-existent files with clear error messages, addressing the issue where
FileNotFoundError was raised without a user-friendly message.

Related Issue: FileNotFoundError during CSV analysis process
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import io_contracts

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFileNotFoundHandling(unittest.TestCase):
    """Test file existence checking in csv_schema_check"""

    def test_nonexistent_file_raises_clear_error(self):
        """Verify non-existent file raises FileNotFoundError with helpful message"""
        nonexistent_path = "/path/to/nonexistent/file.csv"

        with self.assertRaises(FileNotFoundError) as context:
            io_contracts.csv_schema_check(nonexistent_path)

        error_msg = str(context.exception)
        self.assertIn("CSV file not found", error_msg)
        self.assertIn(nonexistent_path, error_msg)
        self.assertIn("Please verify the file path", error_msg)

    def test_upload_directory_pattern(self):
        """Test handling of upload directory paths (UUID pattern)"""
        upload_path = "uploads/dd23257a-c303-458a-8a39-c887b9341c11/selftest.csv"

        with self.assertRaises(FileNotFoundError) as context:
            io_contracts.csv_schema_check(upload_path)

        error_msg = str(context.exception)
        self.assertIn("CSV file not found", error_msg)
        self.assertIn("selftest.csv", error_msg)

    def test_existing_file_succeeds(self):
        """Verify existing file is processed without error"""
        # Create a temporary CSV file with required columns
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("rpm,map_kpa,torque\n")
            f.write("1500,35,50\n")
            temp_path = f.name

        try:
            # Should not raise an exception
            result = io_contracts.csv_schema_check(temp_path)

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("path", result)
            self.assertIn("size_bytes", result)
            self.assertIn("required_columns_present", result)
            self.assertEqual(result["path"], temp_path)
            self.assertGreater(result["size_bytes"], 0)

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_empty_file_handling(self):
        """Verify empty file is handled correctly"""
        # Create an empty temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            # Should not raise FileNotFoundError (file exists)
            # May raise other errors for empty file, but that's expected
            result = io_contracts.csv_schema_check(temp_path)
            self.assertEqual(result["size_bytes"], 0)

        except Exception as e:
            # Empty file may cause other errors, but not FileNotFoundError
            self.assertNotIsInstance(e, FileNotFoundError)

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestToolkitErrorHandling(unittest.TestCase):
    """Test that the main toolkit properly handles csv_schema_check errors"""

    def test_toolkit_handles_missing_file(self):
        """Verify toolkit exits cleanly with error message for missing file"""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "ai_tuner_toolkit_dyno_v1_2.py",
                "--csv",
                "uploads/missing/file.csv",
                "--outdir",
                "test_output",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        # Should exit with error code
        self.assertNotEqual(result.returncode, 0)

        # Should have clear error message in stderr
        self.assertIn("[ERROR]", result.stderr)
        self.assertIn("CSV file not found", result.stderr)
        self.assertIn("file.csv", result.stderr)

        # Should NOT have a Python traceback
        self.assertNotIn("Traceback (most recent call last)", result.stderr)


if __name__ == "__main__":
    unittest.main()
