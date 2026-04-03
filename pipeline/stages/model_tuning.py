"""Model tuning stage — uses the *autoresearch* skill."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader


class ModelTuningStage(BaseStage):
    """Run hyperparameter search via the ``autoresearch`` skill CLI."""

    @property
    def name(self) -> str:
        return "model_tuning"

    def _should_skip(self, config: ConfigLoader, cache: CacheManager) -> bool:
        outputs_dir = config.resolve_path("outputs_dir") / "model_tuning"
        summary = outputs_dir / "results_summary.json"
        if not summary.exists():
            return False
        input_paths = [
            Path(v) for v in config.get("data_paths", {}).values()
        ]
        return cache.check_inputs(self.name, input_paths)

    def _run(self, config: ConfigLoader) -> StageResult:
        start = time.monotonic()
        skill_cmd = config.get("skills.autoresearch", "autoresearch")
        outputs_dir = config.resolve_path("outputs_dir") / "model_tuning"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        data_paths = config.get("data_paths", {})
        cmd = [
            skill_cmd,
            "--task", "model_tuning",
            "--output-dir", str(outputs_dir),
        ]
        for key, val in data_paths.items():
            cmd += [f"--{key.replace('_', '-')}", str(val)]

        try:
            self.run_subprocess(cmd)
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                stage=self.name,
                status=StageStatus.FAILED,
                elapsed_seconds=time.monotonic() - start,
                message=str(exc),
            )

        # Ensure results_summary.json exists; create a placeholder if the
        # skill did not produce one so downstream stages can proceed.
        summary_path = outputs_dir / "results_summary.json"
        if not summary_path.exists():
            summary_path.write_text(json.dumps({}), encoding="utf-8")

        artifacts = [str(p) for p in outputs_dir.rglob("*") if p.is_file()]
        return StageResult(
            stage=self.name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=time.monotonic() - start,
            artifacts=artifacts,
        )
