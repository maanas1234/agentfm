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
        "waiting",
        "waiting",
    ]
    assert all(e.session_id == "test-session" for e in events)


def test_tool_call_detail_captures_tool_and_args():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(b"\xe2\x8f\xba Read(agentfm/daemon/__main__.py)\n")
    assert len(events) == 1
    assert events[0].kind == "tool_call"
    assert "Read(agentfm/daemon/__main__.py)" in events[0].detail


def test_edit_tool_classified_as_edit_kind():
    parser = ClaudeCodeParser(session_id="s1")
    events = parser.feed(b"\xe2\x8f\xba Edit(foo.py)\n")
    assert events[0].kind == "edit"


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
