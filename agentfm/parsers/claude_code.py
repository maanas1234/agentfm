"""Parse raw Claude Code CLI output into structured Events.

Claude Code renders tool calls as `⏺ ToolName(args)`, results indented below
with `⎿`, a spinner line while working (a random whimsical verb each time --
`✻ Fiddle-faddling… (esc to interrupt · 4s · 102 tokens)`, `✻ Thinking…`,
etc. -- so the check matches the shape, not a fixed word list), and
permission prompts as numbered `❯ 1. Yes` menus. This module turns that text
stream into Event objects.
"""

from __future__ import annotations

import re

from agentfm.daemon.events import Event
from agentfm.parsers.ansi import strip_ansi

_TOOL_CALL_RE = re.compile(r"^\s*⏺\s+(?P<tool>[A-Za-z][\w]*)\((?P<args>.*)\)\s*$")
_THINKING_RE = re.compile(r"^\s*[✻✽·✢*]\s*[A-Z][\w-]*…|\(esc to interrupt")
_WAITING_RE = re.compile(r"Do you want to proceed\?|^\s*❯\s*\d+\.")
_ERROR_RE = re.compile(r"\b(Error|ERROR)\b:|Traceback \(most recent call last\)")

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def parse_line(session_id: str, line: str) -> Event | None:
    clean = strip_ansi(line).rstrip("\r\n")
    if not clean.strip():
        return None

    match = _TOOL_CALL_RE.match(clean)
    if match:
        tool = match.group("tool")
        kind = "edit" if tool in _EDIT_TOOLS else "tool_call"
        return Event(session_id=session_id, kind=kind, detail=clean.strip())

    if _WAITING_RE.search(clean):
        return Event(session_id=session_id, kind="waiting", detail=clean.strip())

    if _ERROR_RE.search(clean):
        return Event(session_id=session_id, kind="error", detail=clean.strip())

    if _THINKING_RE.search(clean):
        return Event(session_id=session_id, kind="thinking", detail=clean.strip())

    return None


class ClaudeCodeParser:
    """Stateful line-buffering parser: feed raw PTY bytes, get back Events."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._buffer = ""

    def feed(self, data: bytes) -> list[Event]:
        self._buffer += data.decode("utf-8", errors="replace")
        events: list[Event] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            event = parse_line(self.session_id, line)
            if event is not None:
                events.append(event)
        return events
