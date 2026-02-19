import os
import unittest
from unittest.mock import patch

from flask import Flask


def _load_app() -> Flask:
    # Ensure env for import
    os.environ.setdefault("XAI_API_KEY", "sk-test")
    from api.app import app  # app already registers blueprint lazily

    return app


class TestXAIChatBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _load_app()
        self.client = self.app.test_client()

    @patch("dynoai.api.xai_blueprint.chat_grok")
    def test_chat_success(self, mock_chat):
        mock_chat.return_value = {"choices": [{"message": {"content": "ok"}}]}
        resp = self.client.post(
            "/api/xai/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("content"), "ok")
        self.assertIn("raw", data)

    def test_chat_validation_error(self):
        resp = self.client.post("/api/xai/chat", json={})
        self.assertEqual(resp.status_code, 400)

    @patch("dynoai.api.xai_blueprint.chat_grok", side_effect=Exception("boom"))
    def test_chat_unexpected(self, _mock_chat):
        resp = self.client.post(
            "/api/xai/chat",
            json={"messages": [{"role": "user", "content": "X"}]},
        )
        # Generic exception path returns 500
        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
