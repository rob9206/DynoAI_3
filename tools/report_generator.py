"""
PDF Report Generator for DynoAI

This module generates professional PDF reports from dyno tuning data, including:
- Run metadata (date, operator, vehicle info)
- Before/after performance graphs
- VE correction summary tables
- Anomalies and warnings
- Confidence scores
- QR code with verification hash

The generated PDF is suitable for customer delivery and insurance documentation.
"""

import hashlib
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from templates import report_template

# Configure matplotlib to use non-interactive backend
matplotlib.use("Agg")

logger = logging.getLogger(__name__)


def generate_verification_hash(data: Dict[str, Any]) -> str:
    """
    Generate a SHA-256 hash for report verification.

    Args:
        data: Dictionary containing report data

    Returns:
        Hex string of SHA-256 hash
    """
    # Create a deterministic JSON string for hashing
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    hash_obj = hashlib.sha256(json_str.encode("utf-8"))
    return hash_obj.hexdigest()


def create_qr_code(data: str, size: int = 200) -> io.BytesIO:
    """
    Create a QR code image from data.

    Args:
        data: String data to encode in QR code
        size: Size of the QR code in pixels

    Returns:
        BytesIO object containing PNG image data
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to BytesIO
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return img_buffer


def create_performance_graph(
    torque_map: Optional[List[List[Optional[float]]]] = None,
    hp_map: Optional[List[List[Optional[float]]]] = None,
    rpm_bins: Optional[List[int]] = None,
    title: str = "Performance Map",
) -> io.BytesIO:
    """
    Create a performance graph from torque or HP data.

    Args:
        torque_map: 2D grid of torque values
        hp_map: 2D grid of HP values
        rpm_bins: List of RPM bin values
        title: Graph title

    Returns:
        BytesIO object containing PNG image data
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    if torque_map and rpm_bins:
        # Extract peak values across all load levels for each RPM
        peak_torque = []
        for row in torque_map:
            valid_values = [v for v in row if v is not None]
            if valid_values:
                peak_torque.append(max(valid_values))
            else:
                peak_torque.append(0)

        ax.plot(rpm_bins, peak_torque, "b-", linewidth=2, label="Torque (ft-lb)")

    if hp_map and rpm_bins:
        # Extract peak values across all load levels for each RPM
        peak_hp = []
        for row in hp_map:
            valid_values = [v for v in row if v is not None]
            if valid_values:
                peak_hp.append(max(valid_values))
            else:
                peak_hp.append(0)

        ax2 = ax.twinx()
        ax2.plot(rpm_bins, peak_hp, "r-", linewidth=2, label="HP")
        ax2.set_ylabel("HP", color="r")
        ax2.tick_params(axis="y", labelcolor="r")

    ax.set_xlabel("RPM")
    ax.set_ylabel("Torque (ft-lb)", color="b")
    ax.tick_params(axis="y", labelcolor="b")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    # Add legend
    lines1, labels1 = ax.get_legend_handles_labels()
    if hp_map:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="best")
    else:
        ax.legend(loc="best")

    plt.tight_layout()

    # Save to BytesIO
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_buffer.seek(0)

    return img_buffer


def create_ve_correction_table(
    ve_delta: List[List[Optional[float]]],
    rpm_bins: List[int],
    kpa_bins: List[int],
    max_rows: int = 10,
) -> Table:
    """
    Create a table showing VE correction values.

    Args:
        ve_delta: 2D grid of VE correction percentages
        rpm_bins: List of RPM bin values
        kpa_bins: List of kPa bin values
        max_rows: Maximum number of rows to include

    Returns:
        ReportLab Table object
    """
    # Create table header with kPa columns
    header = ["RPM"] + [f"{kpa} kPa" for kpa in kpa_bins]

    # Create table data
    table_data = [header]

    # Add rows (limit to max_rows)
    for i, rpm in enumerate(rpm_bins[:max_rows]):
        row = [str(rpm)]
        for value in ve_delta[i][: len(kpa_bins)]:
            if value is not None:
                row.append(f"{value:+.2f}%")
            else:
                row.append("--")
        table_data.append(row)

    # Create table with styling
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                # Body styling
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8F8F8")],
                ),
            ]
        )
    )

    return table


