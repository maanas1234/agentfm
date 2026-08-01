from fastapi.testclient import TestClient

from agentfm.daemon.events import Event
from agentfm.daemon.server import app, broadcaster


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
