"""Jetstream configuration routes."""

import json
import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from api.jetstream.models import JetstreamConfig
from api.jetstream.poller import get_poller, init_poller
from io_contracts import safe_path

config_bp = Blueprint("jetstream_config", __name__)

# Default config file path
CONFIG_FILE = "config/jetstream.json"


def _get_config_path() -> Path:
    """Get the safe path to the config file."""
    return safe_path(CONFIG_FILE)


def _load_config() -> JetstreamConfig:
    """Load configuration from file or environment."""
    config_path = _get_config_path()

    # Try loading from file first
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JetstreamConfig.from_dict(data)
        except (json.JSONDecodeError, IOError):
            pass

    # Fall back to environment variables
    return JetstreamConfig(
        api_url=os.environ.get("JETSTREAM_API_URL", ""),
        api_key=os.environ.get("JETSTREAM_API_KEY", ""),
        poll_interval_seconds=int(os.environ.get("JETSTREAM_POLL_INTERVAL", "30")),
        auto_process=os.environ.get("JETSTREAM_AUTO_PROCESS", "true").lower() == "true",
        enabled=os.environ.get("JETSTREAM_ENABLED", "false").lower() == "true",
    )


def _save_config(config: JetstreamConfig) -> None:
    """Save configuration to file."""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Save without masking the API key
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(mask_key=False), f, indent=2)


@config_bp.route("/config", methods=["GET"])
def get_config():
    """
    Get Jetstream config.
    ---
    tags:
      - Jetstream
    summary: Get Jetstream configuration
    description: |
      Returns the current Jetstream configuration.
      The API key is masked for security (shows only first and last 4 characters).
    responses:
      200:
        description: Jetstream configuration
        schema:
          $ref: '#/definitions/JetstreamConfig'
        examples:
          application/json:
            api_url: "https://api.jetstream.example.com"
            api_key: "abc1****xyz9"
            poll_interval_seconds: 30
            auto_process: true
            enabled: true
    """
    config = _load_config()
    return jsonify(config.to_dict(mask_key=True)), 200


@config_bp.route("/config", methods=["PUT"])
def update_config():
    """
    Update Jetstream config.
    ---
    tags:
      - Jetstream
    summary: Update Jetstream configuration
    description: |
      Update the Jetstream configuration. Only provided fields will be updated.

      **Note:** To update the API key, provide the full unmasked key.
      If the provided api_key contains asterisks, it will be ignored.
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/JetstreamConfig'
    responses:
      200:
        description: Configuration updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Configuration updated"
            config:
              $ref: '#/definitions/JetstreamConfig'
      400:
        description: Validation error (e.g., missing API URL when enabling)
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Load existing config
        existing = _load_config()

        # Update only provided fields
        if "api_url" in data:
            existing.api_url = data["api_url"]
        if "api_key" in data:
            # Only update if a new key is provided (not masked)
            if data["api_key"] and "*" not in data["api_key"]:
                existing.api_key = data["api_key"]
        if "poll_interval_seconds" in data:
            existing.poll_interval_seconds = int(data["poll_interval_seconds"])
        if "auto_process" in data:
            existing.auto_process = bool(data["auto_process"])
        if "enabled" in data:
            existing.enabled = bool(data["enabled"])

        # Validate
        if existing.enabled and (not existing.api_url or not existing.api_key):
            return (
                jsonify(
                    {
                        "error": "API URL and API key are required when enabling Jetstream"
                    }
                ),
                400,
            )

        # Save updated config
        _save_config(existing)

        # Update poller if running
        poller = get_poller()
        if poller:
            poller.configure(existing)

        return (
            jsonify(
                {
                    "message": "Configuration updated",
                    "config": existing.to_dict(mask_key=True),
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_current_config() -> JetstreamConfig:
    """Get the current configuration (for use by other modules)."""
    return _load_config()
