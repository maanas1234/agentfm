"""Parse raw OpenAI Codex CLI output into structured Events.

Codex renders each action as a `• Verb ...` bullet line (`• Reading foo.py`,
`• Running command: npm test`, `• Editing bar.py`), approval prompts as
`Allow this command? (y/n)`, and a spinner line while it's working. This
module turns that text stream into Event objects, mirroring
`agentfm.parsers.claude_code`.
"""

from __future__ import annotations

import re

from agentfm.daemon.events import Event
from agentfm.parsers.ansi import strip_ansi

_BULLET_RE = re.compile(r"^\s*•\s*(?P<verb>[A-Za-z][\w]*)\b(?P<rest>.*)$")
_THINKING_RE = re.compile(r"^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]|Codex is thinking", re.IGNORECASE)
_WAITING_RE = re.compile(r"Allow this command\?|\(y/n\)|Approve\?", re.IGNORECASE)
_ERROR_RE = re.compile(r"\b(Error|ERROR)\b:|Traceback \(most recent call last\)")

_EDIT_VERBS = {"Editing", "Writing", "Applying"}


def parse_line(session_id: str, line: str) -> Event | None:
    clean = strip_ansi(line).rstrip("\r\n")
    if not clean.strip():
        return None

    match = _BULLET_RE.match(clean)
    if match:
        verb = match.group("verb")
        kind = "edit" if verb in _EDIT_VERBS else "tool_call"
        return Event(session_id=session_id, kind=kind, detail=clean.strip())

    if _WAITING_RE.search(clean):
        return Event(session_id=session_id, kind="waiting", detail=clean.strip())

    if _ERROR_RE.search(clean):
        return Event(session_id=session_id, kind="error", detail=clean.strip())

    if _THINKING_RE.match(clean):
        return Event(session_id=session_id, kind="thinking", detail=clean.strip())

    return None


class CodexParser:
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
