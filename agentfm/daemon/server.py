"""Local FastAPI server: WebSocket broadcast of events + REST session list.

Runs entirely on localhost. The PTY-reading thread calls
`broadcaster.publish(event)` (thread-safe) to push events into whatever
asyncio loop the server is running on; connected dashboard clients receive
them over `/ws`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from agentfm.daemon.events import Event

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class Broadcaster:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.sessions: dict[str, dict] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def publish(self, event: Event) -> None:
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.publish_event_async(event), self.loop)

    async def publish_event_async(self, event: Event) -> None:
        state = self.sessions.setdefault(event.session_id, {"status": "active"})
        state["status"] = "waiting" if event.kind == "waiting" else (
            "error" if event.kind == "error" else "active"
        )

        payload = json.dumps(
            {
                "type": "event",
                "session_id": event.session_id,
                "kind": event.kind,
                "detail": event.detail,
                "ts": event.ts,
            }
        )
        await self._broadcast(payload)

    def publish_narration(self, session_id: str, text: str, audio: bytes | None) -> None:
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self.publish_narration_async(session_id, text, audio), self.loop
        )

    async def publish_narration_async(
        self, session_id: str, text: str, audio: bytes | None
    ) -> None:
        payload = json.dumps(
            {
                "type": "narration",
                "session_id": session_id,
                "text": text,
                "audio_b64": base64.b64encode(audio).decode("ascii") if audio else None,
            }
        )
        await self._broadcast(payload)

    async def _broadcast(self, payload: str) -> None:
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self.connections -= dead


broadcaster = Broadcaster()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    broadcaster.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(lifespan=_lifespan)


@app.get("/api/sessions")
def get_sessions() -> dict:
    return broadcaster.sessions


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    broadcaster.connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.connections.discard(websocket)


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


def start_server_in_thread(host: str = "127.0.0.1", port: int = 8765) -> threading.Thread:
    def _run() -> None:
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        asyncio.run(server.serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
