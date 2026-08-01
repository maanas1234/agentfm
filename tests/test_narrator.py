import json

import httpx
import pytest

from agentfm.daemon.config import LLMConfig
from agentfm.daemon.events import Event
from agentfm.daemon.narrator import (
    EventBatcher,
    Narrator,
    build_digest,
    looks_like_leaked_reasoning,
)


def _event(kind: str, detail: str, ts: float) -> Event:
    return Event(session_id="s1", kind=kind, detail=detail, ts=ts)


def test_build_digest_formats_kind_and_detail():
    events = [_event("tool_call", "⏺ Read(foo.py)", 1.0), _event("edit", "⏺ Edit(bar.py)", 2.0)]
    digest = build_digest(events)
    assert digest == "[tool_call] ⏺ Read(foo.py)\n[edit] ⏺ Edit(bar.py)"


def test_batcher_does_not_flush_before_debounce():
    batcher = EventBatcher(debounce_seconds=5.0)
    immediate = batcher.add(_event("tool_call", "x", 100.0))
    assert immediate is False
    assert batcher.should_flush(now=102.0) is False
    assert batcher.should_flush(now=105.5) is True


def test_batcher_flushes_immediately_on_waiting_or_error():
    batcher = EventBatcher(debounce_seconds=999.0)
    assert batcher.add(_event("waiting", "Do you want to proceed?", 1.0)) is True
    assert batcher.add(_event("error", "Error: boom", 2.0)) is True
    assert batcher.add(_event("tool_call", "x", 3.0)) is False


def test_batcher_flush_returns_and_clears_pending():
    batcher = EventBatcher()
    batcher.add(_event("tool_call", "a", 1.0))
    batcher.add(_event("tool_call", "b", 2.0))
    events = batcher.flush()
    assert [e.detail for e in events] == ["a", "b"]
    assert batcher.flush() == []
    assert batcher.should_flush(now=9999.0) is False


@pytest.mark.asyncio
async def test_narrator_summarize_calls_configured_endpoint_with_byok_key():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Agent is reading foo.py."}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    config = LLMConfig(base_url="https://my-provider.example/v1", api_key="secret-key", model="my-model")
    narrator = Narrator(config=config, client=client)

    result = await narrator.summarize([_event("tool_call", "⏺ Read(foo.py)", 1.0)])

    assert result == "Agent is reading foo.py."
    assert captured["url"] == "https://my-provider.example/v1/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["body"]["model"] == "my-model"
    assert "Read(foo.py)" in captured["body"]["messages"][-1]["content"]

    await client.aclose()


@pytest.mark.asyncio
async def test_narrator_summarize_returns_empty_string_for_no_events():
    config = LLMConfig(base_url="https://x", api_key="k", model="m")
    narrator = Narrator(config=config)
    assert await narrator.summarize([]) == ""


def test_looks_like_leaked_reasoning_flags_oversized_text():
    assert looks_like_leaked_reasoning("The agent reads foo.py.") is False
    assert looks_like_leaked_reasoning("x" * 300) is True


def test_looks_like_leaked_reasoning_flags_giveaway_phrases():
    assert looks_like_leaked_reasoning("Let's count: The(1) agent(2)...") is True
    assert looks_like_leaked_reasoning("As a radio announcer would say...") is True


@pytest.mark.asyncio
async def test_narrator_retries_once_then_falls_back_on_leaked_reasoning():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Let's count the words. " * 20}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = LLMConfig(base_url="https://x", api_key="k", model="m")
    narrator = Narrator(config=config, client=client)

    result = await narrator.summarize([_event("error", "Exit 127, boom", 1.0)])

    assert call_count == 2
    assert result == "[error] Exit 127, boom"

    await client.aclose()


@pytest.mark.asyncio
async def test_narrator_accepts_clean_response_on_retry():
    responses = iter(
        [
            {"choices": [{"message": {"content": "Let's count the words. " * 20}}]},
            {"choices": [{"message": {"content": "The agent hits an error."}}]},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = LLMConfig(base_url="https://x", api_key="k", model="m")
    narrator = Narrator(config=config, client=client)

    result = await narrator.summarize([_event("error", "Exit 127, boom", 1.0)])

    assert result == "The agent hits an error."

    await client.aclose()
