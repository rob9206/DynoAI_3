"""
PTI file parser for Engine Analyzer Pro component files.

Provides best-effort parsing across legacy PTI formats with robust error handling.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api.errors import ValidationError
from api.services.engine_analyzer.schemas import (
    CamSpec,
    CompleteEngineSpec,
    HeadFlowPoint,
    HeadSpec,
    IntakeSpec,
    ShortBlockSpec,
)

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {
    ".C1",
    ".S96",
    ".CMP",
    ".TXT",
    ".NEW",
    ".MDL",
    ".HEV",
    ".EV",
}


@dataclass
class PTIParseResult:
    component_type: str
    spec: (
        HeadSpec
        | CamSpec
        | IntakeSpec
        | ShortBlockSpec
        | CompleteEngineSpec
    )
    header: str | None = None
    source_path: Path | None = None


def parse_pti_file(path: Path) -> PTIParseResult:
    if not path.exists():
        raise ValidationError(f"PTI file not found: {path}")

    lines = _read_text_lines(path)
    header = _find_header(lines)
    
    # Only parse files with valid PTI headers, and exclude config files
    if header is None:
        raise ValidationError(f"Not a valid PTI file (no EAPRO-PTI header): {path}")
    if "-CFG" in header.upper():
        raise ValidationError(f"Skipping configuration file: {path}")
    
    component_type = _infer_component_type(path, header, lines)
    # FIX: Extract name from line immediately after header (line 2), not all comment text
    name = _extract_component_name(lines)
    comment = _extract_comment(lines)
    numbers = _extract_numbers(lines)

    if component_type == "head":
        spec = _parse_head(path, name, comment, numbers)
    elif component_type == "cam":
        spec = _parse_cam(path, name, comment, numbers)
    elif component_type == "intake":
        spec = _parse_intake(path, name, comment, numbers)
    elif component_type == "short_block":
        spec = _parse_short_block(path, name, comment, numbers)
    else:
        component_refs = _extract_component_refs(lines)
        spec = _parse_engine(path, name, comment, numbers, component_refs)
        component_type = "engine"

    return PTIParseResult(
        component_type=component_type,
        spec=spec,
        header=header,
        source_path=path,
    )


def _read_text_lines(path: Path) -> list[str]:
    encodings = ["utf-8", "latin-1", "cp1252"]
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding, errors="ignore") as file:
                return file.read().splitlines()
        except Exception as exc:  # pragma: no cover - best effort
            last_error = exc
            continue
    raise ValidationError(f"Unable to read PTI file: {path} ({last_error})")


def _find_header(lines: Iterable[str]) -> str | None:
    for line in lines:
        value = line.strip()
        if value.startswith("EAPRO-PTI"):
            return value
    return None


def _infer_component_type(
    path: Path, header: str | None, lines: list[str]
) -> str:
    header_value = (header or "").upper()
    if "-CY" in header_value:
        return "head"
    if "-CA" in header_value:
        return "cam"
    if "-EN" in header_value:
        return "engine"
    if "-IN" in header_value:
        return "intake"

    path_hint = str(path).lower()
    if "head file" in path_hint or "headfiles" in path_hint:
        return "head"
    if "cam" in path_hint:
        return "cam"
    if "intake" in path_hint:
        return "intake"
    if "short block" in path_hint or "shortblock" in path_hint:
        return "short_block"
    if "engine" in path_hint:
        return "engine"

    ext = path.suffix.lower()
    if ext in {".c1", ".s96"}:
        return "cam"
    if ext in {".ev", ".hev"}:
        return "engine"
    return "head"


def _extract_component_name(lines: list[str]) -> str | None:
    """Extract the component name from line 2 (immediately after the EAPRO-PTI header).
    
    In valid PTI files, the structure is:
    Line 1: EAPRO-PTI-En3.50 (header)
    Line 2: 2013 Ford Shelby (component name)
    """
    found_header = False
    for line in lines:
        value = line.strip()
        if value.startswith("EAPRO-PTI"):
            found_header = True
            continue
        if found_header and value and not _is_numeric(value):
            return value
    return None


def _extract_comment(lines: Iterable[str]) -> str | None:
    comment_lines: list[str] = []
    # Convert to list so we can iterate multiple times
    lines_list = list(lines) if not isinstance(lines, list) else lines
    for line in lines_list:
        value = line.strip()
        if value == "-9999":
            break
        if not value:
            continue
        if _is_numeric(value):
            continue
        if value.startswith("EAPRO-PTI"):
            continue
        comment_lines.append(value)
    if not comment_lines:
        return None
    return " ".join(comment_lines).strip()


def _extract_numbers(lines: Iterable[str]) -> list[float]:
    numbers: list[float] = []
    for line in lines:
        value = line.strip()
        if value == "-9999":
            break
        if not value:
            continue
        for token in re.split(r"\s+", value):
            if not token or token == "-9999":
                continue
            if _is_numeric(token):
                try:
                    numbers.append(float(token))
                except ValueError:
                    continue
    return numbers


def _extract_component_refs(lines: Iterable[str]) -> list[str]:
    refs: list[str] = []
    for line in lines:
        value = line.strip()
        if value == "-9999":
            break
        if not value:
            continue
        if _is_numeric(value):
            continue
        if value.startswith("EAPRO-PTI"):
            continue
        refs.append(value)
    return refs


def _parse_head(
    path: Path, name: str | None, comment: str | None, numbers: list[float]
) -> HeadSpec:
    flow_sequences = _extract_flow_sequences(numbers)
    intake_flow = [
        HeadFlowPoint(lift_inches=lift, cfm=cfm)
        for lift, cfm in flow_sequences[0]
    ] if flow_sequences else []
    exhaust_flow = [
        HeadFlowPoint(lift_inches=lift, cfm=cfm)
        for lift, cfm in flow_sequences[1]
    ] if len(flow_sequences) > 1 else []

    valve_candidates = [n for n in numbers if 1.0 <= n <= 2.5]
    port_candidates = [n for n in numbers if 50 <= n <= 400]
    chamber_candidates = [n for n in numbers if 40 <= n <= 120]

    return HeadSpec(
        name=name or path.stem,
        intake_valve_dia=valve_candidates[0] if valve_candidates else None,
        exhaust_valve_dia=valve_candidates[1]
        if len(valve_candidates) > 1
        else None,
        intake_port_cc=port_candidates[0] if port_candidates else None,
        exhaust_port_cc=port_candidates[1]
        if len(port_candidates) > 1
        else None,
        chamber_cc=chamber_candidates[0] if chamber_candidates else None,
        intake_flow=intake_flow,
        exhaust_flow=exhaust_flow,
        notes=comment,
        raw_numbers=numbers,
    )


def _parse_cam(
    path: Path, name: str | None, comment: str | None, numbers: list[float]
) -> CamSpec:
    duration_candidates = [n for n in numbers if 140 <= n <= 320]
    lift_candidates = [n for n in numbers if 0.1 <= n <= 1.0]
    lsa_candidates = [n for n in numbers if 90 <= n <= 130]
    rocker_candidates = [n for n in numbers if 1.2 <= n <= 2.1]

    return CamSpec(
        name=name or path.stem,
        intake_duration_050=duration_candidates[0]
        if duration_candidates
        else None,
        exhaust_duration_050=duration_candidates[1]
        if len(duration_candidates) > 1
        else None,
        intake_lift=lift_candidates[0] if lift_candidates else None,
        exhaust_lift=lift_candidates[1] if len(lift_candidates) > 1 else None,
        lobe_separation=lsa_candidates[0] if lsa_candidates else None,
        advance=None,
        rocker_ratio_int=rocker_candidates[0] if rocker_candidates else None,
        rocker_ratio_exh=rocker_candidates[1]
        if len(rocker_candidates) > 1
        else None,
        notes=comment,
        raw_numbers=numbers,
    )


def _parse_intake(
    path: Path, name: str | None, comment: str | None, numbers: list[float]
) -> IntakeSpec:
    length_candidates = [n for n in numbers if 4 <= n <= 20]
    dia_candidates = [n for n in numbers if 1.0 <= n <= 6.0]

    return IntakeSpec(
        name=name or path.stem,
        runner_length_in=length_candidates[0] if length_candidates else None,
        runner_dia_in=dia_candidates[0] if dia_candidates else None,
        throttle_body_dia_in=dia_candidates[1] if len(dia_candidates) > 1 else None,
        notes=comment,
        raw_numbers=numbers,
    )


def _parse_short_block(
    path: Path, name: str | None, comment: str | None, numbers: list[float]
) -> ShortBlockSpec:
    bore_candidates = [n for n in numbers if 3.0 <= n <= 6.0]
    stroke_candidates = [n for n in numbers if 2.5 <= n <= 6.0]
    rod_candidates = [n for n in numbers if 4.5 <= n <= 7.5]
    comp_candidates = [n for n in numbers if 6.0 <= n <= 15.0]
    cyl_candidates = [n for n in numbers if float(int(n)) == n and 2 <= n <= 16]

    return ShortBlockSpec(
        name=name or path.stem,
        bore=bore_candidates[0] if bore_candidates else None,
        stroke=stroke_candidates[1]
        if len(stroke_candidates) > 1
        else (stroke_candidates[0] if stroke_candidates else None),
        rod_length=rod_candidates[0] if rod_candidates else None,
        cylinders=int(cyl_candidates[0]) if cyl_candidates else None,
        compression_ratio=comp_candidates[0] if comp_candidates else None,
        notes=comment,
        raw_numbers=numbers,
    )


def _parse_engine(
    path: Path,
    name: str | None,
    comment: str | None,
    numbers: list[float],
    component_refs: list[str],
) -> CompleteEngineSpec:
    # Calculate displacement from bore and stroke if available
    displacement_ci = None
    displacement_cc = None
    engine_name = name or path.stem
    summary = engine_name
    
    # Look for displacement-related numbers in the data
    if len(numbers) >= 2:
        bore_candidates = [n for n in numbers if 3.0 <= n <= 6.0]  # Typical bore range
        stroke_candidates = [n for n in numbers if 2.5 <= n <= 6.0]  # Typical stroke range
        cyl_candidates = [n for n in numbers if float(int(n)) == n and 2 <= n <= 16]
        
        if bore_candidates and stroke_candidates:
            bore = bore_candidates[0]
            stroke = stroke_candidates[0]
            # Use detected cylinders or default to 8 (common V8)
            cylinders = int(cyl_candidates[0]) if cyl_candidates else 8
            
            # Calculate displacement in cubic inches
            displacement_ci = (bore ** 2) * stroke * 0.7854 * cylinders
            # Convert to cubic centimeters
            displacement_cc = displacement_ci * 16.387
            
            summary = f"{displacement_ci:.0f}ci V{cylinders} {bore:.2f} x {stroke:.2f}"
    
    return CompleteEngineSpec(
        name=engine_name,
        component_refs=component_refs,
        notes=comment,
        raw_numbers=numbers,
        displacement_ci=displacement_ci if displacement_ci else 350.0,  # Default value
        displacement_cc=displacement_cc if displacement_cc else 5730.0,  # Default value
        summary=summary,
    )


def _extract_flow_sequences(numbers: list[float]) -> list[list[tuple[float, float]]]:
    sequences: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    last_lift: float | None = None

    for idx in range(len(numbers) - 1):
        lift = numbers[idx]
        cfm = numbers[idx + 1]
        if _looks_like_flow_pair(lift, cfm):
            if last_lift is None or lift >= last_lift - 0.01:
                current.append((lift, cfm))
            else:
                if len(current) >= 4:
                    sequences.append(current)
                current = [(lift, cfm)]
            last_lift = lift
        else:
            if len(current) >= 4:
                sequences.append(current)
            current = []
            last_lift = None

    if len(current) >= 4:
        sequences.append(current)

    sequences.sort(key=len, reverse=True)
    return sequences[:2]


def _looks_like_flow_pair(lift: float, cfm: float) -> bool:
    return 0.05 <= lift <= 1.2 and 10 <= cfm <= 600


def _is_numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", value))
