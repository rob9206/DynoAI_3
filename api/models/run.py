"""
Database models for DynoAI runs.

These models provide persistent storage for run state, progress tracking,
and output file metadata.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class Run(Base):
    """
    Analysis run record.

    Stores the state and metadata for each analysis run, whether from
    Jetstream integration or manual file upload.

    Attributes:
        id: Unique run identifier (e.g., 'run_abc123')
        status: Current status (pending, processing, complete, error)
        source: Origin of the run ('jetstream' or 'manual_upload')
        created_at: When the run was created
        updated_at: When the run was last modified
        jetstream_id: External Jetstream run ID (if applicable)
        current_stage: Current processing stage name
        progress_percent: Progress percentage (0-100)
        results_summary: JSON summary of analysis results
        error_info: JSON error details if status is 'error'
        input_filename: Original uploaded filename
        config_snapshot: JSON snapshot of config at run time
    """

    __tablename__ = "runs"

    # Primary identifier
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Jetstream integration
    jetstream_id: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )

    # Progress tracking
    current_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)

    # Results and errors (stored as JSON)
    results_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        SQLiteJSON, nullable=True
    )
    error_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        SQLiteJSON, nullable=True
    )

    # Metadata
    input_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        SQLiteJSON, nullable=True
    )

    # Relationships
    files: Mapped[List["RunFile"]] = relationship(
        "RunFile", back_populates="run", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_runs_status_created", "status", "created_at"),
        Index("ix_runs_source_created", "source", "created_at"),
    )

    def to_dict(self, include_files: bool = True) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Args:
            include_files: Whether to include file list

        Returns:
            Dictionary representation of the run
        """
        result = {
            "run_id": self.id,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "jetstream_id": self.jetstream_id,
            "current_stage": self.current_stage,
            "progress_percent": self.progress_percent,
            "input_filename": self.input_filename,
        }

        if self.results_summary:
            result["results_summary"] = self.results_summary

        if self.error_info:
            result["error"] = self.error_info

        if include_files:
            result["files"] = [f.filename for f in self.files]

        return result

    def __repr__(self) -> str:
        return f"<Run(id={self.id!r}, status={self.status!r}, source={self.source!r})>"


class RunFile(Base):
    """
    Output file from a run.

    Tracks metadata about files produced during analysis.

    Attributes:
        id: Auto-incrementing primary key
        run_id: Foreign key to parent run
        filename: Name of the file
        file_type: Type/extension (csv, json, txt)
        size_bytes: File size in bytes
        storage_path: Local filesystem path or cloud storage key
        created_at: When the file was created
    """

    __tablename__ = "run_files"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to run
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationship back to run
    run: Mapped["Run"] = relationship("Run", back_populates="files")

    # Index for efficient lookups
    __table_args__ = (Index("ix_run_files_run_filename", "run_id", "filename"),)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<RunFile(id={self.id}, run_id={self.run_id!r}, filename={self.filename!r})>"
