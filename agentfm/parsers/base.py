"""Shared line-buffering logic for CLI output parsers.

Real terminal streams use bare `\\r` (carriage return, no linefeed) for
in-place redraws -- a captured live Claude Code session had zero `\\n`
characters at all, only `\\r`. Splitting on `\\n` alone means the entire
stream is treated as one unsplit blob and no line-anchored pattern ever
matches, so this splits on either.
"""

from __future__ import annotations

import re
from typing import Callable

from agentfm.daemon.events import Event

_LINE_SPLIT_RE = re.compile(r"[\r\n]")

ParseLineFn = Callable[[str, str], "Event | None"]


class LineBufferedParser:
    def __init__(self, session_id: str, parse_line: ParseLineFn):
        self.session_id = session_id
        self._parse_line = parse_line
        self._buffer = ""

    def feed(self, data: bytes) -> list[Event]:
        self._buffer += data.decode("utf-8", errors="replace")
        events: list[Event] = []
        while True:
            match = _LINE_SPLIT_RE.search(self._buffer)
            if not match:
                break
            line = self._buffer[: match.start()]
            self._buffer = self._buffer[match.end() :]
            event = self._parse_line(self.session_id, line)
            if event is not None:
                events.append(event)
        return events
