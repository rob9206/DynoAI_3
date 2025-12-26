"""
Database models for DynoAI analysis runs.

Models:
- Run: Analysis run record with status, results, metadata
- RunFile: Output files associated with runs
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Run(Base):
    """
    Analysis run record.

    Stores metadata, status, and results for each analysis run.
    Replaces JSON file storage for better querying and concurrent access.
    """

    __tablename__ = "runs"

    # Primary key
    id = Column(
        String(64),
        primary_key=True,
        comment="Run ID (e.g., run_20251225_120000_abc123)",
    )

    # Status and source
    status = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Run status: pending, processing, complete, error",
    )
    source = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Data source: upload, jetstream, simulator",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Jetstream integration
    jetstream_id = Column(
        String(64), index=True, nullable=True, comment="Jetstream run ID"
    )
    jetstream_status = Column(String(20), nullable=True)

    # Progress tracking
    current_stage = Column(String(50), comment="Current processing stage")
    progress_percent = Column(Integer, default=0, comment="Progress percentage (0-100)")
    progress_message = Column(Text, comment="Human-readable progress message")

    # Results summary (JSON)
    results_summary = Column(
        JSON,
        nullable=True,
        comment="Analysis results: HP, torque, AFR stats, etc.",
    )

    # Error tracking
    error_info = Column(JSON, nullable=True, comment="Error details if status=error")
    error_message = Column(Text, nullable=True)

    # Input metadata
    input_filename = Column(String(255), comment="Original uploaded filename")
    input_size_bytes = Column(Integer, comment="File size in bytes")
    input_rows = Column(Integer, comment="Number of data rows")

    # Analysis configuration
    config_snapshot = Column(
        JSON,
        nullable=True,
        comment="Configuration used for this run",
    )

    # Performance metrics
    peak_hp = Column(Float, nullable=True, comment="Peak horsepower")
    peak_torque = Column(Float, nullable=True, comment="Peak torque")
    afr_mean = Column(Float, nullable=True, comment="Mean AFR")
    afr_std = Column(Float, nullable=True, comment="AFR standard deviation")

    # VE corrections
    ve_corrections_count = Column(
        Integer, nullable=True, comment="Number of VE corrections suggested"
    )
    ve_max_correction_pct = Column(
        Float, nullable=True, comment="Maximum correction magnitude (%)"
    )

    # Relationships
    files = relationship("RunFile", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Run(id='{self.id}', status='{self.status}', source='{self.source}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "jetstream_id": self.jetstream_id,
            "current_stage": self.current_stage,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "results_summary": self.results_summary,
            "error_message": self.error_message,
            "input_filename": self.input_filename,
            "peak_hp": self.peak_hp,
            "peak_torque": self.peak_torque,
            "afr_mean": self.afr_mean,
            "ve_corrections_count": self.ve_corrections_count,
        }


class RunFile(Base):
    """
    Output file from an analysis run.

    Tracks files generated during analysis (CSV exports, reports, plots, etc.)
    """

    __tablename__ = "run_files"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to run
    run_id = Column(
        String(64),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File metadata
    filename = Column(
        String(255), nullable=False, comment="Filename (e.g., corrections.csv)"
    )
    file_type = Column(String(50), comment="File type: csv, json, txt, png, pdf")
    size_bytes = Column(Integer, comment="File size in bytes")

    # Storage
    storage_path = Column(Text, comment="Local file path or cloud storage key")
    storage_type = Column(
        String(20), default="local", comment="Storage backend: local, s3, gcs"
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    run = relationship("Run", back_populates="files")

    def __repr__(self):
        return f"<RunFile(id={self.id}, run_id='{self.run_id}', filename='{self.filename}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "storage_type": self.storage_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