def generate_pdf_report(
    output_path: Path,
    run_data: Dict[str, Any],
    manifest: Dict[str, Any],
    anomalies: List[Dict[str, Any]],
    confidence_report: Dict[str, Any],
    ve_delta: List[List[Optional[float]]],
    torque_map: Optional[List[List[Optional[float]]]] = None,
    hp_map: Optional[List[List[Optional[float]]]] = None,
    rpm_bins: Optional[List[int]] = None,
    kpa_bins: Optional[List[int]] = None,
    shop_info: Optional[Dict[str, Any]] = None,
    disclaimer: Optional[str] = None,
) -> None:
    """
    Generate a professional PDF report from dyno tuning data.

    Args:
        output_path: Path where PDF should be saved
        run_data: Dictionary with run metadata (date, operator, vehicle, etc.)
        manifest: Complete manifest data from the run
        anomalies: List of detected anomalies
        confidence_report: Confidence score report
        ve_delta: VE correction grid
        torque_map: Optional torque map data
        hp_map: Optional HP map data
        rpm_bins: RPM bin values
        kpa_bins: kPa bin values
        shop_info: Optional shop/business information
        disclaimer: Optional custom disclaimer text
    """
    logger.info(f"Generating PDF report: {output_path}")

    # Use defaults if not provided
    if shop_info is None:
        shop_info = report_template.DEFAULT_SHOP_INFO.copy()
    if disclaimer is None:
        disclaimer = report_template.DEFAULT_DISCLAIMER

    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=report_template.MARGIN_LEFT,
        rightMargin=report_template.MARGIN_RIGHT,
        topMargin=report_template.MARGIN_TOP,
        bottomMargin=report_template.MARGIN_BOTTOM,
    )

    # Container for PDF elements
    story = []

    # Get styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=report_template.FONT_SIZE_TITLE,
        textColor=colors.HexColor("#1A334D"),
        spaceAfter=30,
        alignment=1,  # Center
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=report_template.FONT_SIZE_HEADING,
        textColor=colors.HexColor("#1A334D"),
        spaceAfter=12,
        spaceBefore=20,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=report_template.FONT_SIZE_BODY,
        spaceAfter=6,
    )

    # === COVER PAGE ===

    # Shop logo (if available)
    if shop_info.get("logo_path") and Path(shop_info["logo_path"]).exists():
        try:
            logo = Image(shop_info["logo_path"], width=2 * inch, height=1 * inch)
            story.append(logo)
            story.append(Spacer(1, 0.3 * inch))
        except Exception as e:
            logger.warning(f"Failed to load logo: {e}")

    # Title
    story.append(Paragraph("DynoAI Tuning Report", title_style))
    story.append(Spacer(1, 0.5 * inch))

    # Shop info
    if shop_info.get("name"):
        story.append(Paragraph(f"<b>{shop_info['name']}</b>", body_style))
    if shop_info.get("address"):
        story.append(Paragraph(shop_info["address"], body_style))
    if shop_info.get("phone"):
        story.append(Paragraph(f"Phone: {shop_info['phone']}", body_style))
    if shop_info.get("email"):
        story.append(Paragraph(f"Email: {shop_info['email']}", body_style))

    story.append(Spacer(1, 0.3 * inch))

    # Run metadata
    story.append(Paragraph("Run Information", heading_style))

    run_info_data = [
        ["Run ID:", run_data.get("run_id", "N/A")],
        ["Date:", run_data.get("date", "N/A")],
        ["Operator:", run_data.get("operator", "N/A")],
        ["Vehicle:", run_data.get("vehicle", "N/A")],
        ["Tool Version:", manifest.get("tool_version", "N/A")],
    ]

    run_info_table = Table(run_info_data, colWidths=[2 * inch, 4 * inch])
    run_info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(run_info_table)
    story.append(PageBreak())

    # === CONFIDENCE SCORE PAGE ===

    story.append(Paragraph("Tune Confidence Score", heading_style))
    story.append(Spacer(1, 0.2 * inch))

    # Main confidence score
    score = confidence_report.get("overall_score", 0)
    grade = confidence_report.get("letter_grade", "N/A")
    grade_desc = confidence_report.get("grade_description", "")

    score_color = report_template.get_confidence_color(score)
    score_hex = colors.HexColor(
        f"#{int(score_color[0] * 255):02x}{int(score_color[1] * 255):02x}{int(score_color[2] * 255):02x}"
    )

    score_style = ParagraphStyle(
        "ScoreStyle",
        parent=styles["Normal"],
        fontSize=48,
        textColor=score_hex,
        alignment=1,
        spaceAfter=12,
    )

    story.append(Paragraph(f"{score}%", score_style))
    story.append(Paragraph(f"<b>Grade: {grade}</b> - {grade_desc}", body_style))
    story.append(Spacer(1, 0.3 * inch))

    # Component scores
    story.append(Paragraph("Component Breakdown", heading_style))

    component_data = [["Component", "Score", "Weight"]]
    for component, data in confidence_report.get("component_scores", {}).items():
        component_data.append(
            [
                component.replace("_", " ").title(),
                f"{data['score']:.1f}%",
                f"{data['weight']}",
            ]
        )

    component_table = Table(
        component_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch]
    )
    component_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8F8F8")],
                ),
            ]
        )
    )

    story.append(component_table)
    story.append(Spacer(1, 0.3 * inch))

    # Recommendations
    if confidence_report.get("recommendations"):
        story.append(Paragraph("Recommendations", heading_style))
        for i, rec in enumerate(confidence_report["recommendations"], 1):
            story.append(Paragraph(f"{i}. {rec}", body_style))
        story.append(Spacer(1, 0.2 * inch))

    story.append(PageBreak())

    # === PERFORMANCE GRAPHS PAGE ===

    if torque_map and hp_map and rpm_bins:
        story.append(Paragraph("Performance Analysis", heading_style))
        story.append(Spacer(1, 0.2 * inch))

        # Create and add performance graph
        perf_graph = create_performance_graph(
            torque_map=torque_map,
            hp_map=hp_map,
            rpm_bins=rpm_bins,
            title="Peak Performance Curves",
        )

        perf_img = Image(perf_graph, width=6 * inch, height=3.75 * inch)
        story.append(perf_img)
        story.append(Spacer(1, 0.3 * inch))

        story.append(PageBreak())

    # === VE CORRECTION PAGE ===

    if ve_delta and rpm_bins and kpa_bins:
        story.append(Paragraph("VE Correction Summary", heading_style))
        story.append(Spacer(1, 0.2 * inch))

        story.append(
            Paragraph(
                "The following table shows the recommended VE correction percentages "
                "for each RPM and load cell. Positive values indicate enrichment needed, "
                "negative values indicate leaning needed.",
                body_style,
            )
        )
        story.append(Spacer(1, 0.2 * inch))

        ve_table = create_ve_correction_table(ve_delta, rpm_bins, kpa_bins)
        story.append(ve_table)
        story.append(Spacer(1, 0.2 * inch))

        if len(rpm_bins) > 10:
            story.append(
                Paragraph(
                    f"<i>Note: Showing first 10 of {len(rpm_bins)} RPM bins. "
                    "See CSV files for complete data.</i>",
                    body_style,
                )
            )

        story.append(PageBreak())

    # === ANOMALIES PAGE ===

    story.append(Paragraph("Anomalies and Warnings", heading_style))
    story.append(Spacer(1, 0.2 * inch))

    if not anomalies:
        story.append(
            Paragraph(
                "No significant anomalies detected. Data quality appears good.",
                body_style,
            )
        )
    else:
        story.append(
            Paragraph(
                f"Detected {len(anomalies)} anomalies that require attention:",
                body_style,
            )
        )
        story.append(Spacer(1, 0.1 * inch))

        for i, anomaly in enumerate(anomalies[:10], 1):  # Limit to 10 anomalies
            anom_type = anomaly.get("type", "Unknown")
            score = anomaly.get("score", 0)
            explanation = anomaly.get("explanation", "No explanation provided")

            story.append(
                Paragraph(f"<b>{i}. {anom_type}</b> (Score: {score})", body_style)
            )
            story.append(Paragraph(f"   {explanation}", body_style))
            story.append(Spacer(1, 0.1 * inch))

        if len(anomalies) > 10:
            story.append(
                Paragraph(
                    f"<i>Note: Showing first 10 of {len(anomalies)} anomalies. "
                    "See JSON files for complete data.</i>",
                    body_style,
                )
            )

    story.append(PageBreak())

    # === VERIFICATION PAGE ===

    story.append(Paragraph("Report Verification", heading_style))
    story.append(Spacer(1, 0.2 * inch))

    # Generate verification hash
    hash_data = {
        "run_id": run_data.get("run_id"),
        "date": run_data.get("date"),
        "confidence_score": confidence_report.get("overall_score"),
        "anomaly_count": len(anomalies),
    }

    verification_hash = generate_verification_hash(hash_data)

    story.append(
        Paragraph(f"<b>Verification Hash:</b> {verification_hash[:32]}...", body_style)
    )
    story.append(Spacer(1, 0.2 * inch))

    # Create QR code with verification data
    qr_data = json.dumps(
        {
            "run_id": run_data.get("run_id"),
            "hash": verification_hash,
            "date": run_data.get("date"),
        }
    )

    qr_code = create_qr_code(qr_data)
    qr_img = Image(qr_code, width=2 * inch, height=2 * inch)
    story.append(qr_img)
    story.append(Spacer(1, 0.2 * inch))

    story.append(
        Paragraph(
            "Scan this QR code to verify the authenticity of this report.", body_style
        )
    )

    story.append(PageBreak())

    # === DISCLAIMER PAGE ===

    story.append(Paragraph("Disclaimer", heading_style))
    story.append(Spacer(1, 0.2 * inch))

    disclaimer_style = ParagraphStyle(
        "DisclaimerStyle",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        alignment=4,  # Justify
    )

    story.append(Paragraph(disclaimer, disclaimer_style))

    # Build PDF
    doc.build(story)

    logger.info(f"PDF report generated successfully: {output_path}")
