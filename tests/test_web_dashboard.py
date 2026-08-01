from fastapi.testclient import TestClient

from agentfm.daemon.server import app


def test_index_html_served_at_root():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Agent FM" in resp.text
        assert "dashboard.js" in resp.text


def test_dashboard_js_served():
    with TestClient(app) as client:
        resp = client.get("/dashboard.js")
        assert resp.status_code == 200
        assert "player.js" in resp.text


def test_player_js_served():
    with TestClient(app) as client:
        resp = client.get("/player.js")
        assert resp.status_code == 200
        assert "AudioQueue" in resp.text


def test_api_routes_not_shadowed_by_static_mount():
    with TestClient(app) as client:
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
