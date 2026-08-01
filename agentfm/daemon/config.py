"""Reads ~/.agentfm/config.toml — BYOK provider settings, nothing else."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

CONFIG_PATH = Path.home() / ".agentfm" / "config.toml"


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class TTSConfig:
    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = "tts-1"
    voice: str = ""


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)


_LLM_FIELDS = {"base_url", "api_key", "model"}
_TTS_FIELDS = {"enabled", "base_url", "api_key", "model", "voice"}


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    llm_data = {k: v for k, v in data.get("llm", {}).items() if k in _LLM_FIELDS}
    tts_data = {k: v for k, v in data.get("tts", {}).items() if k in _TTS_FIELDS}

    return AppConfig(llm=LLMConfig(**llm_data), tts=TTSConfig(**tts_data))
