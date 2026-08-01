from agentfm.parsers.opencode import OpenCodeParser


def test_reading_bullet_classified_as_tool_call():
    parser = OpenCodeParser(session_id="s1")
    events = parser.feed("• Reading agentfm/daemon/__main__.py\n".encode())
    assert len(events) == 1
    assert events[0].kind == "tool_call"


def test_editing_bullet_classified_as_edit_kind():
    parser = OpenCodeParser(session_id="s1")
    events = parser.feed("• Editing foo.py\n".encode())
    assert events[0].kind == "edit"


def test_waiting_prompt_detected():
    parser = OpenCodeParser(session_id="s1")
    events = parser.feed("Proceed? (y/n)\n".encode())
    assert events[0].kind == "waiting"


def test_error_line_detected():
    parser = OpenCodeParser(session_id="s1")
    events = parser.feed("Error: build failed\n".encode())
    assert events[0].kind == "error"


def test_blank_lines_produce_no_events():
    parser = OpenCodeParser(session_id="s1")
    assert parser.feed(b"\n\n   \n") == []


def test_incremental_feed_across_chunk_boundaries():
    parser = OpenCodeParser(session_id="s1")
    assert parser.feed("Confirm".encode()) == []
    events = parser.feed("? (y/n)\n".encode())
    assert len(events) == 1
    assert events[0].kind == "waiting"
