"""Structured progress logger for the GBM research automation pipeline.

Writes newline-delimited JSON records to ``pipeline.log`` so that the
user can review execution status after reconnecting to the machine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.base import StageResult


class ProgressLogger:
    """Append structured JSON log lines to ``pipeline.log``."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(self, result: "StageResult") -> None:
        """Write a :class:`~pipeline.base.StageResult` as a JSON record."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stage": result.stage,
            "status": result.status.value,
            "elapsed_seconds": round(result.elapsed_seconds, 2),
            "message": result.message,
            "artifacts": result.artifacts,
        }
        self._append(record)

    def log_message(self, stage: str, level: str, message: str) -> None:
        """Write a free-form log message for *stage*."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stage": stage,
            "level": level.upper(),
            "message": message,
        }
        self._append(record)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append(self, record: dict) -> None:
        with open(self._log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
