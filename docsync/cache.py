"""Simple file-based cache for DocSync."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class FileCache:
    def __init__(self, path: str | Path = ".docsync-cache.json"):
        self.path = Path(path)
        self._data: dict[str, Any] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._data = {}

    @staticmethod
    def key_for(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.path.write_text(json.dumps(self._data), encoding="utf-8")
