from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExternalDynoChart(Base):
    """
    External dyno chart metadata used only as reference for synthetic generation.
    """

    __tablename__ = "external_dyno_charts"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    engine_family: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    displacement_ci: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cam_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exhaust_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    max_power_hp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_power_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_torque_ftlb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_torque_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    synthetic_runs: Mapped[List["SyntheticWinpepRun"]] = relationship(
        "SyntheticWinpepRun", back_populates="chart", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "source": self.source,
            "category": self.category,
            "title": self.title,
            "page_url": self.page_url,
            "image_url": self.image_url,
            "image_file": self.image_file,
            "engine_family": self.engine_family,
            "displacement_ci": self.displacement_ci,
            "cam_info": self.cam_info,
            "exhaust_info": self.exhaust_info,
            "max_power_hp": self.max_power_hp,
            "max_power_rpm": self.max_power_rpm,
            "max_torque_ftlb": self.max_torque_ftlb,
            "max_torque_rpm": self.max_torque_rpm,
        }


class SyntheticWinpepRun(Base):
    """
    Synthetic WinPEP CSV metadata keyed to an external dyno chart.
    """

    __tablename__ = "synthetic_winpep_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chart_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("external_dyno_charts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_path: Mapped[str] = mapped_column(Text, nullable=False)
    hp_peak_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_hp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tq_peak_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tq: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    engine_family: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    displacement_ci: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    chart: Mapped[ExternalDynoChart] = relationship(
        "ExternalDynoChart", back_populates="synthetic_runs"
    )
