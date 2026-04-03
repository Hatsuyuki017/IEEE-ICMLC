"""Structured progress logger for the GBM research automation pipeline.

Writes newline-delimited JSON records to ``pipeline.log`` so that the
user can review execution status after reconnecting to the machine.

:class:`ReadmeLogger` additionally appends a human-readable markdown
section to ``README.md`` after each stage, satisfying the requirement
that all actual execution is recorded in README.md.
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


_STATUS_ICONS = {
    "completed": "✓",
    "failed": "✗",
    "timeout": "⏱",
    "skipped": "–",
}


class ReadmeLogger:
    """Append structured stage records to ``README.md`` as markdown.

    Each call to :meth:`log` appends a fenced section that records the
    stage name, execution timestamp, status, elapsed time, any message,
    and the list of produced artifacts.  This satisfies the requirement
    that *all actual execution* is recorded in ``README.md``.
    """

    def __init__(self, readme_path: Path) -> None:
        self._readme_path = readme_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(self, result: "StageResult") -> None:
        """Append a markdown record for *result* to README.md."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        icon = _STATUS_ICONS.get(result.status.value, "?")
        lines = [
            "",
            f"## Stage `{result.stage}` — {icon} {result.status.value.upper()}",
            f"_Recorded: {timestamp}_",
            "",
            f"- **Status**: {result.status.value}",
            f"- **Elapsed**: {result.elapsed_seconds:.1f}s",
        ]
        if result.message:
            lines.append(f"- **Message**: {result.message}")
        if result.artifacts:
            lines.append("- **Artifacts**:")
            for artifact in result.artifacts:
                lines.append(f"  - `{artifact}`")
        gate_passed = result.status.value == "completed"
        lines.append(
            f"- **Gate**: {'PASSED' if gate_passed else 'FAILED — pipeline halted'}"
        )
        lines.append("")
        with open(self._readme_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
