import os
import unittest
from unittest import mock
from unittest.mock import patch

from dynoai.clients import xai_client


class TestXAIClient(unittest.TestCase):
    def test_extract_content_happy(self):
        sample = {"choices": [{"message": {"content": "hello"}}]}
        self.assertEqual(xai_client.extract_content(sample), "hello")

    def test_extract_content_empty(self):
        sample = {"choices": [{}]}
        self.assertEqual(xai_client.extract_content(sample), "")

    @patch.dict(os.environ, {}, clear=True)
    def test_chat_grok_missing_key(self):
        with self.assertRaises(xai_client.XAIError) as ctx:
            xai_client.chat_grok(messages=[{"role": "user", "content": "hi"}])
        self.assertIn("Missing XAI_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {"XAI_API_KEY": "test"}, clear=True)
    def test_chat_grok_success(self):
        fake_json = {"choices": [{"message": {"content": "ok"}}]}
        with mock.patch("requests.Session.post") as mpost:
            mresp = mock.Mock(status_code=200)
            mresp.json.return_value = fake_json
            mpost.return_value = mresp
            out = xai_client.chat_grok(
                messages=[{"role": "user", "content": "hi"}], max_tokens=5
            )
        self.assertEqual(out, fake_json)
        self.assertEqual(xai_client.extract_content(out), "ok")

    @patch.dict(os.environ, {"XAI_API_KEY": "test"}, clear=True)
    def test_chat_grok_error(self):
        with mock.patch("requests.Session.post") as mpost:
            mresp = mock.Mock(status_code=500, text="boom")
            mpost.return_value = mresp
            with self.assertRaises(xai_client.XAIError) as ctx:
                xai_client.chat_grok(
                    messages=[{"role": "user", "content": "hi"}], max_tokens=5
                )
            self.assertIn("500", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
