"""Configuration loading for DocSync."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "docs_paths": ["docs", "README.md", "CHANGELOG.md"],
    "ignore": ["*.lock", "node_modules", ".git"],
    "threshold": 0.0,
    "provider": "openrouter",
    "model": "cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
    "base_url": "",
    "api_key": "",
    "api_key_env": "OPENROUTER_API_KEY",
}


@dataclass
class Config:
    docs_paths: list[str] = field(default_factory=lambda: list(DEFAULT_CONFIG["docs_paths"]))
    ignore: list[str] = field(default_factory=lambda: list(DEFAULT_CONFIG["ignore"]))
    threshold: float = 0.0
    provider: str = DEFAULT_CONFIG["provider"]
    model: str = DEFAULT_CONFIG["model"]
    base_url: str = DEFAULT_CONFIG["base_url"]
    api_key: str = DEFAULT_CONFIG["api_key"]
    api_key_env: str = DEFAULT_CONFIG["api_key_env"]

    @property
    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        return os.environ.get(self.api_key_env, "")


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from a YAML file, falling back to defaults."""
    if path is None:
        for candidate in (".docsync.yml", ".docsync.yaml", "docsync.yml"):
            if Path(candidate).exists():
                path = candidate
                break
    if path is None or not Path(path).exists():
        return Config()
    with open(path, encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}
    cfg = Config()
    for key in ("docs_paths", "ignore", "threshold", "provider", "model", "base_url", "api_key", "api_key_env"):
        if key in data:
            setattr(cfg, key, data[key])
    return cfg
