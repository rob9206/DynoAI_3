from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

XAI_API_URL = os.getenv("XAI_API_URL", "https://api.x.ai/v1/chat/completions")
DEFAULT_MODEL = os.getenv("XAI_MODEL", "grok-2")


class XAIError(Exception):
    """Raised for non-200 responses or invalid responses from xAI."""


def _session_with_retry() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def chat_grok(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: int = 256,
    temperature: float = 0.7,
    timeout: int = 30,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calls xAI chat completions and returns the full JSON result.
    messages: [{"role": "user"|"system"|"assistant", "content": str}, ...]
    extra: optional dict to pass additional parameters supported by xAI (e.g., top_p).
    """
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise XAIError("Missing XAI_API_KEY environment variable")

    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra:
        payload.update(extra)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Request-ID": str(uuid.uuid4()),
    }

    s = _session_with_retry()
    resp = s.post(XAI_API_URL, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise XAIError(f"xAI error {resp.status_code}: {resp.text[:800]}")
    return resp.json()


def extract_content(resp_json: Dict[str, Any]) -> str:
    """Safely extract assistant content from an OpenAI-style response."""
    try:
        return (
            resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        ) or ""
    except Exception:
        return ""


def list_models(timeout: int = 30) -> Dict[str, Any]:
    """Optional: list available models (if permitted by account)."""
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise XAIError("Missing XAI_API_KEY environment variable")
    s = _session_with_retry()
    r = s.get(
        "https://api.x.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise XAIError(f"List models error {r.status_code}: {r.text[:800]}")
    return r.json()


if __name__ == "__main__":
    result = chat_grok(
        messages=[
            {
                "role": "user",
                "content": "Hello, Grok! How can you help with my DynoAI app?",
            }
        ],
        max_tokens=100,
    )
    print(extract_content(result) or "[No content in response]")
