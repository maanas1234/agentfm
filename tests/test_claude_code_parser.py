from pathlib import Path

from agentfm.parsers.claude_code import ClaudeCodeParser

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_sample.log"


def test_parses_full_transcript_into_expected_event_sequence():
    parser = ClaudeCodeParser(session_id="test-session")
    data = FIXTURE.read_bytes()

    events = parser.feed(data)

    kinds = [e.kind for e in events]
    assert kinds == [
        "thinking",
        "tool_call",
        "edit",
        "tool_call",
        "error",
        "thinking",
        "waiting",
        "waiting",
    ]
    assert all(e.session_id == "test-session" for e in events)


def test_reading_bullet_classified_as_tool_call():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed("● Reading agentfm/daemon/__main__.py…\n".encode())
    assert len(events) == 1
    assert events[0].kind == "tool_call"
    assert "Reading agentfm/daemon/__main__.py" in events[0].detail


def test_writing_bullet_classified_as_edit_kind():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed("● Writing foo.py…\n".encode())
    assert events[0].kind == "edit"


def test_assistant_reply_text_is_not_misclassified_as_tool_call():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(
        "● agentfm: PTY wrapper for Claude Code/Codex CLI, BYOK narration+TTS.\n".encode()
    )
    assert events == []


def test_exit_error_detected():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(
        "● Exit 127, nonexistent-command: command not found.\n".encode()
    )
    assert len(events) == 1
    assert events[0].kind == "error"


def test_blank_lines_produce_no_events():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(b"\n\n   \n")
    assert events == []


def test_incremental_feed_across_chunk_boundaries():
    parser = ClaudeCodeParser(session_id="s1")
    first = parser.feed("Do you want to ".encode())
    assert first == []
    second = parser.feed("proceed?\n".encode())
    assert len(second) == 1
    assert second[0].kind == "waiting"


def test_whimsical_spinner_verb_detected_as_thinking():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(
        "✻ Fiddle-faddling… (esc to interrupt · 4s · ↑ 102 tokens)\n".encode()
    )
    assert len(events) == 1
    assert events[0].kind == "thinking"


def test_lines_separated_by_bare_carriage_return_are_split():
    """Real terminal redraws use bare \\r with no \\n at all."""
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed("● Reading a.py…\r● Running 1 shell command…\r".encode())
    assert [e.kind for e in events] == ["tool_call", "tool_call"]
