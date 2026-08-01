"""Parse raw Claude Code CLI output into structured Events.

Patterns here are based on a real captured session log (not guesswork):
Claude Code marks both in-progress tool calls and its own settled text
replies with `●` (`● Reading 1 file…`, `● agentfm: ...`), reports
failed commands as `● Exit <code>, ...`, shows a spinner while working with
a random whimsical verb each time (`✳ Fiddle-faddling… (esc to interrupt)`,
settling to `✳ Brewed for 12s` once done), and echoes the composed prompt
with a `❯` prefix (not a numbered permission menu, which uses `❯ 1. Yes`
same-line style).
"""

from __future__ import annotations

import re

from agentfm.daemon.events import Event
from agentfm.parsers.ansi import strip_ansi
from agentfm.parsers.base import LineBufferedParser

_BULLET_RE = re.compile(r"^\s*●\s*(?P<verb>[A-Z][a-zA-Z]*ing)\b(?P<rest>.*)$")
_EXIT_ERROR_RE = re.compile(r"^\s*●\s*Exit\s+\d+\s*,")
_THINKING_RE = re.compile(r"^\s*[✢✳✶✻✽·⠂⠐]\s*[A-Z]")
_WAITING_RE = re.compile(r"Do you want to proceed\?|^\s*❯\s*\d+\.")
_ERROR_RE = re.compile(r"\b(Error|ERROR)\b:|Traceback \(most recent call last\)")

_EDIT_VERBS = {"Writing", "Editing", "Applying"}


def parse_line(session_id: str, line: str) -> Event | None:
    clean = strip_ansi(line).rstrip("\r\n").strip()
    if not clean:
        return None

    if _EXIT_ERROR_RE.match(clean):
        return Event(session_id=session_id, kind="error", detail=clean)

    match = _BULLET_RE.match(clean)
    if match:
        verb = match.group("verb")
        kind = "edit" if verb in _EDIT_VERBS else "tool_call"
        return Event(session_id=session_id, kind=kind, detail=clean)

    if _WAITING_RE.search(clean):
        return Event(session_id=session_id, kind="waiting", detail=clean)

    if _ERROR_RE.search(clean):
        return Event(session_id=session_id, kind="error", detail=clean)

    if _THINKING_RE.match(clean):
        return Event(session_id=session_id, kind="thinking", detail=clean)

    return None


class ClaudeCodeParser(LineBufferedParser):
    def __init__(self, session_id: str):
        super().__init__(session_id, parse_line)
