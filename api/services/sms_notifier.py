"""
SMS notifications for DynoAI run events via Twilio.

Sends an SMS to a configured number when:
  - A run completes successfully (includes peak HP/TQ and any clamp warnings)
  - A run fails with an error

All SMS sends run in a background thread — they never block analysis.
Configuration is opt-in: if TWILIO_* env vars are absent and config file is missing,
this module is a no-op. No exception is ever raised to the caller.

Required config (all must be set for SMS to send):
  account_sid   — Twilio Account SID (starts with AC)
  auth_token    — Twilio Auth Token
  from_number   — Your Twilio phone number (E.164, e.g. +15005550006)
  alert_to      — Recipient number (E.164, e.g. +15551234567)
"""

import json
import logging
import os
import threading
from typing import Any, Optional

from dynoai.core.io_contracts import safe_path

logger = logging.getLogger(__name__)

CONFIG_FILE = "config/twilio.json"

_REQUIRED_VARS = (
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "TWILIO_ALERT_TO",
)


def get_config() -> dict[str, str]:
    """Get the current Twilio configuration, merging file and env vars."""
    config = {
        "account_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "from_number": os.environ.get("TWILIO_FROM_NUMBER", ""),
        "alert_to": os.environ.get("TWILIO_ALERT_TO", ""),
        "enabled": True,
    }

    try:
        config_path = safe_path(CONFIG_FILE)
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                file_config = json.load(f)
                # File config overrides env vars if present
                for k in ["account_sid", "auth_token", "from_number", "alert_to"]:
                    if file_config.get(k):
                        config[k] = file_config[k]
                if "enabled" in file_config:
                    config["enabled"] = bool(file_config["enabled"])
    except Exception as e:
        logger.warning(f"Failed to read Twilio config file: {e}")

    return config


def save_config(config: dict[str, Any]) -> None:
    """Save Twilio configuration to file."""
    try:
        config_path = safe_path(CONFIG_FILE)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save Twilio config: {e}")
        raise


def _is_configured(config: dict[str, str] | None = None) -> bool:
    cfg = config or get_config()
    if not cfg.get("enabled", True):
        return False
    return all(cfg.get(k) for k in ["account_sid", "auth_token", "from_number", "alert_to"])


def _get_client(config: dict[str, str]):
    """Return a Twilio REST client, or None if twilio is not installed."""
    try:
        from twilio.rest import Client  # type: ignore[import-not-found]

        return Client(config["account_sid"], config["auth_token"])
    except ImportError:
        logger.warning(
            "twilio package not installed — SMS notifications disabled. "
            "Run: pip install twilio"
        )
        return None


def _send_async(body: str) -> None:
    """Fire-and-forget SMS in a daemon thread."""
    config = get_config()
    if not _is_configured(config):
        logger.debug("Twilio SMS not configured or disabled — skipping notification.")
        return

    client = _get_client(config)
    if client is None:
        return

    from_number = config["from_number"]
    to_number = config["alert_to"]

    def _send():
        try:
            msg = client.messages.create(body=body, from_=from_number, to=to_number)
            logger.info("SMS sent (SID=%s) to %s", msg.sid, to_number)
        except Exception:
            logger.exception("Twilio SMS send failed")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def notify_run_complete(run_id: str, results_summary: Optional[dict[str, Any]]) -> None:
    """
    Send an SMS when a DynoAI run completes.

    Highlights clipped VE zones in the message as a safety signal — if
    corrections were clamped it means the measured AFR deviated enough that
    the safety clamp engaged, which warrants a closer look.
    """
    if not _is_configured():
        return

    summary = results_summary or {}

    # Extract key metrics from the summary dict (all optional)
    peak_hp: Optional[float] = summary.get("peak_hp")
    peak_tq: Optional[float] = summary.get("peak_tq")
    zones_adjusted: Optional[int] = summary.get("zones_adjusted")
    clipped_zones: Optional[int] = summary.get("clipped_zones")
    max_correction_pct: Optional[float] = summary.get("max_correction_pct")

    lines = [f"DynoAI run {run_id} COMPLETE"]

    if peak_hp is not None:
        lines.append(f"Peak: {peak_hp:.1f} HP")
    if peak_tq is not None:
        lines.append(f"       {peak_tq:.1f} ft-lb")

    if zones_adjusted is not None:
        lines.append(f"VE zones adjusted: {zones_adjusted}")
    if max_correction_pct is not None:
        lines.append(f"Max correction: {max_correction_pct:+.1f}%")

    if clipped_zones:
        lines.append(
            f"CLAMP WARNING: {clipped_zones} zone(s) hit the safety clamp — "
            "review corrections before applying."
        )

    _send_async("\n".join(lines))


def notify_run_error(run_id: str, stage: str, message: str) -> None:
    """Send an SMS when a DynoAI run fails."""
    if not _is_configured():
        return

    body = f"DynoAI run {run_id} FAILED\nStage: {stage}\n{message}"
    _send_async(body)

def send_test_message() -> dict[str, Any]:
    """Send a test message synchronously and return the result."""
    config = get_config()
    if not _is_configured(config):
        return {"success": False, "error": "Twilio SMS not fully configured."}

    client = _get_client(config)
    if client is None:
        return {"success": False, "error": "twilio package not installed."}

    from_number = config["from_number"]
    to_number = config["alert_to"]

    try:
        msg = client.messages.create(
            body="DynoAI: This is a test SMS notification. Your configuration is working!",
            from_=from_number,
            to=to_number
        )
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        logger.exception("Twilio SMS test failed")
        return {"success": False, "error": str(e)}
