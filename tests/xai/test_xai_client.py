from unittest import mock

from dynoai.clients import xai_client


def test_extract_content_happy():
    sample = {"choices": [{"message": {"content": "hello"}}]}
    assert xai_client.extract_content(sample) == "hello"


def test_extract_content_empty():
    sample = {"choices": [{}]}
    assert xai_client.extract_content(sample) == ""


def test_chat_grok_missing_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    try:
        xai_client.chat_grok(messages=[{"role": "user", "content": "hi"}])
    except xai_client.XAIError as e:
        assert "Missing XAI_API_KEY" in str(e)
    else:  # pragma: no cover
        assert False, "Expected XAIError"


def test_chat_grok_success(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test")
    fake_json = {"choices": [{"message": {"content": "ok"}}]}
    with mock.patch("requests.Session.post") as mpost:
        mresp = mock.Mock(status_code=200)
        mresp.json.return_value = fake_json
        mpost.return_value = mresp
        out = xai_client.chat_grok(
            messages=[{"role": "user", "content": "hi"}], max_tokens=5
        )
    assert out == fake_json
    assert xai_client.extract_content(out) == "ok"


def test_chat_grok_error(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test")
    with mock.patch("requests.Session.post") as mpost:
        mresp = mock.Mock(status_code=500, text="boom")
        mpost.return_value = mresp
        try:
            xai_client.chat_grok(
                messages=[{"role": "user", "content": "hi"}], max_tokens=5
            )
        except xai_client.XAIError as e:
            assert "500" in str(e)
        else:  # pragma: no cover
            assert False, "Expected XAIError"
