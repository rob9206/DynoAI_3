from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from api.models.external_dyno import ExternalDynoChart, SyntheticWinpepRun, utc_now
from api.services.database import get_db
from external_scrapers.dyno_models import DynoChartMeta, meta_from_row
from dynoai.core.io_contracts import safe_path
from synthetic.winpep8_synthesizer import (
    EngineFamily,
    PeakInfo as SynthPeakInfo,
    generate_winpep8_like_run,
    save_winpep8_run,
)

# NOTE: external chart data is used only as reference for synthetic curve
# generation. Do not rehost or redistribute original assets directly.


def _load_meta(index_csv_path: str) -> List[DynoChartMeta]:
    safe_path_obj = safe_path(index_csv_path)
    with safe_path_obj.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [meta_from_row(row) for row in reader]


def _upsert_chart(meta: DynoChartMeta) -> None:
    with get_db() as db:
        chart = ExternalDynoChart(
            id=meta.id,
            source=meta.source,
            category=meta.category,
            title=meta.title,
            page_url=meta.page_url,
            image_url=meta.image_url,
            image_file=meta.image_file,
            engine_family=meta.engine_family,
            displacement_ci=meta.displacement_ci,
            cam_info=meta.cam_info,
            exhaust_info=meta.exhaust_info,
            max_power_hp=meta.max_power_hp,
            max_power_rpm=meta.max_power_rpm,
            max_torque_ftlb=meta.max_torque_ftlb,
            max_torque_rpm=meta.max_torque_rpm,
            updated_at=utc_now(),
        )
        db.merge(chart)


def ingest_fuelmoto(index_csv_path: str) -> int:
    metas = [m for m in _load_meta(index_csv_path) if m.source == "fuelmoto"]
    for meta in metas:
        _upsert_chart(meta)
        build_synthetic_run_from_external_chart(meta)
    return len(metas)


def ingest_dynojet(index_csv_path: str) -> int:
    metas = [m for m in _load_meta(index_csv_path) if m.source == "dynojet"]
    for meta in metas:
        _upsert_chart(meta)
        build_synthetic_run_from_external_chart(meta)
    return len(metas)


def record_synthetic_run(
    chart_id: str, run_path: str, spec: Dict[str, float | str]
) -> None:
    """
    Persist metadata for a generated synthetic WinPEP CSV.
    """
    with get_db() as db:
        existing = (
            db.query(SyntheticWinpepRun)
            .filter(SyntheticWinpepRun.chart_id == chart_id)
            .one_or_none()
        )
        if existing:
            existing.run_path = run_path
            existing.hp_peak_rpm = float(spec["hp_peak_rpm"])
            existing.max_hp = float(spec["max_hp"])
            existing.tq_peak_rpm = float(spec["tq_peak_rpm"])
            existing.max_tq = float(spec["max_tq"])
            existing.engine_family = str(spec["engine_family"])
            existing.displacement_ci = float(spec["displacement_ci"])
        else:
            run = SyntheticWinpepRun(
                chart_id=chart_id,
                run_path=run_path,
                hp_peak_rpm=float(spec["hp_peak_rpm"]),
                max_hp=float(spec["max_hp"]),
                tq_peak_rpm=float(spec["tq_peak_rpm"]),
                max_tq=float(spec["max_tq"]),
                engine_family=str(spec["engine_family"]),
                displacement_ci=float(spec["displacement_ci"]),
            )
            db.add(run)


def _resolve_engine_family(raw: Optional[str]) -> EngineFamily:
    if not raw:
        return "Generic"
    lowered = raw.lower()
    if "m8" in lowered or "milwaukee" in lowered:
        return "M8"
    if "twin cam" in lowered or "twincam" in lowered:
        return "TwinCam"
    if any(label in lowered for label in ("gsx", "r1", "cbr", "zx", "sport")):
        return "Sportbike"
    return "Generic"


def build_synthetic_run_from_external_chart(meta: DynoChartMeta) -> Optional[str]:
    """
    Generate and persist a WinPEP-style synthetic run for a chart if peaks exist.
    """

    required = [
        meta.max_power_hp,
        meta.max_power_rpm,
        meta.max_torque_ftlb,
        meta.max_torque_rpm,
        meta.engine_family,
        meta.displacement_ci,
    ]
    if any(val is None for val in required):
        return None

    peaks = SynthPeakInfo(
        max_hp=float(meta.max_power_hp),
        hp_peak_rpm=float(meta.max_power_rpm),
        max_tq=float(meta.max_torque_ftlb),
        tq_peak_rpm=float(meta.max_torque_rpm),
    )
    family = _resolve_engine_family(meta.engine_family)
    run_df = generate_winpep8_like_run(
        peaks=peaks,
        family=family,
        displacement_ci=float(meta.displacement_ci),
    )
    run_id = f"{meta.source}/{meta.id}"
    run_path = save_winpep8_run(run_id, run_df)
    record_synthetic_run(
        chart_id=meta.id,
        run_path=run_path,
        spec={
            "hp_peak_rpm": peaks.hp_peak_rpm,
            "max_hp": peaks.max_hp,
            "tq_peak_rpm": peaks.tq_peak_rpm,
            "max_tq": peaks.max_tq,
            "engine_family": family,
            "displacement_ci": float(meta.displacement_ci),
        },
    )
    return run_path


__all__ = [
    "build_synthetic_run_from_external_chart",
    "ingest_fuelmoto",
    "ingest_dynojet",
    "record_synthetic_run",
]
