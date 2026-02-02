"""
Engine Analyzer API routes.

Provides endpoints for PTI parsing, component library browsing, and prediction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import unquote

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from api.errors import ValidationError, with_error_handling
from api.services.engine_analyzer.library_service import get_engine_analyzer_library
from api.services.engine_analyzer.prediction_service import predict_performance
from api.services.engine_analyzer.schemas import (
    CamSpec,
    CompleteEngineSpec,
    HeadFlowPoint,
    HeadSpec,
    IntakeSpec,
    ShortBlockSpec,
)
from api.services.parsers.pti_parser import parse_pti_file

logger = logging.getLogger(__name__)

engine_analyzer_bp = Blueprint("engine_analyzer", __name__, url_prefix="/api/ea")


@engine_analyzer_bp.route("/library", methods=["GET"])
@with_error_handling
def list_library():
    """
    List components in the Engine Analyzer library.
    """
    component_type = request.args.get("type")
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    components = library.list_components(component_type, search)
    stats = library.get_stats()
    
    # Add debug info for library path
    debug_info = {
        "available": True,
        "lib_dir": str(library.lib_dir),
        "lib_exists": library.lib_dir.exists(),
        "lib_content": [str(c) for c in library.lib_dir.iterdir()][:5] if library.lib_dir.exists() else [],
        "components": components,
        "stats": stats.to_dict(),
        "skipped_files": library.get_skipped_files(),
    }
    
    return jsonify(debug_info), 200


@engine_analyzer_bp.route("/library/<component_type>/<component_name>", methods=["GET"])
@with_error_handling
def get_component(component_type: str, component_name: str):
    """
    Get a specific component by type and name.
    """
    library = get_engine_analyzer_library()
    name = unquote(component_name)
    component = library.get_component(component_type, name)
    return jsonify(component), 200


@engine_analyzer_bp.route("/parse", methods=["POST"])
@with_error_handling
def parse_pti():
    """
    Parse a PTI file uploaded via multipart/form-data.
    """
    if "file" not in request.files:
        raise ValidationError("No file provided")
    file = request.files["file"]
    if not file.filename:
        raise ValidationError("No file selected")

    filename = secure_filename(file.filename)
    temp_path = Path.cwd() / "uploads" / filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    file.save(str(temp_path))

    parsed = parse_pti_file(temp_path)
    return (
        jsonify(
            {
                "type": parsed.component_type,
                "spec": parsed.spec.to_dict(),
                "header": parsed.header,
            }
        ),
        200,
    )


@engine_analyzer_bp.route("/build", methods=["POST"])
@with_error_handling
def build_engine():
    """
    Create an engine build from component references.
    """
    data = request.get_json() or {}
    build_name = data.get("name", "EA Build")
    components = data.get("components") or {}

    library = get_engine_analyzer_library()
    short_block = _resolve_component(
        library, "short_block", components.get("short_block")
    )
    heads = _resolve_component(library, "head", components.get("heads"))
    cam = _resolve_component(library, "cam", components.get("cam"))
    intake = _resolve_component(library, "intake", components.get("intake"))

    build = CompleteEngineSpec(
        name=build_name,
        short_block=_deserialize_short_block(short_block["spec"]) if short_block else None,
        heads=_deserialize_head(heads["spec"]) if heads else None,
        cam=_deserialize_cam(cam["spec"]) if cam else None,
        intake=_deserialize_intake(intake["spec"]) if intake else None,
        component_refs=[c for c in components.values() if isinstance(c, str)],
    )

    return jsonify({"build": build.to_dict()}), 200


@engine_analyzer_bp.route("/predict", methods=["POST"])
@with_error_handling
def predict():
    """
    Predict VE and performance from component specs or engine name.
    """
    data = request.get_json() or {}
    
    # Support engine_name lookup (what frontend sends)
    engine_name = data.get("engine_name")
    build_data = data.get("build")
    
    if engine_name:
        # Lookup engine from library
        library = get_engine_analyzer_library()
        try:
            component = library.get_component("engine", engine_name)
            spec = component.get("spec", {})
            # Create a CompleteEngineSpec from the library component
            build = CompleteEngineSpec(
                name=component.get("name", engine_name),
                displacement_ci=spec.get("displacement_ci"),
                displacement_cc=spec.get("displacement_cc"),
                component_refs=spec.get("component_refs", []),
                notes=spec.get("notes"),
                raw_numbers=spec.get("raw_numbers", []),
            )
        except Exception:
            # If lookup fails, create a simple spec from the name
            build = CompleteEngineSpec(name=engine_name)
    elif build_data:
        build = _build_from_payload(build_data)
    else:
        raise ValidationError("engine_name or build payload is required")

    prediction = predict_performance(build)
    
    # Return format that frontend expects
    result = {
        "build_name": prediction.metadata.get("buildName", build.name),
        "displacement_ci": prediction.metadata.get("displacementCi") or build.displacement_ci or 350.0,
        "compression_ratio": prediction.metadata.get("compressionRatio"),
        "peak_hp": prediction.metadata.get("predictedPeakHp"),
        "peak_hp_rpm": prediction.metadata.get("predictedPeakHpRpm"),
        "peak_tq": prediction.metadata.get("predictedPeakTq"),
        "peak_tq_rpm": prediction.metadata.get("predictedPeakTqRpm"),
        "prediction_notes": [prediction.metadata.get("notes", "")],
        "confidence_level": "medium",
        # Also include full prediction data for advanced use
        "full_prediction": prediction.to_dict(),
    }
    return jsonify(result), 200


def _resolve_component(library, component_type: str, ref: str | None):
    if not ref:
        return None
    if ":" in ref:
        return library.get_component(*ref.split(":", 1))
    return library.get_component(component_type, ref)


def _build_from_payload(payload: dict) -> CompleteEngineSpec:
    return CompleteEngineSpec(
        name=payload.get("name", "EA Build"),
        short_block=_deserialize_short_block(payload.get("short_block")),
        heads=_deserialize_head(payload.get("heads")),
        cam=_deserialize_cam(payload.get("cam")),
        intake=_deserialize_intake(payload.get("intake")),
        component_refs=payload.get("component_refs", []),
        notes=payload.get("notes"),
        raw_numbers=payload.get("raw_numbers", []),
    )


def _deserialize_short_block(data: dict | None) -> ShortBlockSpec | None:
    if not data:
        return None
    return ShortBlockSpec(**data)


def _deserialize_intake(data: dict | None) -> IntakeSpec | None:
    if not data:
        return None
    return IntakeSpec(**data)


def _deserialize_cam(data: dict | None) -> CamSpec | None:
    if not data:
        return None
    return CamSpec(**data)


def _deserialize_head(data: dict | None) -> HeadSpec | None:
    if not data:
        return None
    intake_flow = [
        HeadFlowPoint(**point) for point in data.get("intake_flow", [])
    ]
    exhaust_flow = [
        HeadFlowPoint(**point) for point in data.get("exhaust_flow", [])
    ]
    data = {**data, "intake_flow": intake_flow, "exhaust_flow": exhaust_flow}
    return HeadSpec(**data)


# =============================================================================
# Component List Endpoints - These are the endpoints the frontend calls
# =============================================================================

@engine_analyzer_bp.route("/library/engines", methods=["GET"])
@with_error_handling
def list_engines():
    """List engine components."""
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    
    try:
        components = library.list_components("engine", search)
        engine_list = []
        for comp in components:
            spec = comp.get("spec", {})
            engine_list.append({
                "name": spec.get("name", comp.get("name", "Unknown")),
                "displacement_ci": spec.get("displacement_ci", 350.0),
                "displacement_cc": spec.get("displacement_cc", 5730.0),
                "summary": spec.get("summary", "Engine component")
            })
        return jsonify({"engines": engine_list}), 200
    except Exception as e:
        logger.error(f"Error listing engines: {e}")
        return jsonify({"engines": []}), 200


@engine_analyzer_bp.route("/library/heads", methods=["GET"])
@with_error_handling  
def list_heads():
    """List head components."""
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    
    try:
        components = library.list_components("head", search)
        head_list = []
        for comp in components:
            spec = comp.get("spec", {})
            head_list.append({
                "name": spec.get("name", comp.get("name", "Unknown")),
                "intake_valve_dia": spec.get("intake_valve_dia", 2.02),
                "exhaust_valve_dia": spec.get("exhaust_valve_dia", 1.60),
                "intake_port_cc": spec.get("intake_port_cc"),
                "exhaust_port_cc": spec.get("exhaust_port_cc"),
                "chamber_cc": spec.get("chamber_cc"),
                "intake_flow": spec.get("intake_flow", []),
                "exhaust_flow": spec.get("exhaust_flow", []),
                "peak_intake_cfm": max([f.get("cfm", 0) for f in spec.get("intake_flow", [])] or [0]),
                "peak_exhaust_cfm": max([f.get("cfm", 0) for f in spec.get("exhaust_flow", [])] or [0]),
                "flow_ratio": 0.7,
                "notes": spec.get("notes")
            })
        return jsonify({"heads": head_list}), 200
    except Exception as e:
        logger.error(f"Error listing heads: {e}")
        return jsonify({"heads": []}), 200


@engine_analyzer_bp.route("/library/cams", methods=["GET"])
@with_error_handling
def list_cams():
    """List cam components."""
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    
    try:
        components = library.list_components("cam", search)
        cam_list = []
        for comp in components:
            spec = comp.get("spec", {})
            cam_list.append({
                "name": spec.get("name", comp.get("name", "Unknown")),
                "intake_duration_050": spec.get("intake_duration_050", 220),
                "exhaust_duration_050": spec.get("exhaust_duration_050", 224),
                "intake_lift": spec.get("intake_lift", 0.477),
                "exhaust_lift": spec.get("exhaust_lift", 0.477),
                "lobe_separation": spec.get("lobe_separation", 112),
                "overlap": spec.get("overlap", 4.0),
                "notes": spec.get("notes")
            })
        return jsonify({"cams": cam_list}), 200
    except Exception as e:
        logger.error(f"Error listing cams: {e}")
        return jsonify({"cams": []}), 200


@engine_analyzer_bp.route("/library/intakes", methods=["GET"])
@with_error_handling
def list_intakes():
    """List intake components."""
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    
    try:
        components = library.list_components("intake", search)
        intake_list = []
        for comp in components:
            spec = comp.get("spec", {})
            intake_list.append({
                "name": spec.get("name", comp.get("name", "Unknown")),
                "runner_length_in": spec.get("runner_length_in"),
                "runner_dia_in": spec.get("runner_dia_in"),
                "throttle_body_dia_in": spec.get("throttle_body_dia_in"),
                "throttle_body_cfm": spec.get("throttle_body_cfm"),
                "notes": spec.get("notes")
            })
        return jsonify({"intakes": intake_list}), 200
    except Exception as e:
        logger.error(f"Error listing intakes: {e}")
        return jsonify({"intakes": []}), 200


@engine_analyzer_bp.route("/library/short-blocks", methods=["GET"])
@with_error_handling
def list_short_blocks():
    """List short block components."""
    search = request.args.get("search")
    library = get_engine_analyzer_library()
    
    try:
        components = library.list_components("short_block", search)
        block_list = []
        for comp in components:
            spec = comp.get("spec", {})
            bore = spec.get("bore") or 4.0
            stroke = spec.get("stroke") or 3.5
            cylinders = spec.get("cylinders") or 8
            displacement_ci = bore * bore * stroke * 0.7854 * cylinders
            displacement_cc = displacement_ci * 16.387
            block_list.append({
                "name": spec.get("name", comp.get("name", "Unknown")),
                "bore": bore,
                "stroke": stroke,
                "rod_length": spec.get("rod_length", 5.7),
                "cylinders": cylinders,
                "compression_ratio": spec.get("compression_ratio"),
                "displacement_ci": displacement_ci,
                "displacement_cc": displacement_cc,
                "notes": spec.get("notes")
            })
        return jsonify({"short_blocks": block_list}), 200
    except Exception as e:
        logger.error(f"Error listing short blocks: {e}")
        return jsonify({"short_blocks": []}), 200


@engine_analyzer_bp.route("/library/refresh", methods=["POST"])
@with_error_handling
def refresh_library():
    """Force refresh of the component library cache."""
    # Reset the global library instance to force a rescan
    import api.services.engine_analyzer.library_service as lib_service
    lib_service._library = None
    
    library = get_engine_analyzer_library()
    stats = library.get_stats()
    
    return jsonify({
        "success": True,
        "stats": stats.to_dict()
    }), 200
