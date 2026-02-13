from __future__ import annotations

from flask import Blueprint, jsonify, request

from api.services.parsers.file_index import FileType, get_file_index
from api.services.yourdyno import (
    find_yourdyno_run_files,
    parse_yourdyno_run,
)

import_bp = Blueprint("yourdyno_import", __name__)


@import_bp.route("/discover/runs", methods=["GET"])
def discover_runs():
    """
    Discover likely YourDyno run/export files and return secure file IDs.
    """
    file_index = get_file_index()
    runs = find_yourdyno_run_files()

    files = []
    for f in runs[:100]:
        try:
            file_id = file_index.register(f, FileType.YOURDYNO)
            entry = file_index.get_entry(file_id)
            if entry:
                api = entry.to_api_response()
                api["extension"] = f.suffix
                files.append(api)
        except (FileNotFoundError, ValueError):
            continue

    return jsonify({"count": len(files), "files": files})


@import_bp.route("/import/parse", methods=["POST"])
def parse_run():
    """
    Parse a YourDyno run file and return normalized preview data.

    Request body:
      { "file_id": "..." }       preferred
      { "path": "C:/...csv" }    legacy fallback
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    if "file_id" in data:
        file_index = get_file_index()
        try:
            safe_path = file_index.resolve(
                data["file_id"], expected_type=FileType.YOURDYNO
            )
        except KeyError:
            return jsonify({"error": "Invalid or expired file_id"}), 400
        except ValueError:
            return (
                jsonify({"error": "File type mismatch: expected YourDyno run file"}),
                400,
            )
        except FileNotFoundError:
            return jsonify({"error": "File no longer exists"}), 404
    elif "path" in data:
        # Legacy fallback path usage, intentionally simple for local workflows.
        safe_path = data["path"]
    else:
        return jsonify({"error": "Missing 'file_id' in request body"}), 400

    try:
        run = parse_yourdyno_run(str(safe_path))
        normalized = run.normalized_data
        raw = run.raw_data

        return jsonify(
            {
                "success": True,
                "rows": len(raw),
                "columns": list(raw.columns),
                "normalized_columns": list(normalized.columns),
                "detected_columns": run.detected_columns,
                "preview": normalized.head(10).to_dict(orient="records"),
                "source_path": run.source_path,
            }
        )
    except Exception:
        return (
            jsonify({"success": False, "error": "Failed to parse YourDyno run file"}),
            500,
        )


@import_bp.route("/formats", methods=["GET"])
def supported_formats():
    """
    Describe supported YourDyno import formats and minimum data expectations.
    """
    return jsonify(
        {
            "supported_extensions": [".csv", ".txt"],
            "required_for_live_dashboard": ["Engine RPM", "Horsepower", "Torque"],
            "required_for_ve_corrections": ["Engine RPM", "AFR Meas", "MAP kPa"],
            "optional_columns": [
                "AFR Meas F",
                "AFR Meas R",
                "TPS",
                "IAT F",
                "Engine Temp",
                "Vehicle Speed",
                "Force",
                "Time_ms",
                "Time_s",
            ],
        }
    )
