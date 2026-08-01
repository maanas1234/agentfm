from pathlib import Path

from agentfm.parsers.codex import CodexParser

FIXTURE = Path(__file__).parent / "fixtures" / "codex_sample.log"


def test_parses_full_transcript_into_expected_event_sequence():
    parser = CodexParser(session_id="test-session")
    data = FIXTURE.read_bytes()

    events = parser.feed(data)

    kinds = [e.kind for e in events]
    assert kinds == ["thinking", "tool_call", "edit", "tool_call", "error", "waiting"]
    assert all(e.session_id == "test-session" for e in events)


def test_reading_bullet_classified_as_tool_call():
    parser = CodexParser(session_id="s1")
    events = parser.feed("• Reading agentfm/daemon/__main__.py\n".encode())
    assert len(events) == 1
    assert events[0].kind == "tool_call"
    assert "Reading agentfm/daemon/__main__.py" in events[0].detail


def test_editing_bullet_classified_as_edit_kind():
    parser = CodexParser(session_id="s1")
    events = parser.feed("• Editing foo.py\n".encode())
    assert events[0].kind == "edit"


def test_blank_lines_produce_no_events():
    parser = CodexParser(session_id="s1")
    events = parser.feed(b"\n\n   \n")
    assert events == []


def test_incremental_feed_across_chunk_boundaries():
    parser = CodexParser(session_id="s1")
    first = parser.feed("Allow this ".encode())
    assert first == []
    second = parser.feed("command? (y/n)\n".encode())
    assert len(second) == 1
    assert second[0].kind == "waiting"
