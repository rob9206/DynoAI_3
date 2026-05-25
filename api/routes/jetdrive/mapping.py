"""
JetDrive Auto-Tune – Channel Mapping, Preflight, Queue & Realtime Analysis Routes.

Sub-blueprint for:
- /preflight/*
- /mapping/*
- /queue/*
- /realtime/*
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from ._shared import logger

mapping_bp = Blueprint("jetdrive_mapping", __name__)


# ---------------------------------------------------------------------------
# Preflight Validation
# ---------------------------------------------------------------------------


@mapping_bp.route("/preflight/run", methods=["POST"])
def run_preflight_check():
    """Run preflight validation before starting a dyno session."""
    from api.services.jetdrive.jetdrive_preflight import run_preflight

    provider_id_param = request.args.get("provider_id")
    requested_provider_id = None
    if provider_id_param:
        try:
            if provider_id_param.lower().startswith("0x"):
                requested_provider_id = int(provider_id_param, 16)
            else:
                requested_provider_id = int(provider_id_param)
        except ValueError:
            return (
                jsonify(
                    {
                        "passed": False,
                        "error": f"Invalid provider_id format: {provider_id_param}",
                    }
                ),
                400,
            )

    mode = request.args.get("mode", "blocking")
    if mode not in ("blocking", "advisory"):
        return (
            jsonify(
                {
                    "passed": False,
                    "error": f"Invalid mode: {mode}. Must be 'blocking' or 'advisory'",
                }
            ),
            400,
        )

    try:
        sample_seconds = int(request.args.get("sample_seconds", 15))
        if sample_seconds < 5:
            sample_seconds = 5
        elif sample_seconds > 60:
            sample_seconds = 60
    except ValueError:
        sample_seconds = 15

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                run_preflight(
                    provider_id=requested_provider_id,
                    sample_seconds=sample_seconds,
                    mode=mode,
                )
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"Preflight check failed: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "passed": False,
                    "error": str(e),
                    "checks": [],
                    "missing_channels": [],
                    "suspected_mislabels": [],
                    "can_override": mode == "advisory",
                    "mode": mode,
                }
            ),
            500,
        )


@mapping_bp.route("/preflight/status", methods=["GET"])
def get_preflight_status():
    """Get the current preflight status without running checks."""
    from api.services.jetdrive.jetdrive_client import (
        JetDriveConfig,
        discover_providers,
    )

    config = JetDriveConfig.from_env()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(discover_providers(config, timeout=5.0))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not providers:
            return jsonify(
                {
                    "connected": False,
                    "providers": [],
                    "message": "No JetDrive providers found",
                }
            )

        provider_list: list[dict[str, Any]] = []
        for p in providers:
            provider_list.append(
                {
                    "provider_id": p.provider_id,
                    "provider_id_hex": f"0x{p.provider_id:04X}",
                    "name": p.name,
                    "host": p.host,
                    "channel_count": len(p.channels),
                    "channels": [
                        {"id": c.chan_id, "name": c.name} for c in p.channels.values()
                    ],
                }
            )

        return jsonify(
            {
                "connected": True,
                "providers": provider_list,
                "message": f"Found {len(providers)} provider(s)",
            }
        )

    except Exception as e:
        logger.error(f"Preflight status check failed: {e}", exc_info=True)
        return (
            jsonify({"connected": False, "providers": [], "error": str(e)}),
            500,
        )


# ---------------------------------------------------------------------------
# Channel Mapping
# ---------------------------------------------------------------------------


@mapping_bp.route("/mapping/<signature>", methods=["GET"])
def get_channel_mapping(signature: str):
    """Get the channel mapping for a provider signature."""
    from api.services.jetdrive.jetdrive_mapping import get_mapping

    mapping = get_mapping(signature)
    if mapping is None:
        return (
            jsonify({"error": "Mapping not found", "signature": signature}),
            404,
        )

    return jsonify(mapping.to_dict())


@mapping_bp.route("/mapping/<signature>", methods=["PUT"])
def save_channel_mapping(signature: str):
    """Save or update a channel mapping for a provider.

    Saving clears any in-memory transient proposal for the same signature
    so the unified status endpoint stops surfacing the "unsaved
    auto-detected mapping" banner once the operator persists.
    """
    from api.services.jetdrive.jetdrive_mapping import ProviderMapping, save_mapping
    from api.services.jetdrive.mapping_transient_cache import (
        clear_transient_mapping,
    )

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        data["provider_signature"] = signature
        mapping = ProviderMapping.from_dict(data)
        if save_mapping(mapping):
            clear_transient_mapping(signature)
            return jsonify(mapping.to_dict())
        else:
            return jsonify({"error": "Failed to save mapping"}), 500

    except Exception as e:
        logger.error(f"Failed to save mapping: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@mapping_bp.route("/mapping/<signature>", methods=["DELETE"])
def delete_channel_mapping(signature: str):
    """Delete a channel mapping."""
    from api.services.jetdrive.jetdrive_mapping import delete_mapping

    if delete_mapping(signature):
        return jsonify({"status": "deleted", "signature": signature})
    else:
        return jsonify({"error": "Failed to delete mapping"}), 500


@mapping_bp.route("/mapping", methods=["GET"])
def list_channel_mappings():
    """List all saved channel mappings."""
    from api.services.jetdrive.jetdrive_mapping import list_mappings

    mappings = list_mappings()
    return jsonify(
        {"mappings": [m.to_dict() for m in mappings], "count": len(mappings)}
    )


@mapping_bp.route("/mapping/templates", methods=["GET"])
def get_mapping_templates():
    """Get list of available mapping templates."""
    from api.services.jetdrive.jetdrive_mapping import get_templates

    templates = get_templates()
    return jsonify({"templates": templates, "count": len(templates)})


@mapping_bp.route("/mapping/templates/<template_id>", methods=["GET"])
def get_mapping_template(template_id: str):
    """Get a specific mapping template by ID."""
    from api.services.jetdrive.jetdrive_mapping import get_template

    template = get_template(template_id)
    if template is None:
        return jsonify({"error": "Template not found", "template_id": template_id}), 404

    return jsonify(template)


@mapping_bp.route("/mapping/from-template", methods=["POST"])
def create_mapping_from_template_endpoint():
    """Create a new mapping from a template."""
    from api.services.jetdrive.jetdrive_client import JetDriveConfig, discover_providers
    from api.services.jetdrive.jetdrive_mapping import (
        compute_provider_signature,
        create_mapping_from_template,
    )

    try:
        data = request.get_json() or {}
        template_id = data.get("template_id")
        requested_provider_id = data.get("provider_id")

        if not template_id:
            return jsonify({"error": "template_id is required"}), 400

        config = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(discover_providers(config, timeout=5.0))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not providers:
            return jsonify({"error": "No JetDrive providers found"}), 404

        provider = None
        if requested_provider_id:
            for p in providers:
                if p.provider_id == requested_provider_id:
                    provider = p
                    break
            if provider is None:
                return (
                    jsonify(
                        {
                            "error": f"Provider {requested_provider_id} not found",
                            "available": [p.provider_id for p in providers],
                        }
                    ),
                    404,
                )
        else:
            provider = providers[0]

        signature = compute_provider_signature(provider)
        mapping = create_mapping_from_template(template_id, provider, signature)

        if mapping is None:
            return jsonify({"error": f"Template '{template_id}' not found"}), 404

        return jsonify(
            {
                "mapping": mapping.to_dict(),
                "provider_channels": [
                    {"id": c.chan_id, "name": c.name}
                    for c in provider.channels.values()
                ],
                "message": "Review mapping and PUT to /mapping/<signature> to save",
            }
        )

    except Exception as e:
        logger.error(f"Failed to create mapping from template: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@mapping_bp.route("/mapping/auto-detect", methods=["POST"])
def auto_detect_mapping():
    """Auto-detect channel mappings for a provider.

    Returns a structured 503 when discovery yields no providers, matching
    the contract used by ``/hardware/live/start``:
    ``{ status, error_code, error, message, retryable, retry_after_ms }``.
    The ``ChannelMappingPanel`` consumes this directly to render an
    actionable message instead of a raw HTTP error.
    """
    from api.services.jetdrive.jetdrive_client import JetDriveConfig, discover_providers
    from api.services.jetdrive.jetdrive_mapping import (
        compute_provider_signature,
        create_auto_mapping,
    )

    try:
        data = request.get_json() or {}
        requested_provider_id = data.get("provider_id")

        config = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(discover_providers(config, timeout=5.0))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not providers:
            message = (
                "No JetDrive providers found. Start the dyno (DynoWare/Power Core) "
                "and confirm multicast access, then retry."
            )
            return (
                jsonify(
                    {
                        "status": "no_providers",
                        "error_code": "no_providers",
                        "error": message,
                        "message": message,
                        "retryable": True,
                        "retry_after_ms": 5000,
                    }
                ),
                503,
            )

        provider = None
        if requested_provider_id:
            for p in providers:
                if p.provider_id == requested_provider_id:
                    provider = p
                    break
            if provider is None:
                message = f"Requested provider 0x{int(requested_provider_id):04X} not found."
                return (
                    jsonify(
                        {
                            "status": "provider_not_found",
                            "error_code": "provider_not_found",
                            "error": message,
                            "message": message,
                            "available_provider_ids": [
                                f"0x{p.provider_id:04X}" for p in providers
                            ],
                            "retryable": False,
                        }
                    ),
                    404,
                )
        else:
            provider = providers[0]

        from api.services.jetdrive.mapping_transient_cache import (
            store_transient_mapping,
        )

        signature = compute_provider_signature(provider)
        mapping = create_auto_mapping(provider, signature)
        mapping_dict = mapping.to_dict()

        # Cache the proposal in-memory so the Hardware Configuration UI can
        # show "Unsaved auto-detected mapping" via the unified status
        # endpoint until the operator persists it.
        transient_entry = store_transient_mapping(
            provider_signature=signature,
            provider_id=provider.provider_id,
            provider_name=provider.name,
            host=provider.host,
            mapping=mapping_dict,
            source="auto_detect",
        )

        return jsonify(
            {
                "status": "ok",
                "mapping": mapping_dict,
                "transient_proposal": transient_entry.to_dict(),
                "provider_channels": [
                    {"id": c.chan_id, "name": c.name}
                    for c in provider.channels.values()
                ],
                "unmapped_channels": [
                    {"id": c.chan_id, "name": c.name}
                    for c in provider.channels.values()
                    if c.chan_id not in [m.source_id for m in mapping.channels.values()]
                ],
                "missing_required": mapping.get_missing_required(),
                "missing_recommended": mapping.get_missing_recommended(),
                "message": "Review mapping and PUT to /mapping/<signature> to save",
            }
        )

    except Exception as e:
        logger.error(f"Failed to auto-detect mapping: {e}", exc_info=True)
        return jsonify({"status": "error", "error": str(e)}), 500


@mapping_bp.route("/mapping/transforms", methods=["GET"])
def get_available_transforms():
    """Get list of available value transforms."""
    from api.services.jetdrive.jetdrive_mapping import TRANSFORMS

    transforms: list[dict[str, str]] = []
    for name in TRANSFORMS:
        parts = name.split("_to_")
        if len(parts) == 2:
            description = f"Convert {parts[0].upper()} to {parts[1].upper()}"
        else:
            description = name.replace("_", " ").title()

        transforms.append({"id": name, "name": name, "description": description})

    return jsonify({"transforms": transforms, "count": len(transforms)})


@mapping_bp.route("/mapping/confidence", methods=["GET"])
def get_mapping_confidence():
    """Get confidence report for current or auto-detected mapping."""
    from api.services.jetdrive.jetdrive_client import JetDriveConfig, discover_providers
    from api.services.jetdrive.jetdrive_mapping import (
        RECOMMENDED_CANONICAL,
        ChannelMapping,
        ProviderMapping,
        auto_map_channels_with_confidence,
        compute_provider_signature,
        get_low_confidence_mappings,
        get_mapping,
        get_unmapped_required_channels,
        score_channel_for_canonical,
    )

    try:
        requested_provider_id = request.args.get("provider_id", type=int)

        config = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(discover_providers(config, timeout=5.0))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not providers:
            return jsonify({"error": "No JetDrive providers found"}), 404

        provider = None
        if requested_provider_id:
            for p in providers:
                if p.provider_id == requested_provider_id:
                    provider = p
                    break
            if provider is None:
                return (
                    jsonify(
                        {
                            "error": f"Provider {requested_provider_id} not found",
                            "available": [p.provider_id for p in providers],
                        }
                    ),
                    404,
                )
        else:
            provider = providers[0]

        signature = compute_provider_signature(provider)
        existing_mapping = get_mapping(signature)

        if existing_mapping:
            confidence_map: dict[str, Any] = {}
            all_channels = list(provider.channels.values())

            for canonical_name, channel_mapping in existing_mapping.channels.items():
                channel = provider.channels.get(channel_mapping.source_id)
                if channel:
                    conf = score_channel_for_canonical(
                        channel, canonical_name, all_channels
                    )
                    conf.transform = channel_mapping.transform
                    confidence_map[canonical_name] = conf

            unmapped_required = get_unmapped_required_channels(existing_mapping)
        else:
            confidence_map = auto_map_channels_with_confidence(provider)
            temp_mapping = ProviderMapping(
                provider_signature=signature,
                provider_id=provider.provider_id,
                provider_name=provider.name,
                host=provider.host,
            )
            for canonical_name, conf in confidence_map.items():
                temp_mapping.channels[canonical_name] = ChannelMapping(
                    canonical_name=canonical_name,
                    source_id=conf.source_id,
                    source_name=conf.source_name,
                    transform=conf.transform,
                    enabled=True,
                )
            unmapped_required = get_unmapped_required_channels(temp_mapping)

        if confidence_map:
            overall_confidence = sum(
                c.confidence for c in confidence_map.values()
            ) / len(confidence_map)
        else:
            overall_confidence = 0.0

        low_confidence = get_low_confidence_mappings(confidence_map, threshold=0.7)

        ready_for_capture = (
            len(unmapped_required) == 0
            and overall_confidence >= 0.7
            and len(low_confidence) == 0
        )

        mapped = set(confidence_map.keys())
        unmapped_recommended = [ch for ch in RECOMMENDED_CANONICAL if ch not in mapped]

        return jsonify(
            {
                "success": True,
                "provider_signature": signature,
                "provider_id": provider.provider_id,
                "provider_name": provider.name,
                "overall_confidence": round(overall_confidence, 2),
                "ready_for_capture": ready_for_capture,
                "mappings": [conf.to_dict() for conf in confidence_map.values()],
                "unmapped_required": unmapped_required,
                "unmapped_recommended": unmapped_recommended,
                "low_confidence": [conf.to_dict() for conf in low_confidence],
                "suspected_mislabels": [],
                "has_existing_mapping": existing_mapping is not None,
            }
        )

    except Exception as e:
        logger.error(f"Failed to get mapping confidence: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@mapping_bp.route("/mapping/export/<signature>", methods=["GET"])
def export_mapping(signature: str):
    """Export a mapping as downloadable JSON file."""
    import io
    import json

    from api.services.jetdrive.jetdrive_mapping import get_mapping

    try:
        mapping = get_mapping(signature)
        if not mapping:
            return jsonify({"error": f"Mapping not found: {signature}"}), 404

        export_data = {
            "version": "1.0",
            "type": "dynoai_mapping_export",
            "name": f"{mapping.provider_name} Mapping",
            "description": f"Channel mapping for {mapping.provider_name} (ID: 0x{mapping.provider_id:04X})",
            "created_at": mapping.created_at,
            "exported_at": datetime.now().isoformat(),
            "provider_signature": mapping.provider_signature,
            "provider_id": mapping.provider_id,
            "provider_name": mapping.provider_name,
            "host": mapping.host,
            "channels": {name: ch.to_dict() for name, ch in mapping.channels.items()},
        }

        json_str = json.dumps(export_data, indent=2)
        file_obj = io.BytesIO(json_str.encode("utf-8"))
        file_obj.seek(0)

        safe_name = mapping.provider_name.replace(" ", "_").replace("/", "_")
        filename = f"jetdrive_mapping_{safe_name}_{signature[:8]}.json"

        return send_file(
            file_obj,
            mimetype="application/json",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        logger.error(f"Failed to export mapping: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@mapping_bp.route("/mapping/import", methods=["POST"])
def import_mapping():
    """Import a mapping from JSON file."""
    import json

    from api.services.jetdrive.jetdrive_mapping import ChannelMapping, ProviderMapping, save_mapping

    try:
        mapping_data = None

        if "file" in request.files:
            file = request.files["file"]
            if file.filename and file.filename.endswith(".json"):
                content = file.read().decode("utf-8")
                mapping_data = json.loads(content)
        elif request.is_json:
            mapping_data = request.get_json()

        if not mapping_data:
            return jsonify({"error": "No mapping data provided"}), 400

        if mapping_data.get("type") not in (
            "dynoai_mapping_export",
            "dynoai_mapping_template",
        ):
            return jsonify({"error": "Invalid mapping file format"}), 400

        mapping = ProviderMapping(
            version=mapping_data.get("version", "1.0"),
            provider_signature=mapping_data.get("provider_signature", ""),
            provider_id=mapping_data.get("provider_id", 0),
            provider_name=mapping_data.get("provider_name", "Imported"),
            host=mapping_data.get("host", ""),
            created_at=mapping_data.get("created_at", datetime.now().isoformat()),
        )

        for name, ch_data in mapping_data.get("channels", {}).items():
            mapping.channels[name] = ChannelMapping.from_dict(name, ch_data)

        if save_mapping(mapping):
            return jsonify(
                {
                    "success": True,
                    "mapping": mapping.to_dict(),
                    "message": f"Imported mapping for {mapping.provider_name}",
                }
            )
        else:
            return jsonify({"error": "Failed to save mapping"}), 500

    except Exception as e:
        logger.error(f"Failed to import mapping: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@mapping_bp.route("/mapping/export-template", methods=["POST"])
def export_as_template():
    """Export current mapping as a reusable template."""
    import json

    from api.services.jetdrive.jetdrive_mapping import MAPPING_DIR, get_mapping

    try:
        data = request.get_json()
        signature = data.get("signature")
        template_name = data.get("template_name", "Custom Template")
        description = data.get("description", "")

        if not signature:
            return jsonify({"error": "Missing signature"}), 400

        mapping = get_mapping(signature)
        if not mapping:
            return jsonify({"error": f"Mapping not found: {signature}"}), 404

        template_id = template_name.lower().replace(" ", "_")
        template_data = {
            "version": "1.0",
            "type": "dynoai_mapping_template",
            "name": template_name,
            "description": description or f"Template based on {mapping.provider_name}",
            "created_at": datetime.now().isoformat(),
            "channels": {name: ch.to_dict() for name, ch in mapping.channels.items()},
        }

        MAPPING_DIR.mkdir(parents=True, exist_ok=True)
        template_path = MAPPING_DIR / f"template_{template_id}.json"

        with open(template_path, "w") as f:
            json.dump(template_data, f, indent=2)

        return jsonify(
            {
                "success": True,
                "template_id": template_id,
                "template_name": template_name,
                "message": f"Template saved as {template_path.name}",
            }
        )

    except Exception as e:
        logger.error(f"Failed to export template: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Queue Health
# ---------------------------------------------------------------------------


@mapping_bp.route("/queue/health", methods=["GET"])
def get_queue_health():
    """Get live capture queue health and statistics."""
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager

    try:
        queue_mgr = get_live_queue_manager()
        stats = queue_mgr.get_stats()

        return jsonify({"success": True, "stats": stats, "timestamp": time.time()})
    except Exception as e:
        logger.error(f"Failed to get queue health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mapping_bp.route("/queue/reset", methods=["POST"])
def reset_queue():
    """Reset the live capture queue."""
    from api.services.jetdrive.jetdrive_live_queue import reset_live_queue_manager

    try:
        reset_live_queue_manager()
        return jsonify({"success": True, "message": "Queue reset successfully"})
    except Exception as e:
        logger.error(f"Failed to reset queue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Real-Time Analysis (Phase 4)
# ---------------------------------------------------------------------------


@mapping_bp.route("/realtime/analysis", methods=["GET"])
def get_realtime_analysis():
    """Get current real-time analysis state."""
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager

    try:
        queue_mgr = get_live_queue_manager()
        analysis = queue_mgr.get_realtime_analysis()

        if analysis is None:
            return jsonify(
                {
                    "success": True,
                    "enabled": False,
                    "message": "Realtime analysis not enabled. POST to /realtime/enable to start.",
                }
            )

        return jsonify({"success": True, **analysis})
    except Exception as e:
        logger.error(f"Failed to get realtime analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mapping_bp.route("/realtime/enable", methods=["POST"])
def enable_realtime_analysis():
    """Enable real-time analysis during capture."""
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager

    try:
        target_afr = request.args.get("target_afr", 14.7, type=float)
        queue_mgr = get_live_queue_manager()
        queue_mgr.enable_realtime_analysis(target_afr=target_afr)

        return jsonify(
            {
                "success": True,
                "message": f"Realtime analysis enabled (target AFR: {target_afr})",
                "target_afr": target_afr,
            }
        )
    except Exception as e:
        logger.error(f"Failed to enable realtime analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mapping_bp.route("/realtime/disable", methods=["POST"])
def disable_realtime_analysis():
    """Disable real-time analysis."""
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager

    try:
        queue_mgr = get_live_queue_manager()
        queue_mgr.disable_realtime_analysis()
        return jsonify({"success": True, "message": "Realtime analysis disabled"})
    except Exception as e:
        logger.error(f"Failed to disable realtime analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mapping_bp.route("/realtime/reset", methods=["POST"])
def reset_realtime_analysis():
    """Reset real-time analysis state."""
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager
    from api.services.jetdrive.jetdrive_realtime_analysis import reset_realtime_engine

    try:
        queue_mgr = get_live_queue_manager()

        if not queue_mgr.realtime_analysis_enabled:
            return (
                jsonify(
                    {"success": False, "error": "Realtime analysis not enabled"}
                ),
                400,
            )

        reset_realtime_engine()

        target_afr = request.args.get("target_afr", 14.7, type=float)
        queue_mgr.enable_realtime_analysis(target_afr=target_afr)

        return jsonify({"success": True, "message": "Realtime analysis reset"})
    except Exception as e:
        logger.error(f"Failed to reset realtime analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
