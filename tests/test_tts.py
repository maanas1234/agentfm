import sys
import types

import httpx
import pytest

from agentfm.daemon.config import TTSConfig
from agentfm.daemon.tts import should_use_remote, speak_local, synthesize


def test_should_use_remote_requires_enabled_url_and_key():
    assert should_use_remote(TTSConfig(enabled=True, base_url="https://x", api_key="k")) is True
    assert should_use_remote(TTSConfig(enabled=False, base_url="https://x", api_key="k")) is False
    assert should_use_remote(TTSConfig(enabled=True, base_url="", api_key="k")) is False
    assert should_use_remote(TTSConfig(enabled=True, base_url="https://x", api_key="")) is False


@pytest.mark.asyncio
async def test_synthesize_posts_to_byok_endpoint_and_returns_audio_bytes():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=b"FAKE_MP3_BYTES")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = TTSConfig(enabled=True, base_url="https://my-tts.example/v1", api_key="secret", voice="nova")

    audio = await synthesize(config, "Agent is reading foo.py.", client=client)

    assert audio == b"FAKE_MP3_BYTES"
    assert captured["url"] == "https://my-tts.example/v1/audio/speech"
    assert captured["auth"] == "Bearer secret"

    await client.aclose()


@pytest.mark.asyncio
async def test_synthesize_returns_empty_bytes_for_empty_text():
    config = TTSConfig(enabled=True, base_url="https://x", api_key="k")
    assert await synthesize(config, "") == b""


def test_speak_local_uses_pyttsx3_engine(monkeypatch):
    calls = []

    fake_engine = types.SimpleNamespace(
        say=lambda text: calls.append(("say", text)),
        runAndWait=lambda: calls.append(("runAndWait",)),
    )
    fake_module = types.SimpleNamespace(init=lambda: fake_engine)
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_module)

    speak_local("Agent is done.")

    assert calls == [("say", "Agent is done."), ("runAndWait",)]


def test_speak_local_noop_for_empty_text(monkeypatch):
    def _fail_init():
        raise AssertionError("should not init engine for empty text")

    monkeypatch.setitem(sys.modules, "pyttsx3", types.SimpleNamespace(init=_fail_init))
    speak_local("")
