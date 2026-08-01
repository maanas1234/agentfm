"""agentfm run -- <cmd...>

Spawns <cmd> in a PTY, passes it through so the terminal stays fully
interactive, and tees raw output to a per-session debug log file under
~/.agentfm/logs/.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import uuid
from pathlib import Path

from agentfm.daemon.config import load_config
from agentfm.daemon.pipeline import NarrationPipeline
from agentfm.daemon.pty_wrapper import PtySession
from agentfm.daemon.server import broadcaster, start_server_in_thread
from agentfm.parsers.claude_code import ClaudeCodeParser
from agentfm.parsers.codex import CodexParser
from agentfm.parsers.opencode import OpenCodeParser

LOG_DIR = Path.home() / ".agentfm" / "logs"

_ParserT = ClaudeCodeParser | CodexParser | OpenCodeParser


def _select_parser(cmd: list[str], session_id: str) -> _ParserT:
    exe = Path(cmd[0]).stem.lower()
    if exe == "codex":
        return CodexParser(session_id=session_id)
    if exe == "opencode":
        return OpenCodeParser(session_id=session_id)
    return ClaudeCodeParser(session_id=session_id)


def _pump_output(
    session: PtySession,
    log_file,
    parser: _ParserT,
    pipeline: NarrationPipeline,
) -> None:
    while session.isalive():
        data = session.read()
        if not data:
            time.sleep(0.01)
            continue
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        log_file.write(data)
        log_file.flush()
        for event in parser.feed(data):
            broadcaster.publish(event)
            pipeline.on_event(event)


def _tick_pipeline(session: PtySession, pipeline: NarrationPipeline) -> None:
    while session.isalive():
        time.sleep(1.0)
        pipeline.check_timeouts(time.time())


def _pump_input_unix(session: PtySession) -> None:
    import os
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while session.isalive():
            data = os.read(fd, 1024)
            if not data:
                break
            session.write(data)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _pump_input_windows(session: PtySession) -> None:
    import msvcrt

    while session.isalive():
        if not msvcrt.kbhit():
            time.sleep(0.02)
            continue
        ch = msvcrt.getwch()
        session.write(ch.encode("utf-8", errors="replace"))


def _wait_no_input(session: PtySession) -> None:
    """No real TTY attached to our own stdin (piped/CI/background run) --
    nothing to forward, just block until the wrapped session exits."""
    while session.isalive():
        time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentfm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Wrap and observe an agent CLI session")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run, e.g. -- claude")
    run_parser.add_argument("--port", type=int, default=8765, help="Dashboard server port")
    run_parser.add_argument("--no-server", action="store_true", help="Skip starting the local dashboard server")

    args = parser.parse_args()

    if args.command == "run":
        cmd = args.cmd
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            parser.error("no command given, e.g. `agentfm run -- claude`")

        session_id = uuid.uuid4().hex[:8]
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{session_id}.log"

        if not args.no_server:
            start_server_in_thread(port=args.port)
            print(f"agentfm dashboard: http://127.0.0.1:{args.port}", file=sys.stderr)

        session = PtySession(cmd)
        parser_instance = _select_parser(cmd, session_id)
        pipeline = NarrationPipeline(load_config())

        with open(log_path, "wb") as log_file:
            output_thread = threading.Thread(
                target=_pump_output,
                args=(session, log_file, parser_instance, pipeline),
                daemon=True,
            )
            output_thread.start()

            ticker_thread = threading.Thread(
                target=_tick_pipeline, args=(session, pipeline), daemon=True
            )
            ticker_thread.start()

            if not sys.stdin.isatty():
                _wait_no_input(session)
            elif sys.platform == "win32":
                _pump_input_windows(session)
            else:
                _pump_input_unix(session)

            output_thread.join(timeout=1)
            ticker_thread.join(timeout=1)

        session.close()


if __name__ == "__main__":
    main()
