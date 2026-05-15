"""Notifications configuration routes."""

from flask import Blueprint, jsonify, request

from api.services.sms_notifier import get_config, save_config, send_test_message

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/twilio/config", methods=["GET"])
def get_twilio_config():
    """Get current Twilio configuration."""
    config = get_config()

    # Mask sensitive values before sending to frontend
    masked_config = {**config}
    if masked_config.get("auth_token"):
        token = masked_config["auth_token"]
        if len(token) > 8:
            masked_config["auth_token"] = f"{token[:4]}...{token[-4:]}"
        else:
            masked_config["auth_token"] = "***"

    return jsonify(masked_config), 200


@notifications_bp.route("/twilio/config", methods=["PUT"])
def update_twilio_config():
    """Update Twilio configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Load existing config to preserve unmasked values if they weren't changed
        existing = get_config()

        new_config = {
            "account_sid": data.get("account_sid", existing.get("account_sid", "")),
            "from_number": data.get("from_number", existing.get("from_number", "")),
            "alert_to": data.get("alert_to", existing.get("alert_to", "")),
            "enabled": data.get("enabled", existing.get("enabled", True))
        }

        # Only update auth_token if it's provided and not masked
        if "auth_token" in data and data["auth_token"] and "..." not in data["auth_token"] and "***" not in data["auth_token"]:
            new_config["auth_token"] = data["auth_token"]
        else:
            new_config["auth_token"] = existing.get("auth_token", "")

        save_config(new_config)

        return jsonify({"message": "Configuration updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/twilio/test", methods=["POST"])
def test_twilio_config():
    """Send a test SMS message."""
    try:
        result = send_test_message()
        if result.get("success"):
            return jsonify({"message": "Test SMS sent successfully", "sid": result.get("sid")}), 200
        else:
            return jsonify({"error": result.get("error", "Unknown error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
