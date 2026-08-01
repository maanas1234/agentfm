import re

_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_COLLAPSE_SPACES_RE = re.compile(r" {2,}")


def strip_ansi(text: str) -> str:
    """Strip CSI/OSC escape sequences.

    Real terminal UIs often use cursor-forward movement (part of the CSI
    family) to lay out visual whitespace instead of literal space characters
    -- stripping those to "" glues adjacent words together (observed live:
    "Running1shellcommand"). Replacing with a space instead, then collapsing
    doubled-up spaces, keeps words separated at the cost of occasional
    harmless extra whitespace.
    """
    text = _OSC_RE.sub(" ", text)
    text = _CSI_RE.sub(" ", text)
    return _COLLAPSE_SPACES_RE.sub(" ", text)
