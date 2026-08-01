"""Cross-platform PTY spawn/read/write wrapper.

Uses pywinpty on Windows and ptyprocess on Unix behind one interface so the
rest of the daemon never branches on platform.
"""

from __future__ import annotations

import sys


class PtySession:
    def __init__(self, cmd: list[str]):
        self._cmd = cmd
        if sys.platform == "win32":
            import winpty

            self._proc = winpty.PtyProcess.spawn(cmd)
        else:
            import ptyprocess

            self._proc = ptyprocess.PtyProcess.spawn(cmd)

    def read(self, size: int = 4096) -> bytes:
        try:
            data = self._proc.read(size)
        except EOFError:
            return b""
        if isinstance(data, str):
            return data.encode("utf-8", errors="replace")
        return data

    def write(self, data: bytes) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        self._proc.write(data)

    def isalive(self) -> bool:
        return bool(self._proc.isalive())

    def close(self) -> None:
        self._proc.close()
