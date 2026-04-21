"""
DynoAI Professional Report Generator

Generates customer-facing PDF reports with:
- Shop branding and logo
- Before/After power curves
- VE corrections summary
- AFR analysis heatmap
- Peak performance metrics

Uses ReportLab for PDF generation and Matplotlib for charts.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

matplotlib.use("Agg")  # Non-interactive backend for server

logger = logging.getLogger(__name__)


@dataclass
class ShopBranding:
    """Shop branding configuration for reports."""

    shop_name: str = "DynoAI Tuning"
    tagline: str = "Professional Dyno Tuning Services"
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    logo_path: Optional[str] = None
    primary_color: str = "#F59E0B"  # Amber
    secondary_color: str = "#1F2937"  # Dark gray
    accent_color: str = "#10B981"  # Emerald


@dataclass
class ReportData:
    """Data structure for report generation."""

    run_id: str
    customer_name: str = "Valued Customer"
    vehicle_info: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime("%B %d, %Y"))

    # Performance metrics
    peak_hp: float = 0.0
    peak_hp_rpm: float = 0.0
    peak_tq: float = 0.0
    peak_tq_rpm: float = 0.0

    # Baseline metrics (for comparison)
    baseline_hp: Optional[float] = None
    baseline_hp_rpm: Optional[float] = None
    baseline_tq: Optional[float] = None
    baseline_tq_rpm: Optional[float] = None

    # Power curve data
    power_curve: Optional[list[dict]] = None
    baseline_curve: Optional[list[dict]] = None

    # VE corrections
    ve_grid: Optional[list[dict]] = None
    afr_grid: Optional[list[dict]] = None
    hit_grid: Optional[list[dict]] = None

    # Analysis summary
    zones_corrected: int = 0
    max_correction_pct: float = 0.0
    mean_afr_error: float = 0.0

    # Confidence
    confidence_score: Optional[float] = None
    confidence_breakdown: Optional[dict] = None

    # Notes
    tuner_notes: str = ""


@dataclass
class ComparisonReportData:
    """Data structure for side-by-side comparison report generation."""

    run_a_id: str
    run_b_id: str
    customer_name: str = "Valued Customer"
    vehicle_info: str = ""
    tuner_notes: str = ""
    generated_at: str = field(
        default_factory=lambda: datetime.now().strftime("%B %d, %Y")
    )
    run_a_date: str = ""
    run_b_date: str = ""
    peaks_a: dict[str, float] = field(default_factory=dict)
    peaks_b: dict[str, float] = field(default_factory=dict)
    curve_a: list[dict[str, float]] = field(default_factory=list)
    curve_b: list[dict[str, float]] = field(default_factory=list)
    afr_a: list[dict[str, float]] = field(default_factory=list)
    afr_b: list[dict[str, float]] = field(default_factory=list)
    deltas: dict[str, float] = field(default_factory=dict)


def load_shop_branding(config_path: Optional[str] = None) -> ShopBranding:
    """Load shop branding from configuration file."""
    if config_path is None:
        # Default path
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "shop_branding.json"
        )
    else:
        config_path = Path(config_path)

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            return ShopBranding(**data)
        except Exception as e:
            logger.warning(f"Failed to load shop branding: {e}")

    return ShopBranding()


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color to RGB tuple (0-1 range)."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i: i + 2], 16) / 255.0 for i in (0, 2, 4))


class DynoReportGenerator:
    """
    Professional PDF report generator for DynoAI tuning sessions.

    Creates customer-ready reports with:
    - Shop branding and contact info
    - Performance summary (HP/TQ gains)
    - Before/After power curves
    - VE correction heatmap
    - AFR analysis visualization
    - Tuner notes and recommendations
    """

    # Standard grid dimensions
    RPM_BINS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000]
    MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100]

    def __init__(self, branding: Optional[ShopBranding] = None):
        """Initialize the report generator with optional branding."""
        self.branding = branding or load_shop_branding()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Title"],
                fontSize=28,
                spaceAfter=12,
                textColor=colors.HexColor(self.branding.secondary_color),
                alignment=TA_CENTER,
            )
        )

        # Section header
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading1"],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=10,
                textColor=colors.HexColor(self.branding.primary_color),
                borderColor=colors.HexColor(self.branding.primary_color),
                borderWidth=1,
                borderPadding=5,
            )
        )

        # Metric value
        self.styles.add(
            ParagraphStyle(
                name="MetricValue",
                parent=self.styles["Normal"],
                fontSize=24,
                alignment=TA_CENTER,
                textColor=colors.HexColor(self.branding.accent_color),
                fontName="Helvetica-Bold",
            )
        )

        # Metric label
        self.styles.add(
            ParagraphStyle(
                name="MetricLabel",
                parent=self.styles["Normal"],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.gray,
            )
        )

        # Footer
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.gray,
            )
        )

    def generate_report(
        self,
        data: ReportData,
        output_path: Optional[str] = None,
        include_heatmaps: bool = True,
        include_power_curve: bool = True,
    ) -> bytes:
        """
        Generate a professional PDF report.

        Args:
            data: Report data including run results
            output_path: Optional path to save PDF file
            include_heatmaps: Include VE/AFR heatmap visualizations
            include_power_curve: Include power curve chart

        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []

        # Header with branding
        story.extend(self._build_header(data))

        # Performance summary
        story.extend(self._build_performance_summary(data))

        # Power curves (if available)
        if include_power_curve and data.power_curve:
            story.extend(self._build_power_curves(data))

        # VE Corrections heatmap
        if include_heatmaps and data.ve_grid:
            story.append(PageBreak())
            story.extend(self._build_ve_heatmap(data))

        # AFR Analysis heatmap
        if include_heatmaps and data.afr_grid:
            story.extend(self._build_afr_heatmap(data))

        # Tuner notes and recommendations
        if data.tuner_notes:
            story.extend(self._build_notes_section(data))

        # Confidence score (if available)
        if data.confidence_score is not None:
            story.extend(self._build_confidence_section(data))

        # Footer
        story.extend(self._build_footer(data))

        # Build the PDF
        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Save to file if path provided
        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def _build_header(self, data: ReportData) -> list:
        """Build the report header with shop branding."""
        elements = []

        # Logo (if available)
        if self.branding.logo_path and Path(self.branding.logo_path).exists():
            try:
                logo = Image(self.branding.logo_path, width=2 * inch, height=1 * inch)
                logo.hAlign = "CENTER"
                elements.append(logo)
                elements.append(Spacer(1, 12))
            except Exception as e:
                logger.warning(f"Failed to load logo: {e}")

        # Shop name
        elements.append(Paragraph(self.branding.shop_name, self.styles["ReportTitle"]))

        # Tagline
        if self.branding.tagline:
            elements.append(
                Paragraph(f"<i>{self.branding.tagline}</i>", self.styles["Normal"])
            )

        elements.append(Spacer(1, 6))

        # Horizontal rule
        elements.append(
            HRFlowable(
                width="100%",
                thickness=2,
                color=colors.HexColor(self.branding.primary_color),
                spaceBefore=10,
                spaceAfter=20,
            )
        )

        # Customer/Vehicle info table
        info_data = [
            ["Customer:", data.customer_name, "Date:", data.date],
            ["Vehicle:", data.vehicle_info, "Run ID:", data.run_id],
        ]

        info_table = Table(
            info_data, colWidths=[1 * inch, 2.5 * inch, 0.8 * inch, 2.2 * inch]
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (0, -1),
                        colors.HexColor(self.branding.secondary_color),
                    ),
                    (
                        "TEXTCOLOR",
                        (2, 0),
                        (2, -1),
                        colors.HexColor(self.branding.secondary_color),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elements.append(info_table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_performance_summary(self, data: ReportData) -> list:
        """Build the performance summary section."""
        elements = []

        elements.append(Paragraph("Performance Summary", self.styles["SectionHeader"]))

        # Calculate gains if baseline available
        hp_gain = None
        tq_gain = None
        hp_gain_pct = None
        tq_gain_pct = None

        if data.baseline_hp and data.baseline_hp > 0:
            hp_gain = data.peak_hp - data.baseline_hp
            hp_gain_pct = (hp_gain / data.baseline_hp) * 100

        if data.baseline_tq and data.baseline_tq > 0:
            tq_gain = data.peak_tq - data.baseline_tq
            tq_gain_pct = (tq_gain / data.baseline_tq) * 100

        # Build metrics table
        metrics_data = []

        # Row 1: Values
        row1 = [
            Paragraph(f"<b>{data.peak_hp:.1f}</b>", self.styles["MetricValue"]),
            Paragraph(f"<b>{data.peak_tq:.1f}</b>", self.styles["MetricValue"]),
        ]

        if hp_gain is not None:
            gain_color = self.branding.accent_color if hp_gain > 0 else "#EF4444"
            row1.append(
                Paragraph(
                    f"<b>{'+' if hp_gain > 0 else ''}{hp_gain:.1f}</b>",
                    ParagraphStyle(
                        "GainValue",
                        parent=self.styles["MetricValue"],
                        textColor=colors.HexColor(gain_color),
                    ),
                )
            )

        if tq_gain is not None:
            gain_color = self.branding.accent_color if tq_gain > 0 else "#EF4444"
            row1.append(
                Paragraph(
                    f"<b>{'+' if tq_gain > 0 else ''}{tq_gain:.1f}</b>",
                    ParagraphStyle(
                        "GainValue",
                        parent=self.styles["MetricValue"],
                        textColor=colors.HexColor(gain_color),
                    ),
                )
            )

        metrics_data.append(row1)

        # Row 2: Labels
        row2 = [
            Paragraph("Peak HP", self.styles["MetricLabel"]),
            Paragraph("Peak Torque", self.styles["MetricLabel"]),
        ]
        if hp_gain is not None:
            row2.append(
                Paragraph(f"HP Gain ({hp_gain_pct:.1f}%)", self.styles["MetricLabel"])
            )
        if tq_gain is not None:
            row2.append(
                Paragraph(f"TQ Gain ({tq_gain_pct:.1f}%)", self.styles["MetricLabel"])
            )

        metrics_data.append(row2)

        # Row 3: RPM at peak
        row3 = [
            Paragraph(f"@ {data.peak_hp_rpm:.0f} RPM", self.styles["MetricLabel"]),
            Paragraph(f"@ {data.peak_tq_rpm:.0f} RPM", self.styles["MetricLabel"]),
        ]
        if hp_gain is not None:
            row3.append(Paragraph("", self.styles["MetricLabel"]))
        if tq_gain is not None:
            row3.append(Paragraph("", self.styles["MetricLabel"]))

        metrics_data.append(row3)

        col_width = 1.7 * inch
        metrics_table = Table(metrics_data, colWidths=[col_width] * len(row1))
        metrics_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    # Row 0 (values): more top padding
                    ("TOPPADDING", (0, 0), (-1, 0), 15),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                    # Row 1 (labels): tight padding
                    ("TOPPADDING", (0, 1), (-1, 1), 2),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
                    # Row 2 (RPM): more bottom padding
                    ("TOPPADDING", (0, 2), (-1, 2), 0),
                    ("BOTTOMPADDING", (0, 2), (-1, 2), 15),
                ]
            )
        )

        elements.append(metrics_table)
        elements.append(Spacer(1, 20))

        # Analysis stats
        if data.zones_corrected > 0:
            stats_text = (
                f"<b>Analysis:</b> {data.zones_corrected} zones corrected | "
                f"Max correction: {data.max_correction_pct:+.1f}% | "
                f"Mean AFR error: {data.mean_afr_error:.2f}"
            )
            elements.append(Paragraph(stats_text, self.styles["Normal"]))
            elements.append(Spacer(1, 10))

        return elements

    def _build_power_curves(self, data: ReportData) -> list:
        """Build the power curves chart."""
        elements = []

        elements.append(Paragraph("Power Curves", self.styles["SectionHeader"]))

        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
        fig.patch.set_facecolor("white")

        # Plot current run
        if data.power_curve:
            rpms = [p["rpm"] for p in data.power_curve]
            hps = [p.get("hp", 0) for p in data.power_curve]
            tqs = [p.get("tq", 0) for p in data.power_curve]

            ax.plot(
                rpms,
                hps,
                "-",
                color=self.branding.primary_color,
                linewidth=2.5,
                label=f"HP (Peak: {data.peak_hp:.1f})",
            )
            ax.plot(
                rpms,
                tqs,
                "-",
                color=self.branding.accent_color,
                linewidth=2.5,
                label=f"Torque (Peak: {data.peak_tq:.1f})",
            )

        # Plot baseline if available
        if data.baseline_curve:
            rpms_b = [p["rpm"] for p in data.baseline_curve]
            hps_b = [p.get("hp", 0) for p in data.baseline_curve]
            tqs_b = [p.get("tq", 0) for p in data.baseline_curve]

            ax.plot(
                rpms_b,
                hps_b,
                "--",
                color=self.branding.primary_color,
                linewidth=1.5,
                alpha=0.6,
                label="Baseline HP",
            )
            ax.plot(
                rpms_b,
                tqs_b,
                "--",
                color=self.branding.accent_color,
                linewidth=1.5,
                alpha=0.6,
                label="Baseline TQ",
            )

        ax.set_xlabel("RPM", fontsize=11, fontweight="bold")
        ax.set_ylabel("HP / lb-ft", fontsize=11, fontweight="bold")
        ax.set_title(
            "Dyno Power Curves",
            fontsize=14,
            fontweight="bold",
            color=self.branding.secondary_color,
        )
        ax.legend(loc="upper left", framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=1000)
        ax.set_ylim(bottom=0)

        # Add subtle background
        ax.set_facecolor("#FAFAFA")

        plt.tight_layout()

        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)

        # Add to PDF
        img = Image(img_buffer, width=6.5 * inch, height=3.7 * inch)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 20))

        return elements

    def _build_ve_heatmap(self, data: ReportData) -> list:
        """Build the VE corrections heatmap."""
        elements = []

        elements.append(
            Paragraph("VE Corrections Applied", self.styles["SectionHeader"])
        )

        if not data.ve_grid:
            elements.append(
                Paragraph("No VE correction data available.", self.styles["Normal"])
            )
            return elements

        # Convert grid to numpy array
        grid_data = []
        rpm_labels = []
        for row in data.ve_grid:
            rpm_labels.append(str(row["rpm"]))
            grid_data.append(row["values"])

        grid_array = np.array(grid_data)
        map_labels = [str(m) for m in self.MAP_BINS[: grid_array.shape[1]]]

        # Create heatmap
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

        # Custom colormap: blue (lean/negative) -> white (zero) -> red (rich/positive)
        cmap = plt.cm.RdBu_r
        vmax = max(abs(grid_array.min()), abs(grid_array.max()), 5)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

        im = ax.imshow(grid_array, cmap=cmap, norm=norm, aspect="auto")

        # Labels
        ax.set_xticks(np.arange(len(map_labels)))
        ax.set_yticks(np.arange(len(rpm_labels)))
        ax.set_xticklabels(map_labels)
        ax.set_yticklabels(rpm_labels)
        ax.set_xlabel("MAP (kPa)", fontsize=11, fontweight="bold")
        ax.set_ylabel("RPM", fontsize=11, fontweight="bold")
        ax.set_title(
            "VE Correction % by Zone",
            fontsize=14,
            fontweight="bold",
            color=self.branding.secondary_color,
        )

        # Add text annotations for significant corrections
        for i in range(len(rpm_labels)):
            for j in range(len(map_labels)):
                val = grid_array[i, j]
                if abs(val) > 0.5:  # Only annotate significant corrections
                    color = "white" if abs(val) > vmax * 0.6 else "black"
                    ax.text(
                        j,
                        i,
                        f"{val:.1f}",
                        ha="center",
                        va="center",
                        color=color,
                        fontsize=7,
                        fontweight="bold",
                    )

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("VE Correction %", fontsize=10)

        plt.tight_layout()

        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)

        img = Image(img_buffer, width=6.5 * inch, height=3.7 * inch)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 10))

        # Legend explanation
        elements.append(
            Paragraph(
                "<i>Blue zones indicate lean corrections (add fuel), "
                "Red zones indicate rich corrections (reduce fuel)</i>",
                ParagraphStyle(
                    "HeatmapLegend",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.gray,
                    alignment=TA_CENTER,
                ),
            )
        )
        elements.append(Spacer(1, 20))

        return elements

    def _build_afr_heatmap(self, data: ReportData) -> list:
        """Build the AFR error analysis heatmap."""
        elements = []

        elements.append(Paragraph("AFR Analysis", self.styles["SectionHeader"]))

        if not data.afr_grid:
            elements.append(
                Paragraph("No AFR analysis data available.", self.styles["Normal"])
            )
            return elements

        # Convert grid to numpy array
        grid_data = []
        rpm_labels = []
        for row in data.afr_grid:
            rpm_labels.append(str(row["rpm"]))
            grid_data.append(row["values"])

        grid_array = np.array(grid_data)
        map_labels = [str(m) for m in self.MAP_BINS[: grid_array.shape[1]]]

        # Create heatmap
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

        # Custom colormap for AFR error
        cmap = (
            plt.cm.RdYlGn_r
        )  # Red (lean) -> Yellow (ok) -> Green (slightly rich is OK)
        vmax = max(abs(grid_array.min()), abs(grid_array.max()), 2)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

        im = ax.imshow(grid_array, cmap=cmap, norm=norm, aspect="auto")

        # Labels
        ax.set_xticks(np.arange(len(map_labels)))
        ax.set_yticks(np.arange(len(rpm_labels)))
        ax.set_xticklabels(map_labels)
        ax.set_yticklabels(rpm_labels)
        ax.set_xlabel("MAP (kPa)", fontsize=11, fontweight="bold")
        ax.set_ylabel("RPM", fontsize=11, fontweight="bold")
        ax.set_title(
            "AFR Error by Zone (Measured - Target)",
            fontsize=14,
            fontweight="bold",
            color=self.branding.secondary_color,
        )

        # Add text annotations
        for i in range(len(rpm_labels)):
            for j in range(len(map_labels)):
                val = grid_array[i, j]
                if abs(val) > 0.3:
                    color = "white" if abs(val) > vmax * 0.6 else "black"
                    ax.text(
                        j,
                        i,
                        f"{val:.1f}",
                        ha="center",
                        va="center",
                        color=color,
                        fontsize=7,
                        fontweight="bold",
                    )

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("AFR Error", fontsize=10)

        plt.tight_layout()

        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)

        img = Image(img_buffer, width=6.5 * inch, height=3.7 * inch)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 10))

        # Legend explanation
        elements.append(
            Paragraph(
                "<i>Positive values (red) indicate lean condition, "
                "Negative values (green) indicate rich condition</i>",
                ParagraphStyle(
                    "HeatmapLegend",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.gray,
                    alignment=TA_CENTER,
                ),
            )
        )
        elements.append(Spacer(1, 20))

        return elements

    def _build_notes_section(self, data: ReportData) -> list:
        """Build the tuner notes section."""
        elements = []

        elements.append(
            Paragraph("Tuner Notes & Recommendations", self.styles["SectionHeader"])
        )

        # Notes in a bordered box
        notes_style = ParagraphStyle(
            "Notes",
            parent=self.styles["Normal"],
            fontSize=10,
            leading=14,
            spaceBefore=5,
            spaceAfter=5,
        )

        notes_table = Table(
            [[Paragraph(data.tuner_notes.replace("\n", "<br/>"), notes_style)]],
            colWidths=[6.5 * inch],
        )
        notes_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        1,
                        colors.HexColor(self.branding.primary_color),
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )

        elements.append(notes_table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_confidence_section(self, data: ReportData) -> list:
        """Build the confidence score section."""
        elements = []

        elements.append(
            Paragraph("Tune Confidence Score", self.styles["SectionHeader"])
        )

        # Confidence badge
        score = data.confidence_score
        if score >= 90:
            badge_color = "#10B981"  # Emerald
            badge_text = "Excellent"
        elif score >= 75:
            badge_color = "#3B82F6"  # Blue
            badge_text = "Good"
        elif score >= 60:
            badge_color = "#F59E0B"  # Amber
            badge_text = "Fair"
        else:
            badge_color = "#EF4444"  # Red
            badge_text = "Needs Work"

        score_style = ParagraphStyle(
            "ConfidenceScore",
            parent=self.styles["Normal"],
            fontSize=36,
            alignment=TA_CENTER,
            textColor=colors.HexColor(badge_color),
            fontName="Helvetica-Bold",
        )

        elements.append(Paragraph(f"{score:.0f}%", score_style))
        elements.append(
            Paragraph(
                f"<b>{badge_text}</b>",
                ParagraphStyle(
                    "Badge",
                    parent=self.styles["Normal"],
                    alignment=TA_CENTER,
                    fontSize=14,
                    textColor=colors.HexColor(badge_color),
                ),
            )
        )
        elements.append(Spacer(1, 10))

        # Breakdown if available
        if data.confidence_breakdown:
            breakdown_data = []
            for category, value in data.confidence_breakdown.items():
                category_name = category.replace("_", " ").title()
                breakdown_data.append([category_name, f"{value:.0f}%"])

            breakdown_table = Table(breakdown_data, colWidths=[3 * inch, 1.5 * inch])
            breakdown_table.setStyle(
                TableStyle(
                    [
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("TEXTCOLOR", (0, 0), (0, -1), colors.gray),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )

            elements.append(breakdown_table)

        elements.append(Spacer(1, 20))

        return elements

    def _build_footer(self, data: ReportData) -> list:
        """Build the report footer."""
        elements = []

        elements.append(
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#E5E7EB"),
                spaceBefore=20,
                spaceAfter=10,
            )
        )

        # Contact info
        contact_parts = []
        if self.branding.phone:
            contact_parts.append(f"📞 {self.branding.phone}")
        if self.branding.email:
            contact_parts.append(f"✉️ {self.branding.email}")
        if self.branding.website:
            contact_parts.append(f"🌐 {self.branding.website}")

        if contact_parts:
            elements.append(Paragraph(" | ".join(contact_parts), self.styles["Footer"]))

        if self.branding.address:
            elements.append(Paragraph(self.branding.address, self.styles["Footer"]))

        # Generated by
        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                f"Generated by DynoAI Professional | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                self.styles["Footer"],
            )
        )

        return elements

    def generate_comparison_report(
        self,
        data: ComparisonReportData,
        output_path: Optional[str] = None,
        include_afr: bool = True,
    ) -> bytes:
        """Generate a side-by-side comparison PDF."""
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = self.build_comparison_elements(data, include_afr=include_afr)
        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def build_comparison_elements(
        self,
        data: ComparisonReportData,
        include_afr: bool = True,
    ) -> list:
        """Build report elements for comparison report generation."""
        elements: list[Any] = []

        elements.append(Paragraph(self.branding.shop_name, self.styles["ReportTitle"]))
        elements.append(
            Paragraph("Run Comparison Report", self.styles["SectionHeader"])
        )
        elements.append(Spacer(1, 6))
        elements.append(
            HRFlowable(
                width="100%",
                thickness=2,
                color=colors.HexColor(self.branding.primary_color),
                spaceBefore=6,
                spaceAfter=12,
            )
        )

        info_data = [
            ["Customer:", data.customer_name, "Generated:", data.generated_at],
            ["Vehicle:", data.vehicle_info or "-", "Run A:", data.run_a_id],
            ["Run A Date:", data.run_a_date or "-", "Run B:", data.run_b_id],
            ["Run B Date:", data.run_b_date or "-", "", ""],
        ]
        info_table = Table(
            info_data, colWidths=[1.0 * inch, 2.5 * inch, 1.0 * inch, 2.0 * inch]
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (0, -1),
                        colors.HexColor(self.branding.secondary_color),
                    ),
                    (
                        "TEXTCOLOR",
                        (2, 0),
                        (2, -1),
                        colors.HexColor(self.branding.secondary_color),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(info_table)
        elements.append(Spacer(1, 12))

        elements.extend(self._build_comparison_peak_table(data))
        elements.extend(self._build_comparison_power_overlay(data))
        elements.extend(self._build_comparison_delta_chart(data))

        if include_afr and (data.afr_a or data.afr_b):
            elements.append(PageBreak())
            elements.extend(self._build_comparison_afr_overlay(data))

        if data.tuner_notes:
            elements.append(Paragraph("Tuner Notes", self.styles["SectionHeader"]))
            elements.append(Paragraph(data.tuner_notes, self.styles["Normal"]))
            elements.append(Spacer(1, 10))

        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                f"Generated by DynoAI Professional | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                self.styles["Footer"],
            )
        )

        return elements

    def _build_comparison_peak_table(self, data: ComparisonReportData) -> list:
        """Build run A/B peak comparison table."""
        elements: list[Any] = []
        elements.append(Paragraph("Peak Comparison", self.styles["SectionHeader"]))

        pa = data.peaks_a
        pb = data.peaks_b
        deltas = data.deltas
        table_data = [
            ["Metric", "Run A", "Run B", "Diff", "% Change"],
            [
                "Peak HP",
                f"{pa.get('peak_hp', 0):.1f}",
                f"{pb.get('peak_hp', 0):.1f}",
                f"{deltas.get('peak_hp_gain', 0):+.1f}",
                f"{deltas.get('pct_change_hp', 0):+.1f}%",
            ],
            [
                "Peak HP RPM",
                f"{pa.get('peak_hp_rpm', 0):.0f}",
                f"{pb.get('peak_hp_rpm', 0):.0f}",
                "-",
                "-",
            ],
            [
                "Peak TQ",
                f"{pa.get('peak_tq', 0):.1f}",
                f"{pb.get('peak_tq', 0):.1f}",
                f"{deltas.get('peak_tq_gain', 0):+.1f}",
                f"{deltas.get('pct_change_tq', 0):+.1f}%",
            ],
            [
                "Peak TQ RPM",
                f"{pa.get('peak_tq_rpm', 0):.0f}",
                f"{pb.get('peak_tq_rpm', 0):.0f}",
                "-",
                "-",
            ],
        ]
        table = Table(
            table_data,
            colWidths=[1.5 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(self.branding.secondary_color),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F9FAFB")],
                    ),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 14))
        return elements

    def _build_comparison_power_overlay(self, data: ComparisonReportData) -> list:
        """Build overlay charts for HP and TQ."""
        elements: list[Any] = []
        elements.append(Paragraph("Power Overlay", self.styles["SectionHeader"]))

        rpms = [p.get("rpm", 0) for p in data.curve_a]
        hp_a = [p.get("hp", 0) for p in data.curve_a]
        tq_a = [p.get("tq", 0) for p in data.curve_a]
        hp_b = [p.get("hp", 0) for p in data.curve_b]
        tq_b = [p.get("tq", 0) for p in data.curve_b]

        fig, axes = plt.subplots(2, 1, figsize=(7, 6), dpi=150, sharex=True)
        fig.patch.set_facecolor("white")

        axes[0].plot(
            rpms,
            hp_a,
            "-",
            linewidth=2.2,
            color=self.branding.primary_color,
            label=f"{data.run_a_id} HP",
        )
        axes[0].plot(
            rpms,
            hp_b,
            "--",
            linewidth=2.2,
            color=self.branding.accent_color,
            label=f"{data.run_b_id} HP",
        )
        axes[0].set_ylabel("HP", fontsize=10, fontweight="bold")
        axes[0].grid(True, alpha=0.25)
        axes[0].legend(loc="upper left", fontsize=8)

        axes[1].plot(
            rpms,
            tq_a,
            "-",
            linewidth=2.2,
            color=self.branding.primary_color,
            label=f"{data.run_a_id} TQ",
        )
        axes[1].plot(
            rpms,
            tq_b,
            "--",
            linewidth=2.2,
            color=self.branding.accent_color,
            label=f"{data.run_b_id} TQ",
        )
        axes[1].set_xlabel("RPM", fontsize=10, fontweight="bold")
        axes[1].set_ylabel("TQ", fontsize=10, fontweight="bold")
        axes[1].grid(True, alpha=0.25)
        axes[1].legend(loc="upper left", fontsize=8)

        for ax in axes:
            ax.set_xlim(left=1000)
            ax.set_ylim(bottom=0)
            ax.set_facecolor("#FAFAFA")

        plt.tight_layout()
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)
        chart = Image(img_buffer, width=6.5 * inch, height=5.2 * inch)
        chart.hAlign = "CENTER"
        elements.append(chart)
        elements.append(Spacer(1, 12))
        return elements

    def _build_comparison_delta_chart(self, data: ComparisonReportData) -> list:
        """Build delta chart (run B - run A) for HP and TQ."""
        elements: list[Any] = []
        elements.append(
            Paragraph("Delta by RPM (Run B - Run A)", self.styles["SectionHeader"])
        )

        rpms = [p.get("rpm", 0) for p in data.curve_a]
        hp_delta = [
            b.get("hp", 0) - a.get("hp", 0) for a, b in zip(data.curve_a, data.curve_b)
        ]
        tq_delta = [
            b.get("tq", 0) - a.get("tq", 0) for a, b in zip(data.curve_a, data.curve_b)
        ]

        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
        fig.patch.set_facecolor("white")
        ax.axhline(0, color="#6B7280", linewidth=1.0)
        ax.plot(
            rpms,
            hp_delta,
            "-",
            color=self.branding.primary_color,
            linewidth=2.0,
            label="HP Delta",
        )
        ax.plot(
            rpms,
            tq_delta,
            "-",
            color=self.branding.accent_color,
            linewidth=2.0,
            label="TQ Delta",
        )
        ax.set_xlabel("RPM", fontsize=10, fontweight="bold")
        ax.set_ylabel("Delta", fontsize=10, fontweight="bold")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", fontsize=8)
        ax.set_xlim(left=1000)
        ax.set_facecolor("#FAFAFA")

        plt.tight_layout()
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)
        chart = Image(img_buffer, width=6.5 * inch, height=3.1 * inch)
        chart.hAlign = "CENTER"
        elements.append(chart)
        elements.append(Spacer(1, 10))
        return elements

    def _build_comparison_afr_overlay(self, data: ComparisonReportData) -> list:
        """Build AFR front/rear comparison overlay."""
        elements: list[Any] = []
        elements.append(Paragraph("AFR Overlay", self.styles["SectionHeader"]))

        rpms = [p.get("rpm", 0) for p in data.afr_a]
        afr_f_a = [p.get("afr_front", 0) for p in data.afr_a]
        afr_r_a = [p.get("afr_rear", 0) for p in data.afr_a]
        afr_f_b = [p.get("afr_front", 0) for p in data.afr_b]
        afr_r_b = [p.get("afr_rear", 0) for p in data.afr_b]

        fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
        fig.patch.set_facecolor("white")
        ax.plot(
            rpms,
            afr_f_a,
            "-",
            linewidth=2.0,
            color=self.branding.primary_color,
            label=f"{data.run_a_id} AFR F",
        )
        ax.plot(
            rpms,
            afr_r_a,
            "-",
            linewidth=1.8,
            color=self.branding.primary_color,
            alpha=0.6,
            label=f"{data.run_a_id} AFR R",
        )
        ax.plot(
            rpms,
            afr_f_b,
            "--",
            linewidth=2.0,
            color=self.branding.accent_color,
            label=f"{data.run_b_id} AFR F",
        )
        ax.plot(
            rpms,
            afr_r_b,
            "--",
            linewidth=1.8,
            color=self.branding.accent_color,
            alpha=0.6,
            label=f"{data.run_b_id} AFR R",
        )
        ax.set_xlabel("RPM", fontsize=10, fontweight="bold")
        ax.set_ylabel("AFR", fontsize=10, fontweight="bold")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right", fontsize=7)
        ax.set_xlim(left=1000)
        ax.set_ylim(bottom=9.0, top=18.0)
        ax.set_facecolor("#FAFAFA")

        plt.tight_layout()
        img_buffer = io.BytesIO()
        fig.savefig(
            img_buffer,
            format="png",
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
        img_buffer.seek(0)
        chart = Image(img_buffer, width=6.5 * inch, height=3.3 * inch)
        chart.hAlign = "CENTER"
        elements.append(chart)
        elements.append(Spacer(1, 10))
        return elements


def generate_report_from_run(
    run_id: str,
    runs_dir: str = "runs",
    customer_name: str = "Valued Customer",
    vehicle_info: str = "",
    tuner_notes: str = "",
    baseline_run_id: Optional[str] = None,
    output_path: Optional[str] = None,
    branding: Optional[ShopBranding] = None,
) -> bytes:
    """
    Generate a PDF report from a run directory.

    Args:
        run_id: The run ID to generate report for
        runs_dir: Base runs directory
        customer_name: Customer name for report
        vehicle_info: Vehicle description
        tuner_notes: Tuner notes/recommendations
        baseline_run_id: Optional baseline run for comparison
        output_path: Optional path to save PDF
        branding: Optional shop branding config

    Returns:
        PDF content as bytes
    """
    runs_path = Path(runs_dir)
    run_path = runs_path / run_id

    if not run_path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")

    # Load manifest
    manifest_path = run_path / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    # Extract data from manifest
    analysis = manifest.get("analysis", {})

    # Load grids
    def load_grid(filename: str) -> Optional[list[dict]]:
        grid_path = run_path / filename
        if not grid_path.exists():
            return None
        grid = []
        with open(grid_path) as f:
            lines = f.readlines()
            for line in lines[1:]:  # Skip header
                parts = line.strip().split(",")
                if parts:
                    try:
                        values = [float(v) if v else 0.0 for v in parts[1:]]
                        grid.append({"rpm": int(parts[0]), "values": values})
                    except (ValueError, IndexError):
                        continue
        return grid if grid else None

    ve_grid = load_grid("VE_Corrections_2D.csv")
    afr_grid = load_grid("AFR_Error_2D.csv")
    hit_grid = load_grid("Hit_Count_2D.csv")

    # Load confidence
    confidence_score = None
    confidence_breakdown = None
    confidence_path = run_path / "ConfidenceReport.json"
    if confidence_path.exists():
        with open(confidence_path) as f:
            conf_data = json.load(f)
            confidence_score = conf_data.get("overall_score", 0)
            confidence_breakdown = conf_data.get("breakdown", {})

    # Load power curve
    power_curve = analysis.get("power_curve")

    # Load baseline if specified
    baseline_curve = None
    baseline_hp = None
    baseline_tq = None
    baseline_hp_rpm = None
    baseline_tq_rpm = None

    if baseline_run_id:
        baseline_path = runs_path / baseline_run_id / "manifest.json"
        if baseline_path.exists():
            with open(baseline_path) as f:
                baseline_manifest = json.load(f)
                baseline_analysis = baseline_manifest.get("analysis", {})
                baseline_curve = baseline_analysis.get("power_curve")
                baseline_hp = baseline_analysis.get("peak_hp", 0)
                baseline_tq = baseline_analysis.get("peak_tq", 0)
                baseline_hp_rpm = baseline_analysis.get("peak_hp_rpm", 0)
                baseline_tq_rpm = baseline_analysis.get("peak_tq_rpm", 0)

    # Build report data
    report_data = ReportData(
        run_id=run_id,
        customer_name=customer_name,
        vehicle_info=vehicle_info,
        peak_hp=analysis.get("peak_hp", 0),
        peak_hp_rpm=analysis.get("peak_hp_rpm", 0),
        peak_tq=analysis.get("peak_tq", 0),
        peak_tq_rpm=analysis.get("peak_tq_rpm", 0),
        baseline_hp=baseline_hp,
        baseline_hp_rpm=baseline_hp_rpm,
        baseline_tq=baseline_tq,
        baseline_tq_rpm=baseline_tq_rpm,
        power_curve=power_curve,
        baseline_curve=baseline_curve,
        ve_grid=ve_grid,
        afr_grid=afr_grid,
        hit_grid=hit_grid,
        zones_corrected=analysis.get("zones_corrected", 0),
        max_correction_pct=analysis.get("max_correction_pct", 0),
        mean_afr_error=analysis.get("mean_afr_error", 0),
        confidence_score=confidence_score,
        confidence_breakdown=confidence_breakdown,
        tuner_notes=tuner_notes,
    )

    # Generate report
    generator = DynoReportGenerator(branding)
    return generator.generate_report(report_data, output_path)


def _safe_float(value: Any) -> Optional[float]:
    """Parse float safely; returns None for invalid values."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_date_from_manifest_or_mtime(run_path: Path, manifest: dict[str, Any]) -> str:
    """Get a human-readable run date from manifest or directory mtime."""
    created_at = manifest.get("created_at")
    if isinstance(created_at, str) and created_at.strip():
        return created_at
    try:
        return datetime.fromtimestamp(run_path.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )
    except OSError:
        return datetime.now().strftime("%Y-%m-%d %H:%M")


def _extract_peaks_from_curve(curve: list[dict[str, float]]) -> dict[str, float]:
    """Extract peak HP/TQ and their RPM locations from binned curve rows."""
    if not curve:
        return {
            "peak_hp": 0.0,
            "peak_hp_rpm": 0.0,
            "peak_tq": 0.0,
            "peak_tq_rpm": 0.0,
        }

    hp_row = max(curve, key=lambda row: row.get("hp", 0.0))
    tq_row = max(curve, key=lambda row: row.get("tq", 0.0))
    return {
        "peak_hp": hp_row.get("hp", 0.0),
        "peak_hp_rpm": hp_row.get("rpm", 0.0),
        "peak_tq": tq_row.get("tq", 0.0),
        "peak_tq_rpm": tq_row.get("rpm", 0.0),
    }


def _load_comparison_run(
    run_id: str,
    runs_dir: Path,
) -> tuple[dict[str, float], list[dict[str, float]], list[dict[str, float]], str]:
    """
    Load comparison-friendly curve data from runs/<id>/run.csv with manifest fallback.
    """
    run_path = runs_dir / run_id
    if not run_path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")

    manifest: dict[str, Any] = {}
    manifest_path = run_path / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    csv_path = run_path / "run.csv"
    analysis = manifest.get("analysis", {})
    date_text = _run_date_from_manifest_or_mtime(run_path, manifest)

    if not csv_path.exists():
        fallback_curve = analysis.get("power_curve") or []
        curve_rows = [
            {
                "rpm": _safe_float(p.get("rpm")) or 0.0,
                "hp": _safe_float(p.get("hp")) or 0.0,
                "tq": _safe_float(p.get("tq")) or 0.0,
            }
            for p in fallback_curve
            if isinstance(p, dict)
        ]
        peaks = {
            "peak_hp": _safe_float(analysis.get("peak_hp")) or 0.0,
            "peak_hp_rpm": _safe_float(analysis.get("peak_hp_rpm")) or 0.0,
            "peak_tq": _safe_float(analysis.get("peak_tq")) or 0.0,
            "peak_tq_rpm": _safe_float(analysis.get("peak_tq_rpm")) or 0.0,
        }
        if curve_rows and peaks["peak_hp"] <= 0 and peaks["peak_tq"] <= 0:
            peaks = _extract_peaks_from_curve(curve_rows)
        return peaks, curve_rows, [], date_text

    df = pd.read_csv(csv_path)
    rpm_col = "Engine RPM"
    hp_col = "Horsepower"
    tq_col = "Torque"
    afr_f_col = "AFR Meas F"
    afr_r_col = "AFR Meas R"

    for col in [rpm_col, hp_col, tq_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    valid = df[[rpm_col, hp_col, tq_col]].dropna()
    if valid.empty:
        fallback_curve = analysis.get("power_curve") or []
        curve_rows = [
            {
                "rpm": _safe_float(p.get("rpm")) or 0.0,
                "hp": _safe_float(p.get("hp")) or 0.0,
                "tq": _safe_float(p.get("tq")) or 0.0,
            }
            for p in fallback_curve
            if isinstance(p, dict)
        ]
        peaks = {
            "peak_hp": _safe_float(analysis.get("peak_hp")) or 0.0,
            "peak_hp_rpm": _safe_float(analysis.get("peak_hp_rpm")) or 0.0,
            "peak_tq": _safe_float(analysis.get("peak_tq")) or 0.0,
            "peak_tq_rpm": _safe_float(analysis.get("peak_tq_rpm")) or 0.0,
        }
        return peaks, curve_rows, [], date_text

    bin_values = np.array(DynoReportGenerator.RPM_BINS, dtype=float)
    valid = valid.copy()
    valid["rpm_bin"] = valid[rpm_col].apply(
        lambda v: float(bin_values[np.abs(bin_values - float(v)).argmin()])
    )
    grouped = valid.groupby("rpm_bin", dropna=True).agg(
        hp=(hp_col, "max"),
        tq=(tq_col, "max"),
    )

    curve_rows: list[dict[str, float]] = []
    for rpm in DynoReportGenerator.RPM_BINS:
        hp = float(grouped.at[float(rpm), "hp"]) if float(rpm) in grouped.index else 0.0
        tq = float(grouped.at[float(rpm), "tq"]) if float(rpm) in grouped.index else 0.0
        curve_rows.append({"rpm": float(rpm), "hp": hp, "tq": tq})

    peaks = _extract_peaks_from_curve(curve_rows)
    peaks_manifest = {
        "peak_hp": _safe_float(analysis.get("peak_hp")) or 0.0,
        "peak_hp_rpm": _safe_float(analysis.get("peak_hp_rpm")) or 0.0,
        "peak_tq": _safe_float(analysis.get("peak_tq")) or 0.0,
        "peak_tq_rpm": _safe_float(analysis.get("peak_tq_rpm")) or 0.0,
    }
    if peaks["peak_hp"] <= 0 and peaks_manifest["peak_hp"] > 0:
        peaks = peaks_manifest

    afr_rows: list[dict[str, float]] = []
    if afr_f_col in df.columns or afr_r_col in df.columns:
        afr_df = df[
            [rpm_col] + [c for c in [afr_f_col, afr_r_col] if c in df.columns]
        ].copy()
        afr_df[rpm_col] = pd.to_numeric(afr_df[rpm_col], errors="coerce")
        for c in [afr_f_col, afr_r_col]:
            if c in afr_df.columns:
                afr_df[c] = pd.to_numeric(afr_df[c], errors="coerce")
        afr_df = afr_df.dropna(subset=[rpm_col])
        if not afr_df.empty:
            afr_df["rpm_bin"] = afr_df[rpm_col].apply(
                lambda v: float(bin_values[np.abs(bin_values - float(v)).argmin()])
            )
            agg_spec: dict[str, tuple[str, str]] = {}
            if afr_f_col in afr_df.columns:
                agg_spec["afr_front"] = (afr_f_col, "mean")
            if afr_r_col in afr_df.columns:
                agg_spec["afr_rear"] = (afr_r_col, "mean")
            afr_grouped = afr_df.groupby("rpm_bin", dropna=True).agg(**agg_spec)
            for rpm in DynoReportGenerator.RPM_BINS:
                row: dict[str, float] = {"rpm": float(rpm)}
                if float(rpm) in afr_grouped.index:
                    if "afr_front" in afr_grouped.columns:
                        row["afr_front"] = float(
                            afr_grouped.at[float(rpm), "afr_front"]
                        )
                    if "afr_rear" in afr_grouped.columns:
                        row["afr_rear"] = float(afr_grouped.at[float(rpm), "afr_rear"])
                else:
                    row["afr_front"] = 0.0
                    row["afr_rear"] = 0.0
                afr_rows.append(row)

    return peaks, curve_rows, afr_rows, date_text


def _comparison_deltas(
    peaks_a: dict[str, float], peaks_b: dict[str, float]
) -> dict[str, float]:
    """Compute peak HP/TQ absolute and percent deltas (B - A)."""
    hp_a = peaks_a.get("peak_hp", 0.0) or 0.0
    hp_b = peaks_b.get("peak_hp", 0.0) or 0.0
    tq_a = peaks_a.get("peak_tq", 0.0) or 0.0
    tq_b = peaks_b.get("peak_tq", 0.0) or 0.0

    hp_gain = hp_b - hp_a
    tq_gain = tq_b - tq_a
    return {
        "peak_hp_gain": hp_gain,
        "peak_tq_gain": tq_gain,
        "pct_change_hp": (hp_gain / hp_a * 100.0) if hp_a > 0 else 0.0,
        "pct_change_tq": (tq_gain / tq_a * 100.0) if tq_a > 0 else 0.0,
    }


def get_comparison_summary_from_runs(
    run_a_id: str,
    run_b_id: str,
    runs_dir: str = "runs",
) -> dict[str, Any]:
    """Load peaks and deltas for API JSON responses."""
    runs_path = Path(runs_dir)
    peaks_a, _, _, _ = _load_comparison_run(run_a_id, runs_path)
    peaks_b, _, _, _ = _load_comparison_run(run_b_id, runs_path)
    deltas = _comparison_deltas(peaks_a, peaks_b)
    return {
        "run_a": peaks_a,
        "run_b": peaks_b,
        "deltas": deltas,
    }


def generate_comparison_report_from_runs(
    run_a_id: str,
    run_b_id: str,
    runs_dir: str = "runs",
    customer_name: str = "Valued Customer",
    vehicle_info: str = "",
    tuner_notes: str = "",
    include_afr: bool = True,
    branding: Optional[ShopBranding] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate comparison PDF from two run IDs."""
    runs_path = Path(runs_dir)
    peaks_a, curve_a, afr_a, run_a_date = _load_comparison_run(run_a_id, runs_path)
    peaks_b, curve_b, afr_b, run_b_date = _load_comparison_run(run_b_id, runs_path)
    deltas = _comparison_deltas(peaks_a, peaks_b)

    payload = ComparisonReportData(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        customer_name=customer_name,
        vehicle_info=vehicle_info,
        tuner_notes=tuner_notes,
        run_a_date=run_a_date,
        run_b_date=run_b_date,
        peaks_a=peaks_a,
        peaks_b=peaks_b,
        curve_a=curve_a,
        curve_b=curve_b,
        afr_a=afr_a,
        afr_b=afr_b,
        deltas=deltas,
    )

    generator = DynoReportGenerator(branding)
    return generator.generate_comparison_report(
        payload,
        output_path=output_path,
        include_afr=include_afr,
    )
