"""Pipeline orchestrator — runs stages in order, logs results."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader
from pipeline.logger import ProgressLogger
from pipeline.stages.model_tuning import ModelTuningStage
from pipeline.stages.visualization import VisualizationStage
from pipeline.stages.paper_writing import PaperWritingStage
from pipeline.stages.humanizer import HumanizerStage
from pipeline.stages.cloud_upload import CloudUploadStage

_ORDERED_STAGES: list[BaseStage] = [
    ModelTuningStage(),
    VisualizationStage(),
    PaperWritingStage(),
    HumanizerStage(),
    CloudUploadStage(),
]

_STAGE_MAP: dict[str, BaseStage] = {s.name: s for s in _ORDERED_STAGES}


class PipelineOrchestrator:
    """Run pipeline stages in order, honouring caching and timeouts."""

    def __init__(self, config: ConfigLoader, force: bool = False) -> None:
        self._config = config
        self._force = force
        self._cache = CacheManager(config.repo_root)
        self._logger = ProgressLogger(config.repo_root / "pipeline.log")

    def run(self, stages: Optional[list[str]] = None) -> int:
        """Execute the pipeline.

        Parameters
        ----------
        stages:
            Optional list of stage names to run.  When ``None``, all
            stages in ``_ORDERED_STAGES`` are executed in order.

        Returns
        -------
        int
            ``0`` if all stages completed or were skipped, ``1`` if any
            stage failed or timed out.
        """
        if stages is None:
            stage_list = _ORDERED_STAGES
        else:
            unknown = [s for s in stages if s not in _STAGE_MAP]
            if unknown:
                raise ValueError(f"Unknown stage(s): {unknown!r}")
            stage_list = [_STAGE_MAP[s] for s in stages]

        results: list[StageResult] = []
        pipeline_start = time.monotonic()

        for stage in stage_list:
            self._logger.log_message(stage.name, "INFO", "Starting stage.")
            result = stage.run(self._config, self._cache, force=self._force)
            self._logger.log(result)
            results.append(result)

        total_elapsed = time.monotonic() - pipeline_start
        self._print_summary(results, total_elapsed)

        bad_statuses = {StageStatus.FAILED, StageStatus.TIMEOUT}
        has_failure = any(r.status in bad_statuses for r in results)
        return 1 if has_failure else 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _print_summary(results: list[StageResult], total_elapsed: float) -> None:
        _STATUS_ICONS = {
            StageStatus.COMPLETED: "✓",
            StageStatus.SKIPPED: "–",
            StageStatus.TIMEOUT: "⏱",
            StageStatus.FAILED: "✗",
        }
        col_w = 28
        print("\n" + "─" * 56)
        print(f"{'Stage':<{col_w}} {'Status':<12} {'Elapsed':>10}")
        print("─" * 56)
        for r in results:
            icon = _STATUS_ICONS.get(r.status, "?")
            label = f"{icon} {r.status.value}"
            elapsed = f"{r.elapsed_seconds:.1f}s"
            print(f"{r.stage:<{col_w}} {label:<12} {elapsed:>10}")
            if r.message:
                print(f"  {'':>{col_w}} {r.message}")
        print("─" * 56)
        print(f"{'Total':.<{col_w}} {total_elapsed:.1f}s")
        print("─" * 56 + "\n")
