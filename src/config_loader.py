from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any


class ConfigValidationError(Exception):
    pass


class Config:
    """Wrapper around a parsed YAML dict.

    Supports:
    - Dot-attribute access:  cfg.ollama.base_url
    - Key-path get:          cfg.get("ollama.base_url", default=...)
    """

    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, Config(value) if isinstance(value, dict) else value)

    def get(self, key_path: str, default: Any = None) -> Any:
        parts = key_path.split(".")
        node = self
        for part in parts:
            if not isinstance(node, Config) or not hasattr(node, part):
                return default
            node = getattr(node, part)
        return node

    def __repr__(self) -> str:
        return f"Config({self.__dict__})"


def load_config(
    path: str | Path,
    required_keys: list[str] | None = None,
) -> Config:
    """Load config from a YAML file.

    Args:
        path: Path to the YAML file.
        required_keys: List of dot-separated key paths that must exist and be
                       non-None (e.g. ["ollama.base_url", "tts.voice"]).

    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigValidationError: If any required key is missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = Config(data)

    if required_keys:
        missing = [k for k in required_keys if cfg.get(k) is None]
        if missing:
            raise ConfigValidationError(
                f"Missing required config keys: {', '.join(missing)}"
            )

    return cfg
