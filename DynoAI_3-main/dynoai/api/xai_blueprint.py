from __future__ import annotations

from flask import Blueprint, jsonify, request

from dynoai.clients.xai_client import XAIError, chat_grok, extract_content

xai_bp = Blueprint("xai", __name__)

MAX_TOKENS_CAP = 1024
TEMP_MIN, TEMP_MAX = 0.0, 1.0


@xai_bp.post("/api/xai/chat")
def xai_chat():
    try:
        body = request.get_json(silent=True) or {}
        messages = body.get("messages", [])
        model = body.get("model")
        max_tokens = min(int(body.get("max_tokens", 256)), MAX_TOKENS_CAP)
        temperature = float(body.get("temperature", 0.7))
        if temperature < TEMP_MIN or temperature > TEMP_MAX:
            temperature = 0.7

        if not isinstance(messages, list) or not messages:
            return jsonify({"error": "Invalid or empty 'messages'"}), 400

        result = chat_grok(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return (
            jsonify(
                {
                    "content": extract_content(result),
                    "raw": result,
                }
            ),
            200,
        )

    except XAIError as e:
        return jsonify({"error": str(e)}), 502
    except Exception:
        return jsonify({"error": "Unexpected server error"}), 500
