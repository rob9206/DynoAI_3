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
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker

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


def load_shop_branding(config_path: Optional[str] = None) -> ShopBranding:
    """Load shop branding from configuration file."""
    if config_path is None:
        # Default path
        config_path = Path(__file__).parent.parent.parent / "config" / "shop_branding.json"
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
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


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
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=28,
            spaceAfter=12,
            textColor=colors.HexColor(self.branding.secondary_color),
            alignment=TA_CENTER
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor(self.branding.primary_color),
            borderColor=colors.HexColor(self.branding.primary_color),
            borderWidth=1,
            borderPadding=5
        ))
        
        # Metric value
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor(self.branding.accent_color),
            fontName='Helvetica-Bold'
        ))
        
        # Metric label
        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.gray
        ))
        
        # Footer
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.gray
        ))
    
    def generate_report(
        self, 
        data: ReportData,
        output_path: Optional[str] = None,
        include_heatmaps: bool = True,
        include_power_curve: bool = True
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
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
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
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    def _build_header(self, data: ReportData) -> list:
        """Build the report header with shop branding."""
        elements = []
        
        # Logo (if available)
        if self.branding.logo_path and Path(self.branding.logo_path).exists():
            try:
                logo = Image(self.branding.logo_path, width=2*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 12))
            except Exception as e:
                logger.warning(f"Failed to load logo: {e}")
        
        # Shop name
        elements.append(Paragraph(self.branding.shop_name, self.styles['ReportTitle']))
        
        # Tagline
        if self.branding.tagline:
            elements.append(Paragraph(
                f"<i>{self.branding.tagline}</i>",
                self.styles['Normal']
            ))
        
        elements.append(Spacer(1, 6))
        
        # Horizontal rule
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor(self.branding.primary_color),
            spaceBefore=10,
            spaceAfter=20
        ))
        
        # Customer/Vehicle info table
        info_data = [
            ['Customer:', data.customer_name, 'Date:', data.date],
            ['Vehicle:', data.vehicle_info, 'Run ID:', data.run_id],
        ]
        
        info_table = Table(info_data, colWidths=[1*inch, 2.5*inch, 0.8*inch, 2.2*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor(self.branding.secondary_color)),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor(self.branding.secondary_color)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_performance_summary(self, data: ReportData) -> list:
        """Build the performance summary section."""
        elements = []
        
        elements.append(Paragraph("Performance Summary", self.styles['SectionHeader']))
        
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
            Paragraph(f"<b>{data.peak_hp:.1f}</b>", self.styles['MetricValue']),
            Paragraph(f"<b>{data.peak_tq:.1f}</b>", self.styles['MetricValue']),
        ]
        
        if hp_gain is not None:
            gain_color = self.branding.accent_color if hp_gain > 0 else "#EF4444"
            row1.append(Paragraph(
                f"<b>{'+' if hp_gain > 0 else ''}{hp_gain:.1f}</b>",
                ParagraphStyle('GainValue', parent=self.styles['MetricValue'],
                              textColor=colors.HexColor(gain_color))
            ))
        
        if tq_gain is not None:
            gain_color = self.branding.accent_color if tq_gain > 0 else "#EF4444"
            row1.append(Paragraph(
                f"<b>{'+' if tq_gain > 0 else ''}{tq_gain:.1f}</b>",
                ParagraphStyle('GainValue', parent=self.styles['MetricValue'],
                              textColor=colors.HexColor(gain_color))
            ))
        
        metrics_data.append(row1)
        
        # Row 2: Labels
        row2 = [
            Paragraph("Peak HP", self.styles['MetricLabel']),
            Paragraph("Peak Torque", self.styles['MetricLabel']),
        ]
        if hp_gain is not None:
            row2.append(Paragraph(f"HP Gain ({hp_gain_pct:.1f}%)", self.styles['MetricLabel']))
        if tq_gain is not None:
            row2.append(Paragraph(f"TQ Gain ({tq_gain_pct:.1f}%)", self.styles['MetricLabel']))
        
        metrics_data.append(row2)
        
        # Row 3: RPM at peak
        row3 = [
            Paragraph(f"@ {data.peak_hp_rpm:.0f} RPM", self.styles['MetricLabel']),
            Paragraph(f"@ {data.peak_tq_rpm:.0f} RPM", self.styles['MetricLabel']),
        ]
        if hp_gain is not None:
            row3.append(Paragraph("", self.styles['MetricLabel']))
        if tq_gain is not None:
            row3.append(Paragraph("", self.styles['MetricLabel']))
        
        metrics_data.append(row3)
        
        col_width = 1.7*inch
        metrics_table = Table(metrics_data, colWidths=[col_width] * len(row1))
        metrics_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            # Row 0 (values): more top padding
            ('TOPPADDING', (0, 0), (-1, 0), 15),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            # Row 1 (labels): tight padding
            ('TOPPADDING', (0, 1), (-1, 1), 2),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 2),
            # Row 2 (RPM): more bottom padding
            ('TOPPADDING', (0, 2), (-1, 2), 0),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 15),
        ]))
        
        elements.append(metrics_table)
        elements.append(Spacer(1, 20))
        
        # Analysis stats
        if data.zones_corrected > 0:
            stats_text = (
                f"<b>Analysis:</b> {data.zones_corrected} zones corrected | "
                f"Max correction: {data.max_correction_pct:+.1f}% | "
                f"Mean AFR error: {data.mean_afr_error:.2f}"
            )
            elements.append(Paragraph(stats_text, self.styles['Normal']))
            elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_power_curves(self, data: ReportData) -> list:
        """Build the power curves chart."""
        elements = []
        
        elements.append(Paragraph("Power Curves", self.styles['SectionHeader']))
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
        fig.patch.set_facecolor('white')
        
        # Plot current run
        if data.power_curve:
            rpms = [p['rpm'] for p in data.power_curve]
            hps = [p.get('hp', 0) for p in data.power_curve]
            tqs = [p.get('tq', 0) for p in data.power_curve]
            
            ax.plot(rpms, hps, '-', color=self.branding.primary_color, 
                   linewidth=2.5, label=f'HP (Peak: {data.peak_hp:.1f})')
            ax.plot(rpms, tqs, '-', color=self.branding.accent_color,
                   linewidth=2.5, label=f'Torque (Peak: {data.peak_tq:.1f})')
        
        # Plot baseline if available
        if data.baseline_curve:
            rpms_b = [p['rpm'] for p in data.baseline_curve]
            hps_b = [p.get('hp', 0) for p in data.baseline_curve]
            tqs_b = [p.get('tq', 0) for p in data.baseline_curve]
            
            ax.plot(rpms_b, hps_b, '--', color=self.branding.primary_color,
                   linewidth=1.5, alpha=0.6, label='Baseline HP')
            ax.plot(rpms_b, tqs_b, '--', color=self.branding.accent_color,
                   linewidth=1.5, alpha=0.6, label='Baseline TQ')
        
        ax.set_xlabel('RPM', fontsize=11, fontweight='bold')
        ax.set_ylabel('HP / lb-ft', fontsize=11, fontweight='bold')
        ax.set_title('Dyno Power Curves', fontsize=14, fontweight='bold',
                    color=self.branding.secondary_color)
        ax.legend(loc='upper left', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=1000)
        ax.set_ylim(bottom=0)
        
        # Add subtle background
        ax.set_facecolor('#FAFAFA')
        
        plt.tight_layout()
        
        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        img_buffer.seek(0)
        
        # Add to PDF
        img = Image(img_buffer, width=6.5*inch, height=3.7*inch)
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_ve_heatmap(self, data: ReportData) -> list:
        """Build the VE corrections heatmap."""
        elements = []
        
        elements.append(Paragraph("VE Corrections Applied", self.styles['SectionHeader']))
        
        if not data.ve_grid:
            elements.append(Paragraph("No VE correction data available.", self.styles['Normal']))
            return elements
        
        # Convert grid to numpy array
        grid_data = []
        rpm_labels = []
        for row in data.ve_grid:
            rpm_labels.append(str(row['rpm']))
            grid_data.append(row['values'])
        
        grid_array = np.array(grid_data)
        map_labels = [str(m) for m in self.MAP_BINS[:grid_array.shape[1]]]
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
        
        # Custom colormap: blue (lean/negative) -> white (zero) -> red (rich/positive)
        cmap = plt.cm.RdBu_r
        vmax = max(abs(grid_array.min()), abs(grid_array.max()), 5)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
        
        im = ax.imshow(grid_array, cmap=cmap, norm=norm, aspect='auto')
        
        # Labels
        ax.set_xticks(np.arange(len(map_labels)))
        ax.set_yticks(np.arange(len(rpm_labels)))
        ax.set_xticklabels(map_labels)
        ax.set_yticklabels(rpm_labels)
        ax.set_xlabel('MAP (kPa)', fontsize=11, fontweight='bold')
        ax.set_ylabel('RPM', fontsize=11, fontweight='bold')
        ax.set_title('VE Correction % by Zone', fontsize=14, fontweight='bold',
                    color=self.branding.secondary_color)
        
        # Add text annotations for significant corrections
        for i in range(len(rpm_labels)):
            for j in range(len(map_labels)):
                val = grid_array[i, j]
                if abs(val) > 0.5:  # Only annotate significant corrections
                    color = 'white' if abs(val) > vmax * 0.6 else 'black'
                    ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                           color=color, fontsize=7, fontweight='bold')
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('VE Correction %', fontsize=10)
        
        plt.tight_layout()
        
        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        img_buffer.seek(0)
        
        img = Image(img_buffer, width=6.5*inch, height=3.7*inch)
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Spacer(1, 10))
        
        # Legend explanation
        elements.append(Paragraph(
            "<i>Blue zones indicate lean corrections (add fuel), "
            "Red zones indicate rich corrections (reduce fuel)</i>",
            ParagraphStyle('HeatmapLegend', parent=self.styles['Normal'],
                          fontSize=9, textColor=colors.gray, alignment=TA_CENTER)
        ))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_afr_heatmap(self, data: ReportData) -> list:
        """Build the AFR error analysis heatmap."""
        elements = []
        
        elements.append(Paragraph("AFR Analysis", self.styles['SectionHeader']))
        
        if not data.afr_grid:
            elements.append(Paragraph("No AFR analysis data available.", self.styles['Normal']))
            return elements
        
        # Convert grid to numpy array
        grid_data = []
        rpm_labels = []
        for row in data.afr_grid:
            rpm_labels.append(str(row['rpm']))
            grid_data.append(row['values'])
        
        grid_array = np.array(grid_data)
        map_labels = [str(m) for m in self.MAP_BINS[:grid_array.shape[1]]]
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
        
        # Custom colormap for AFR error
        cmap = plt.cm.RdYlGn_r  # Red (lean) -> Yellow (ok) -> Green (slightly rich is OK)
        vmax = max(abs(grid_array.min()), abs(grid_array.max()), 2)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
        
        im = ax.imshow(grid_array, cmap=cmap, norm=norm, aspect='auto')
        
        # Labels
        ax.set_xticks(np.arange(len(map_labels)))
        ax.set_yticks(np.arange(len(rpm_labels)))
        ax.set_xticklabels(map_labels)
        ax.set_yticklabels(rpm_labels)
        ax.set_xlabel('MAP (kPa)', fontsize=11, fontweight='bold')
        ax.set_ylabel('RPM', fontsize=11, fontweight='bold')
        ax.set_title('AFR Error by Zone (Measured - Target)', fontsize=14, fontweight='bold',
                    color=self.branding.secondary_color)
        
        # Add text annotations
        for i in range(len(rpm_labels)):
            for j in range(len(map_labels)):
                val = grid_array[i, j]
                if abs(val) > 0.3:
                    color = 'white' if abs(val) > vmax * 0.6 else 'black'
                    ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                           color=color, fontsize=7, fontweight='bold')
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('AFR Error', fontsize=10)
        
        plt.tight_layout()
        
        # Save to buffer
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        img_buffer.seek(0)
        
        img = Image(img_buffer, width=6.5*inch, height=3.7*inch)
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Spacer(1, 10))
        
        # Legend explanation
        elements.append(Paragraph(
            "<i>Positive values (red) indicate lean condition, "
            "Negative values (green) indicate rich condition</i>",
            ParagraphStyle('HeatmapLegend', parent=self.styles['Normal'],
                          fontSize=9, textColor=colors.gray, alignment=TA_CENTER)
        ))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_notes_section(self, data: ReportData) -> list:
        """Build the tuner notes section."""
        elements = []
        
        elements.append(Paragraph("Tuner Notes & Recommendations", self.styles['SectionHeader']))
        
        # Notes in a bordered box
        notes_style = ParagraphStyle(
            'Notes',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            spaceBefore=5,
            spaceAfter=5
        )
        
        notes_table = Table(
            [[Paragraph(data.tuner_notes.replace('\n', '<br/>'), notes_style)]],
            colWidths=[6.5*inch]
        )
        notes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(self.branding.primary_color)),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        elements.append(notes_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_confidence_section(self, data: ReportData) -> list:
        """Build the confidence score section."""
        elements = []
        
        elements.append(Paragraph("Tune Confidence Score", self.styles['SectionHeader']))
        
        # Confidence badge
        score = data.confidence_score
        if score >= 90:
            badge_color = '#10B981'  # Emerald
            badge_text = 'Excellent'
        elif score >= 75:
            badge_color = '#3B82F6'  # Blue
            badge_text = 'Good'
        elif score >= 60:
            badge_color = '#F59E0B'  # Amber
            badge_text = 'Fair'
        else:
            badge_color = '#EF4444'  # Red
            badge_text = 'Needs Work'
        
        score_style = ParagraphStyle(
            'ConfidenceScore',
            parent=self.styles['Normal'],
            fontSize=36,
            alignment=TA_CENTER,
            textColor=colors.HexColor(badge_color),
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph(f"{score:.0f}%", score_style))
        elements.append(Paragraph(
            f"<b>{badge_text}</b>",
            ParagraphStyle('Badge', parent=self.styles['Normal'],
                          alignment=TA_CENTER, fontSize=14,
                          textColor=colors.HexColor(badge_color))
        ))
        elements.append(Spacer(1, 10))
        
        # Breakdown if available
        if data.confidence_breakdown:
            breakdown_data = []
            for category, value in data.confidence_breakdown.items():
                category_name = category.replace('_', ' ').title()
                breakdown_data.append([category_name, f"{value:.0f}%"])
            
            breakdown_table = Table(breakdown_data, colWidths=[3*inch, 1.5*inch])
            breakdown_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.gray),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            elements.append(breakdown_table)
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_footer(self, data: ReportData) -> list:
        """Build the report footer."""
        elements = []
        
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#E5E7EB'),
            spaceBefore=20,
            spaceAfter=10
        ))
        
        # Contact info
        contact_parts = []
        if self.branding.phone:
            contact_parts.append(f"📞 {self.branding.phone}")
        if self.branding.email:
            contact_parts.append(f"✉️ {self.branding.email}")
        if self.branding.website:
            contact_parts.append(f"🌐 {self.branding.website}")
        
        if contact_parts:
            elements.append(Paragraph(
                " | ".join(contact_parts),
                self.styles['Footer']
            ))
        
        if self.branding.address:
            elements.append(Paragraph(self.branding.address, self.styles['Footer']))
        
        # Generated by
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            f"Generated by DynoAI Professional | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['Footer']
        ))
        
        return elements


def generate_report_from_run(
    run_id: str,
    runs_dir: str = "runs",
    customer_name: str = "Valued Customer",
    vehicle_info: str = "",
    tuner_notes: str = "",
    baseline_run_id: Optional[str] = None,
    output_path: Optional[str] = None,
    branding: Optional[ShopBranding] = None
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
        tuner_notes=tuner_notes
    )
    
    # Generate report
    generator = DynoReportGenerator(branding)
    return generator.generate_report(report_data, output_path)
