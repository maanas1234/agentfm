"""Shared event schema consumed by narrator, server, and dashboard."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

EventKind = Literal["tool_call", "edit", "error", "waiting", "thinking", "idle"]


@dataclass
class Event:
    session_id: str
    kind: EventKind
    detail: str
    ts: float = field(default_factory=time.time)
