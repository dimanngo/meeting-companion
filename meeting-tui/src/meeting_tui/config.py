"""Configuration loading with layered precedence: CLI > env > config file > defaults."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "meeting-tui"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_OUTPUT_DIR = Path.home() / "meeting-transcripts"


@dataclass
class AudioConfig:
    device: int | str | None = None
    sample_rate: int = 16000
    channels: int = 1
    block_duration_ms: int = 30  # Duration of each audio block in ms


@dataclass
class VADConfig:
    threshold: float = 0.5
    min_speech_frames: int = 6  # Consecutive frames above threshold to start speech
    min_silence_frames: int = 30  # Consecutive frames below threshold to end speech
    frame_duration_ms: int = 30


@dataclass
class TranscriptionConfig:
    model_size: str = "base"
    language: str | None = None  # None = auto-detect
    compute_type: str = "int8"
    beam_size: int = 5


@dataclass
class LLMConfig:
    backend: str = "ollama"  # "ollama", "openai", "gemini"
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-preview"
    gemini_thinking_level: str = "low"  # minimal, low, medium, high


@dataclass
class PersistenceConfig:
    output_dir: str = str(DEFAULT_OUTPUT_DIR)
    title: str = "meeting"


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)


def _deep_update(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _load_toml(path: Path) -> dict[str, Any]:
    """Load config from TOML file if it exists."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_env_overrides() -> dict[str, Any]:
    """Load configuration from environment variables."""
    overrides: dict[str, Any] = {}

    env_mapping = {
        "MEETING_TUI_LLM_BACKEND": ("llm", "backend"),
        "MEETING_TUI_OLLAMA_BASE_URL": ("llm", "ollama_base_url"),
        "MEETING_TUI_OLLAMA_MODEL": ("llm", "ollama_model"),
        "OPENAI_API_KEY": ("llm", "openai_api_key"),
        "MEETING_TUI_OPENAI_MODEL": ("llm", "openai_model"),
        "GEMINI_API_KEY": ("llm", "gemini_api_key"),
        "MEETING_TUI_GEMINI_MODEL": ("llm", "gemini_model"),
        "MEETING_TUI_OUTPUT_DIR": ("persistence", "output_dir"),
        "MEETING_TUI_WHISPER_MODEL": ("transcription", "model_size"),
        "MEETING_TUI_AUDIO_DEVICE": ("audio", "device"),
    }

    for env_var, (section, key) in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            overrides.setdefault(section, {})[key] = value

    return overrides


def _apply_dict_to_config(config: AppConfig, data: dict[str, Any]) -> None:
    """Apply a dict of config values to the AppConfig dataclass."""
    section_map = {
        "audio": config.audio,
        "vad": config.vad,
        "transcription": config.transcription,
        "llm": config.llm,
        "persistence": config.persistence,
    }
    for section_name, section_obj in section_map.items():
        if section_name in data:
            for key, value in data[section_name].items():
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)


def load_config(
    config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """Load configuration with precedence: CLI > env > config file > defaults."""
    config = AppConfig()

    # Layer 1: config file
    toml_path = config_path or DEFAULT_CONFIG_PATH
    toml_data = _load_toml(toml_path)
    _apply_dict_to_config(config, toml_data)

    # Layer 2: environment variables
    env_data = _load_env_overrides()
    _apply_dict_to_config(config, env_data)

    # Layer 3: CLI overrides
    if cli_overrides:
        _apply_dict_to_config(config, cli_overrides)

    return config
