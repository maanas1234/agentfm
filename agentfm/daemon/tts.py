"""Text -> speech. BYOK OpenAI-compatible /audio/speech endpoint when
configured, otherwise a local OS-voice fallback that needs no key at all.
"""

from __future__ import annotations

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

    payload = {"model": "tts-1", "input": text, "voice": config.voice or "alloy"}
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
    """No-key fallback: speaks through the OS's built-in TTS voice."""
    if not text:
        return
    import pyttsx3

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
