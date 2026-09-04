"""A deliberately small JSON cache for API price suggestions."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class PriceCache:
    def __init__(self, path: Path, enabled: bool = True, refresh: bool = False) -> None:
        self.path = path
        self.enabled = enabled
        self.refresh = refresh
        self.data: dict[str, dict[str, dict[str, Any]]] = {}
        if enabled and not refresh:
            self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                self.data = parsed
            else:
                LOGGER.warning("Cache ignorata: formato non valido.")
        except (OSError, json.JSONDecodeError) as error:
            LOGGER.warning("Cache ignorata: %s", error)

    def get(self, release_id: str) -> dict[str, dict[str, Any]] | None:
        if not self.enabled or self.refresh:
            return None
        value = self.data.get(release_id)
        return value if isinstance(value, dict) else None

    def set(self, release_id: str, suggestions: dict[str, dict[str, Any]]) -> None:
        if not self.enabled:
            return
        self.data[release_id] = suggestions
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(self.data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as error:
            LOGGER.warning("Impossibile salvare la cache: %s", error)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
