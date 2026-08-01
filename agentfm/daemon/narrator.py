"""Batches Events and turns them into a short spoken-style narration via the
user's BYOK OpenAI-compatible LLM endpoint. No hosted proxy involved — this
calls straight out to config.llm.base_url from the user's own machine.
"""

from __future__ import annotations

import httpx

from agentfm.daemon.config import LLMConfig
from agentfm.daemon.events import Event

DEBOUNCE_SECONDS = 7.0
IMMEDIATE_KINDS = {"waiting", "error"}

_SYSTEM_PROMPT = (
    "Narrate an AI coding agent's activity for a listener, as a radio announcer would. "
    "Output ONLY the spoken sentence itself — one sentence, present-tense, under 15 words. "
    "Do not explain your reasoning, do not restate these instructions, do not use quotes "
    "or preamble like 'Here's the narration:'. Just the sentence."
)

_EXAMPLE_EVENTS = "[tool_call] ● Reading foo.py…"
_EXAMPLE_NARRATION = "The agent reads foo.py."

MAX_NARRATION_CHARS = 220


def build_digest(events: list[Event]) -> str:
    return "\n".join(f"[{e.kind}] {e.detail}" for e in events)


def looks_like_leaked_reasoning(text: str) -> bool:
    """Some reasoning models occasionally narrate their own interpretation of
    the system prompt instead of following it -- a multi-paragraph dump full
    of word-counting and self-quoted instructions instead of one sentence.
    TTS would read that whole thing aloud, so catch it before it gets there."""
    if len(text) > MAX_NARRATION_CHARS:
        return True
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("let's count", "radio announcer", "the instruction:", "constraints:")
    )


def _fallback_narration(events: list[Event]) -> str:
    return build_digest(events[-1:])


class EventBatcher:
    """Pure batching logic: debounce normal events, flush immediately on
    waiting/error so blockers get narrated right away."""

    def __init__(self, debounce_seconds: float = DEBOUNCE_SECONDS):
        self.debounce_seconds = debounce_seconds
        self._pending: list[Event] = []
        self._first_ts: float | None = None

    def add(self, event: Event) -> bool:
        """Returns True if this event should trigger an immediate flush."""
        self._pending.append(event)
        if self._first_ts is None:
            self._first_ts = event.ts
        return event.kind in IMMEDIATE_KINDS

    def should_flush(self, now: float) -> bool:
        if not self._pending or self._first_ts is None:
            return False
        return (now - self._first_ts) >= self.debounce_seconds

    def flush(self) -> list[Event]:
        events = self._pending
        self._pending = []
        self._first_ts = None
        return events


class Narrator:
    def __init__(self, config: LLMConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self._client = client

    async def summarize(self, events: list[Event]) -> str:
        if not events:
            return ""

        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient()
        try:
            text = await self._call(events, client)
            if looks_like_leaked_reasoning(text):
                text = await self._call(events, client)
            if looks_like_leaked_reasoning(text):
                text = _fallback_narration(events)
            return text
        finally:
            if owns_client:
                await client.aclose()

    async def _call(self, events: list[Event], client: httpx.AsyncClient) -> str:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _EXAMPLE_EVENTS},
                {"role": "assistant", "content": _EXAMPLE_NARRATION},
                {"role": "user", "content": build_digest(events)},
            ],
            "max_tokens": 300,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
