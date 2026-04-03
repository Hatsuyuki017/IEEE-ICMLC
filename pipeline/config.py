"""Configuration loader for the GBM research automation pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when a required configuration key is missing or invalid."""


_REQUIRED_KEYS = [
    "data_paths",
    "outputs_dir",
    "figures_dir",
    "sections_dir",
    "timeout_seconds",
    "skills",
    "cloud",
]


class ConfigLoader:
    """Load and validate ``pipeline_config.yaml``."""

    def __init__(self, config_path: str | Path) -> None:
        self._path = Path(config_path).resolve()
        self._repo_root = self._path.parent
        with open(self._path, "r", encoding="utf-8") as fh:
            self._data: dict[str, Any] = yaml.safe_load(fh) or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`ConfigError` if any required top-level key is missing."""
        for key in _REQUIRED_KEYS:
            if key not in self._data:
                raise ConfigError(
                    f"Required configuration key '{key}' is missing from {self._path}"
                )

    def get(self, key: str, default: Any = None) -> Any:
        """Return a configuration value, supporting dot-notation for nesting.

        Examples::

            config.get("cloud.destination")
            config.get("timeout_seconds")
        """
        parts = key.split(".")
        node: Any = self._data
        for part in parts:
            if not isinstance(node, dict):
                return default
            node = node.get(part, default)
        return node

    def resolve_path(self, key: str) -> Path:
        """Return an absolute :class:`~pathlib.Path` for a path-valued config key.

        Relative paths are resolved against the repository root (the directory
        that contains ``pipeline_config.yaml``).
        """
        raw = self.get(key)
        if raw is None:
            raise ConfigError(f"Path key '{key}' not found in configuration.")
        p = Path(raw)
        if not p.is_absolute():
            p = self._repo_root / p
        return p.resolve()

    @property
    def repo_root(self) -> Path:
        """Absolute path of the repository root."""
        return self._repo_root

    @property
    def timeout_seconds(self) -> int:
        """Per-stage timeout in seconds (default 5400 = 90 min)."""
        return int(self.get("timeout_seconds", 5400))
