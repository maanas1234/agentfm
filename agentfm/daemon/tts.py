"""Text -> speech. BYOK OpenAI-compatible /audio/speech endpoint when
configured, otherwise a local OS-voice fallback that needs no key at all.
"""

from __future__ import annotations

import sys

import httpx

from agentfm.daemon.config import TTSConfig


def should_use_remote(config: TTSConfig) -> bool:
    return bool(config.enabled and config.base_url and config.api_key)


async def synthesize(
    config: TTSConfig, text: str, client: httpx.AsyncClient | None = None
) -> bytes:
    """Calls the user's BYOK TTS endpoint directly and returns raw audio bytes."""
    if not text:
        return b""

    payload = {"model": config.model, "input": text}
    if config.voice:
        payload["voice"] = config.voice
    headers = {"Authorization": f"Bearer {config.api_key}"}
    url = f"{config.base_url.rstrip('/')}/audio/speech"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content
    finally:
        if owns_client:
            await client.aclose()


def speak_local(text: str) -> None:
    """No-key fallback: speaks through the OS's built-in TTS voice.

    Runs on a worker thread via run_in_executor. pyttsx3's SAPI5 backend on
    Windows goes through comtypes, which requires COM to be initialized on
    whichever thread calls it -- worker threads never do that by default.
    """
    if not text:
        return

    if sys.platform == "win32":
        import pythoncom

        pythoncom.CoInitialize()
        try:
            _speak(text)
        finally:
            pythoncom.CoUninitialize()
    else:
        _speak(text)


def _speak(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
