"""Incremental cache manager for the GBM research automation pipeline.

Stores SHA-256 checksums of input and output file sets in
``.pipeline_cache.json`` so that a stage can be skipped when its
inputs have not changed since the last successful run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


_CACHE_FILENAME = ".pipeline_cache.json"


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CacheManager:
    """Persist file checksums to support incremental stage skipping."""

    def __init__(self, repo_root: Path) -> None:
        self._cache_path = repo_root / _CACHE_FILENAME
        self._data: dict[str, dict[str, str]] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_inputs(self, stage_name: str, paths: Iterable[str | Path]) -> bool:
        """Return ``True`` if all *paths* match their cached checksums.

        A return value of ``True`` means the stage may be safely skipped.
        Returns ``False`` if any file is new, modified, or missing from cache.
        """
        cached = self._data.get(f"{stage_name}:inputs", {})
        for p in paths:
            p = Path(p)
            if not p.exists():
                return False
            digest = _sha256(p)
            if cached.get(str(p)) != digest:
                return False
        return bool(cached)

    def record_outputs(self, stage_name: str, paths: Iterable[str | Path]) -> None:
        """Record checksums of *paths* as the outputs of *stage_name*.

        These checksums are also used as the *inputs* key for downstream
        stages so that an unchanged set of outputs signals a skip.
        """
        checksums: dict[str, str] = {}
        for p in paths:
            p = Path(p)
            if p.exists():
                checksums[str(p)] = _sha256(p)
        self._data[f"{stage_name}:inputs"] = checksums
        self._save()

    def record_inputs(self, stage_name: str, paths: Iterable[str | Path]) -> None:
        """Record checksums of *paths* as the current inputs for *stage_name*."""
        checksums: dict[str, str] = {}
        for p in paths:
            p = Path(p)
            if p.exists():
                checksums[str(p)] = _sha256(p)
        self._data[f"{stage_name}:inputs"] = checksums
        self._save()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, dict[str, str]]:
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        with open(self._cache_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
