"""
Database models for DynoAI analysis runs.

Models:
- Run: Analysis run record with status, results, metadata, and user association
- RunFile: Output files associated with runs
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from api.models.base import Base


class Run(Base):
    """
    Analysis run record.

    Stores metadata, status, and results for each analysis run.
    Associates each run with the submitting user for history persistence.
    """

    __tablename__ = "runs"

    # Primary key (UUID)
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )

    # The run identifier string passed to the analysis pipeline
    run_id = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="Analysis run ID (UUID string)",
    )

    # User association
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="Submitting user ID (FK → users.id)",
    )

    # Status
    status = Column(
        String(20),
        nullable=False,
        default="queued",
        index=True,
        comment="Run status: queued, running, completed, error",
    )

    # Input file
    input_file = Column(String(255),
                        nullable=True,
                        comment="Uploaded filename")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Result metrics
    rows_processed = Column(Integer, nullable=True)
    corrections_applied = Column(Integer, nullable=True)
    avg_correction = Column(Float, nullable=True)
    max_correction = Column(Float, nullable=True)

    # Output files stored as JSON string
    output_files = Column(Text,
                          nullable=True,
                          comment="JSON-encoded list of output files")

    # Error info
    error_message = Column(String(500), nullable=True)

    # Relationship to user
    user = relationship("User", backref="runs")

    def __repr__(self):
        return f"<Run(id='{self.id}', run_id='{self.run_id}', status='{self.status}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        import json as _json

        return {
            "id":
            self.id,
            "run_id":
            self.run_id,
            "user_id":
            str(self.user_id) if self.user_id else None,
            "status":
            self.status,
            "input_file":
            self.input_file,
            "created_at":
            self.created_at.isoformat() if self.created_at else None,
            "completed_at":
            (self.completed_at.isoformat() if self.completed_at else None),
            "rows_processed":
            self.rows_processed,
            "corrections_applied":
            self.corrections_applied,
            "avg_correction":
            self.avg_correction,
            "max_correction":
            self.max_correction,
            "output_files":
            _json.loads(self.output_files) if self.output_files else [],
            "error_message":
            self.error_message,
        }


class RunFile(Base):
    """
    Output file from an analysis run.

    Tracks files generated during analysis (CSV exports, reports, plots, etc.)
    """

    __tablename__ = "run_files"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to run (references runs.id which is now String(36))
    run_id = Column(
        String(36),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File metadata
    filename = Column(String(255),
                      nullable=False,
                      comment="Filename (e.g., corrections.csv)")
    file_type = Column(String(50),
                       comment="File type: csv, json, txt, png, pdf")
    size_bytes = Column(Integer, comment="File size in bytes")

    # Storage
    storage_path = Column(Text, comment="Local file path or cloud storage key")
    storage_type = Column(String(20),
                          default="local",
                          comment="Storage backend: local, s3, gcs")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

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
            "created_at":
            self.created_at.isoformat() if self.created_at else None,
        }
