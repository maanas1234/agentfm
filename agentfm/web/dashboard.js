import { AudioQueue } from "/player.js";

const sessions = new Map();
let focusedSession = null;

const queueStatusEl = document.getElementById("queue-status");
const audioQueue = new AudioQueue((queued, playing) => {
  queueStatusEl.textContent = playing ? `playing (${queued} queued)` : `${queued} queued`;
});

function statusClass(status) {
  if (status === "waiting") return "waiting";
  if (status === "error") return "error";
  return "active-status";
}

function ensureSession(id) {
  if (!sessions.has(id)) {
    sessions.set(id, { status: "active", events: [] });
  }
  return sessions.get(id);
}

function handleMessage(msg) {
  if (msg.type === "event") {
    const s = ensureSession(msg.session_id);
    s.status = msg.kind === "waiting" ? "waiting" : msg.kind === "error" ? "error" : "active";
    s.events.push({ kind: msg.kind, text: msg.detail, ts: msg.ts });
  } else if (msg.type === "narration") {
    const s = ensureSession(msg.session_id);
    s.events.push({ kind: "narration", text: msg.text, ts: Date.now() / 1000 });
    if (msg.audio_b64) audioQueue.enqueue(msg.audio_b64);
  }
  render();
}

function render() {
  renderSidebar();
  renderTimeline();
}

function renderSidebar() {
  const el = document.getElementById("sessions");
  el.innerHTML = "";

  const globalItem = document.createElement("div");
  globalItem.className = "session-item" + (focusedSession === null ? " active" : "");
  globalItem.innerHTML = `<span class="dot active-status"></span> Global Mix`;
  globalItem.onclick = () => {
    focusedSession = null;
    render();
  };
  el.appendChild(globalItem);

  for (const [id, s] of sessions) {
    const item = document.createElement("div");
    item.className =
      "session-item " + statusClass(s.status) + (focusedSession === id ? " active" : "");
    item.innerHTML = `<span class="dot"></span> ${id}`;
    item.onclick = () => {
      focusedSession = id;
      render();
    };
    el.appendChild(item);
  }
}

function renderTimeline() {
  const el = document.getElementById("timeline");
  const ids = focusedSession ? [focusedSession] : [...sessions.keys()];
  const combined = ids
    .flatMap((id) => (sessions.get(id)?.events || []).map((e) => ({ ...e, session_id: id })))
    .sort((a, b) => a.ts - b.ts)
    .slice(-200);

  el.innerHTML = "";
  for (const e of combined) {
    const row = document.createElement("div");
    row.className = `entry ${e.kind}`;
    row.textContent = `[${e.session_id}] ${e.text}`;
    el.appendChild(row);
  }
  el.scrollTop = el.scrollHeight;
}

document.getElementById("mute").addEventListener("click", (e) => {
  const wasMuted = e.target.dataset.muted === "true";
  audioQueue.setMuted(!wasMuted);
  e.target.dataset.muted = (!wasMuted).toString();
  e.target.textContent = wasMuted ? "Mute" : "Unmute";
});

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
  ws.onclose = () => setTimeout(connect, 1000);
}

connect();
