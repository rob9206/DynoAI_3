"""Initial run tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-12-05

Creates the initial database schema for DynoAI run tracking:
- runs: Main table for analysis run records
- run_files: Output files associated with runs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables for run tracking."""
    # Create runs table
    op.create_table(
        "runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("source", sa.String(20), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("jetstream_id", sa.String(64), nullable=True, index=True),
        sa.Column("current_stage", sa.String(50), nullable=True),
        sa.Column("progress_percent", sa.Integer(), default=0),
        sa.Column("results_summary", sa.JSON(), nullable=True),
        sa.Column("error_info", sa.JSON(), nullable=True),
        sa.Column("input_filename", sa.String(255), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
    )

    # Create composite indexes for common queries
    op.create_index(
        "ix_runs_status_created", "runs", ["status", "created_at"], unique=False
    )
    op.create_index(
        "ix_runs_source_created", "runs", ["source", "created_at"], unique=False
    )

    # Create run_files table
    op.create_table(
        "run_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create composite index for run+filename lookups
    op.create_index(
        "ix_run_files_run_filename", "run_files", ["run_id", "filename"], unique=False
    )


def downgrade() -> None:
    """Drop run tracking tables."""
    op.drop_index("ix_run_files_run_filename", table_name="run_files")
    op.drop_table("run_files")

    op.drop_index("ix_runs_source_created", table_name="runs")
    op.drop_index("ix_runs_status_created", table_name="runs")
    op.drop_table("runs")




