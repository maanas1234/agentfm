# agentfm

OSS, BYOK ambient observability for AI coding agents. Wraps Claude Code or
Codex CLI sessions in a PTY, turns their output into structured events, and
narrates progress/blockers as short spoken updates — using *your own*
LLM/TTS provider key. No hosted backend, no proxy, no telemetry.

## Install

```bash
pip install -e .
```

## Configure (BYOK)

Create `~/.agentfm/config.toml`:

```toml
[llm]
base_url = "https://your-provider/v1"   # OpenAI-compatible /chat/completions
api_key = "sk-..."
model = "your-model"

[tts]
enabled = true                           # omit/false -> falls back to local OS voice
base_url = "https://your-provider/v1"    # OpenAI-compatible /audio/speech
api_key = "sk-..."
voice = "nova"
```

If `[llm]` isn't configured, agentfm still passes your terminal through and
shows raw events on the dashboard — it just skips narration. If `[tts]` isn't
configured, narration text is spoken through your OS's built-in TTS voice
instead of a remote provider.

## Run

```bash
agentfm run -- claude
agentfm run -- codex
```

This starts a local dashboard (default `http://127.0.0.1:8765`) and passes
your terminal straight through — the CLI stays fully interactive. Open the
dashboard to see live session status, the event timeline, and hear narration
as it's generated.

Flags:
- `--port PORT` — dashboard port (default 8765)
- `--no-server` — skip the dashboard, just tee raw output to
  `~/.agentfm/logs/<session_id>.log`

## Architecture

```
agentfm/
  daemon/
    pty_wrapper.py   # cross-platform PTY spawn/read/write
    events.py        # shared Event schema
    config.py        # ~/.agentfm/config.toml loader
    narrator.py       # batches events -> BYOK LLM summary
    tts.py            # summary -> BYOK TTS audio, or local OS voice fallback
    pipeline.py       # wires batching + narration + TTS + broadcast together
    server.py         # FastAPI + WebSocket dashboard backend
  parsers/
    claude_code.py    # Claude Code CLI output -> Events
    codex.py          # Codex CLI output -> Events
  web/                # static dashboard (vanilla JS, no build step)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
