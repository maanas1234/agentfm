"""Cross-platform PTY spawn/read/write wrapper.

Uses pywinpty on Windows and ptyprocess on Unix behind one interface so the
rest of the daemon never branches on platform.
"""

from __future__ import annotations

import shutil
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

        self._last_size: tuple[int, int] | None = None
        self.sync_winsize()

    def sync_winsize(self) -> None:
        """Match the PTY's size to our own host terminal. Without this the
        child's TUI redraws assuming whatever default size the PTY library
        picked (commonly 80x24), producing corrupted/overlapping output
        whenever the real terminal is a different size."""
        cols, rows = shutil.get_terminal_size(fallback=(80, 24))
        size = (rows, cols)
        if size == self._last_size:
            return
        try:
            self._proc.setwinsize(rows, cols)
        except Exception:
            return
        self._last_size = size

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
