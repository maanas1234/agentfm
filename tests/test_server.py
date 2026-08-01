from fastapi.testclient import TestClient

from agentfm.daemon.events import Event
from agentfm.daemon.server import app, broadcaster, detect_audio_mime


def test_websocket_receives_published_event():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            broadcaster.publish(Event(session_id="s1", kind="tool_call", detail="⏺ Read(foo.py)"))
            message = ws.receive_json()

        assert message["session_id"] == "s1"
        assert message["kind"] == "tool_call"
        assert "Read(foo.py)" in message["detail"]


def test_sessions_endpoint_reflects_latest_status():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            broadcaster.publish(Event(session_id="s2", kind="waiting", detail="Do you want to proceed?"))
            ws.receive_json()

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json()["s2"]["status"] == "waiting"


def test_detect_audio_mime_identifies_wav():
    assert detect_audio_mime(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio/wav"


def test_detect_audio_mime_identifies_mp3_variants():
    assert detect_audio_mime(b"ID3\x03\x00\x00\x00") == "audio/mpeg"
    assert detect_audio_mime(b"\xff\xfb\x90\x00") == "audio/mpeg"


def test_detect_audio_mime_identifies_ogg():
    assert detect_audio_mime(b"OggS\x00\x02\x00\x00") == "audio/ogg"


def test_detect_audio_mime_defaults_to_mpeg_for_unknown():
    assert detect_audio_mime(b"\x00\x01\x02\x03") == "audio/mpeg"


def test_narration_broadcast_includes_detected_mime():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            broadcaster.publish_narration("s3", "hello", b"RIFF\x00\x00\x00\x00WAVEfmt ")
            message = ws.receive_json()

    assert message["audio_mime"] == "audio/wav"
