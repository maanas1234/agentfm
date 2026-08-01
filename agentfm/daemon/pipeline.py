"""Ties EventBatcher + Narrator + TTS + Broadcaster together per session.

Fed synchronously from the PTY-reading thread via `on_event`/`check_timeouts`;
schedules narration work onto the broadcaster's asyncio loop so it never
blocks the terminal passthrough.
"""

from __future__ import annotations

import asyncio
import sys

from agentfm.daemon.config import AppConfig
from agentfm.daemon.events import Event
from agentfm.daemon.narrator import EventBatcher, Narrator
from agentfm.daemon.server import broadcaster
from agentfm.daemon.tts import should_use_remote, speak_local, synthesize


class NarrationPipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.narrator = Narrator(config.llm)
        self.batchers: dict[str, EventBatcher] = {}

    def on_event(self, event: Event) -> None:
        if not self.config.llm.base_url:
            return
        batcher = self.batchers.setdefault(event.session_id, EventBatcher())
        if batcher.add(event):
            self._schedule_flush(event.session_id, batcher)

    def check_timeouts(self, now: float) -> None:
        if not self.config.llm.base_url:
            return
        for session_id, batcher in self.batchers.items():
            if batcher.should_flush(now):
                self._schedule_flush(session_id, batcher)

    def _schedule_flush(self, session_id: str, batcher: EventBatcher) -> None:
        events = batcher.flush()
        if not events or broadcaster.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._narrate(session_id, events), broadcaster.loop)

    async def _narrate(self, session_id: str, events: list[Event]) -> None:
        try:
            text = await self.narrator.summarize(events)
            if not text:
                return
            if should_use_remote(self.config.tts):
                audio = await synthesize(self.config.tts, text)
                await broadcaster.publish_narration_async(session_id, text, audio)
            else:
                await broadcaster.publish_narration_async(session_id, text, None)
                await asyncio.get_running_loop().run_in_executor(None, speak_local, text)
        except Exception as exc:
            print(f"agentfm: narration failed: {exc}", file=sys.stderr)
