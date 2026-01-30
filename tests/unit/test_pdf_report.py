#!/usr/bin/env python3
"""
Test suite for PDF report generator

This test validates the PDF report generation functionality.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import the constants needed
from dynoai.constants import KPA_BINS, RPM_BINS

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPDFReportGenerator(unittest.TestCase):
    """Test PDF report generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

        # Sample data for testing
        self.run_data = {
            "run_id": "test_run_001",
            "date": "2024-01-15T10:30:00Z",
            "operator": "Test Operator",
            "vehicle": "2020 Test Vehicle",
        }

        self.manifest = {
            "tool_version": "1.2",
            "run_id": "test_run_001",
        }

        self.anomalies = [
            {
                "type": "high_correction",
                "score": 4.5,
                "explanation": "Large VE correction needed in mid-range",
                "cell": {"rpm": 3000, "kpa": 75},
            }
        ]

        self.confidence_report = {
            "overall_score": 85.5,
            "letter_grade": "B+",
            "grade_description": "Good tune with minor areas to improve",
            "component_scores": {
                "coverage": {
                    "score": 90.0,
                    "weight": 0.35,
                    "details": {"front_cells": 40, "rear_cells": 40},
                },
                "consistency": {
                    "score": 82.0,
                    "weight": 0.30,
                    "details": {"avg_mad": 0.45},
                },
                "quality": {"score": 84.0, "weight": 0.35, "details": {"anomalies": 1}},
            },
            "recommendations": [
                "Collect more data in cruise region",
                "Monitor for knock",
            ],
            "weak_areas": [],
        }

        # Create sample VE delta grid (9x5)
        self.ve_delta = [
            [1.5 if (i + j) % 2 == 0 else -1.2 for j in range(len(KPA_BINS))]
            for i in range(len(RPM_BINS))
        ]

        # Create sample torque/hp maps
        self.torque_map = [
            [50.0 + i * 5 + j * 2 for j in range(len(KPA_BINS))]
            for i in range(len(RPM_BINS))
        ]
        self.hp_map = [
            [40.0 + i * 4 + j * 1.5 for j in range(len(KPA_BINS))]
            for i in range(len(RPM_BINS))
        ]

    def tearDown(self):
        """Clean up test files"""
        import shutil

        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_pdf_report_generation_basic(self):
        """Test basic PDF report generation"""
        try:
            from report_generator import generate_pdf_report
        except ImportError:
            self.skipTest("report_generator module not available")

        output_path = Path(self.temp_dir) / "test_report.pdf"

        # Generate PDF
        generate_pdf_report(
            output_path=output_path,
            run_data=self.run_data,
            manifest=self.manifest,
            anomalies=self.anomalies,
            confidence_report=self.confidence_report,
            ve_delta=self.ve_delta,
            torque_map=self.torque_map,
            hp_map=self.hp_map,
            rpm_bins=RPM_BINS,
            kpa_bins=KPA_BINS,
        )

        # Verify PDF was created
        self.assertTrue(output_path.exists(), "PDF file should be created")

        # Verify file size is reasonable (> 10KB, < 5MB)
        file_size = output_path.stat().st_size
        self.assertGreater(file_size, 10000, "PDF should be larger than 10KB")
        self.assertLess(file_size, 5 * 1024 * 1024, "PDF should be smaller than 5MB")

        # Verify it's a valid PDF (starts with %PDF)
        with open(output_path, "rb") as f:
            header = f.read(4)
            self.assertEqual(header, b"%PDF", "File should be a valid PDF")

    def test_pdf_report_with_shop_info(self):
        """Test PDF report generation with custom shop info"""
        try:
            from report_generator import generate_pdf_report
        except ImportError:
            self.skipTest("report_generator module not available")

        output_path = Path(self.temp_dir) / "test_report_shop.pdf"

        shop_info = {
            "name": "Test Tuning Shop",
            "address": "123 Main St, Test City, TS 12345",
            "phone": "555-1234",
            "email": "test@testshop.com",
            "website": "https://testshop.com",
            "logo_path": None,
        }

        # Generate PDF
        generate_pdf_report(
            output_path=output_path,
            run_data=self.run_data,
            manifest=self.manifest,
            anomalies=self.anomalies,
            confidence_report=self.confidence_report,
            ve_delta=self.ve_delta,
            torque_map=self.torque_map,
            hp_map=self.hp_map,
            rpm_bins=RPM_BINS,
            kpa_bins=KPA_BINS,
            shop_info=shop_info,
        )

        # Verify PDF was created
        self.assertTrue(output_path.exists(), "PDF file should be created")

        # Verify file size
        file_size = output_path.stat().st_size
        self.assertGreater(file_size, 10000, "PDF should be larger than 10KB")

    def test_pdf_report_no_anomalies(self):
        """Test PDF report generation with no anomalies"""
        try:
            from report_generator import generate_pdf_report
        except ImportError:
            self.skipTest("report_generator module not available")

        output_path = Path(self.temp_dir) / "test_report_clean.pdf"

        # Generate PDF with no anomalies
        generate_pdf_report(
            output_path=output_path,
            run_data=self.run_data,
            manifest=self.manifest,
            anomalies=[],  # No anomalies
            confidence_report=self.confidence_report,
            ve_delta=self.ve_delta,
            torque_map=self.torque_map,
            hp_map=self.hp_map,
            rpm_bins=RPM_BINS,
            kpa_bins=KPA_BINS,
        )

        # Verify PDF was created
        self.assertTrue(output_path.exists(), "PDF file should be created")

    def test_verification_hash_generation(self):
        """Test verification hash generation"""
        try:
            from report_generator import generate_verification_hash
        except ImportError:
            self.skipTest("report_generator module not available")

        data = {"run_id": "test_001", "score": 85}
        hash1 = generate_verification_hash(data)
        hash2 = generate_verification_hash(data)

        # Same data should produce same hash
        self.assertEqual(hash1, hash2)

        # Hash should be 64 characters (SHA-256 in hex)
        self.assertEqual(len(hash1), 64)

    def test_qr_code_generation(self):
        """Test QR code generation"""
        try:
            from report_generator import create_qr_code
        except ImportError:
            self.skipTest("report_generator module not available")

        qr_data = "test_data_12345"
        qr_buffer = create_qr_code(qr_data)

        # Verify we got a BytesIO object with PNG data
        self.assertIsNotNone(qr_buffer)
        qr_buffer.seek(0)
        header = qr_buffer.read(8)

        # PNG magic number
        self.assertEqual(header[:4], b"\x89PNG")


if __name__ == "__main__":
    unittest.main()
