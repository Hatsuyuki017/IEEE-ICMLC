"""Humanizer stage — removes AI writing traces from LaTeX section files."""

from __future__ import annotations

import difflib
import shutil
import time
from pathlib import Path

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader


class HumanizerStage(BaseStage):
    """Post-process section files via the ``humanizer`` skill CLI."""

    @property
    def name(self) -> str:
        return "humanizer"

    def _should_skip(self, config: ConfigLoader, cache: CacheManager) -> bool:
        sections_dir = config.resolve_path("sections_dir")
        input_paths = list(sections_dir.glob("*.tex"))
        return cache.check_inputs(self.name, input_paths)

    def _run(self, config: ConfigLoader) -> StageResult:
        start = time.monotonic()
        skill_cmd = config.get("skills.humanizer", "humanizer")
        sections_dir = config.resolve_path("sections_dir")
        humanized_dir = config.resolve_path("outputs_dir") / "humanized"
        humanized_dir.mkdir(parents=True, exist_ok=True)

        section_files = sorted(sections_dir.glob("*.tex"))
        if not section_files:
            return StageResult(
                stage=self.name,
                status=StageStatus.FAILED,
                elapsed_seconds=time.monotonic() - start,
                message=f"No .tex files found in {sections_dir}",
            )

        artifacts = []
        warnings = []

        for src in section_files:
            dest = humanized_dir / src.name
            cmd = [
                skill_cmd,
                "--input", str(src),
                "--output", str(dest),
            ]
            try:
                self.run_subprocess(cmd)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{src.name}: skill error ({exc}); using original.")
                shutil.copy2(src, dest)
                continue

            # Guard against empty / unchanged output.
            if not dest.exists() or dest.stat().st_size == 0:
                warnings.append(
                    f"{src.name}: humanizer returned empty output; using original."
                )
                shutil.copy2(src, dest)
            else:
                artifacts.append(str(dest))

        # Produce unified diff report.
        diff_lines: list[str] = []
        for src in section_files:
            dest = humanized_dir / src.name
            if dest.exists():
                original = src.read_text(encoding="utf-8").splitlines(keepends=True)
                humanized = dest.read_text(encoding="utf-8").splitlines(keepends=True)
                diff = list(
                    difflib.unified_diff(
                        original,
                        humanized,
                        fromfile=f"a/{src.name}",
                        tofile=f"b/{src.name}",
                    )
                )
                diff_lines.extend(diff)

        diff_path = humanized_dir / "changes.diff"
        diff_path.write_text("".join(diff_lines), encoding="utf-8")
        artifacts.append(str(diff_path))

        msg = " | ".join(warnings) if warnings else ""
        return StageResult(
            stage=self.name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=time.monotonic() - start,
            message=msg,
            artifacts=artifacts,
        )
