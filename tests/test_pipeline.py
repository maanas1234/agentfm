import asyncio
import base64
import json
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from agentfm.daemon.config import AppConfig, LLMConfig, TTSConfig
from agentfm.daemon.events import Event
from agentfm.daemon.pipeline import NarrationPipeline
from agentfm.daemon.server import app, broadcaster


def _llm_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "Agent read foo.py."}}]}
    )


def _tts_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"FAKE_AUDIO")


def test_pipeline_narrates_immediately_on_waiting_event_with_remote_tts(monkeypatch):
    config = AppConfig(
        llm=LLMConfig(base_url="https://llm.example/v1", api_key="k", model="m"),
        tts=TTSConfig(enabled=True, base_url="https://tts.example/v1", api_key="k", voice="nova"),
    )
    pipeline = NarrationPipeline(config)

    async def fake_summarize(events):
        return "Agent is waiting for approval."

    async def fake_synthesize(tts_config, text, client=None):
        return b"FAKE_AUDIO"

    monkeypatch.setattr(pipeline.narrator, "summarize", fake_summarize)
    monkeypatch.setattr("agentfm.daemon.pipeline.synthesize", fake_synthesize)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            pipeline.on_event(
                Event(session_id="s1", kind="waiting", detail="Do you want to proceed?")
            )
            message = ws.receive_json()

    assert message["type"] == "narration"
    assert message["session_id"] == "s1"
    assert message["text"] == "Agent is waiting for approval."
    assert base64.b64decode(message["audio_b64"]) == b"FAKE_AUDIO"
    assert message["audio_mime"] == "audio/mpeg"


def test_pipeline_speaks_locally_when_no_remote_tts_configured(monkeypatch):
    config = AppConfig(llm=LLMConfig(base_url="https://llm.example/v1", api_key="k", model="m"))
    pipeline = NarrationPipeline(config)

    async def fake_summarize(events):
        return "Agent finished the edit."

    monkeypatch.setattr(pipeline.narrator, "summarize", fake_summarize)

    spoken = []
    monkeypatch.setattr("agentfm.daemon.pipeline.speak_local", lambda text: spoken.append(text))

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            pipeline.on_event(Event(session_id="s2", kind="error", detail="Error: boom"))
            message = ws.receive_json()

    assert message["type"] == "narration"
    assert message["audio_b64"] is None
    assert spoken == ["Agent finished the edit."]


def test_pipeline_does_nothing_when_llm_not_configured():
    config = AppConfig()
    pipeline = NarrationPipeline(config)
    pipeline.on_event(Event(session_id="s3", kind="waiting", detail="x"))
    assert pipeline.batchers == {}


def test_pipeline_debounces_non_blocking_events_until_timeout():
    config = AppConfig(llm=LLMConfig(base_url="https://llm.example/v1", api_key="k", model="m"))
    pipeline = NarrationPipeline(config)

    pipeline.on_event(Event(session_id="s4", kind="tool_call", detail="a", ts=100.0))
    batcher = pipeline.batchers["s4"]
    assert batcher.should_flush(now=101.0) is False

    pipeline.check_timeouts(now=101.0)
    assert len(batcher._pending) == 1
