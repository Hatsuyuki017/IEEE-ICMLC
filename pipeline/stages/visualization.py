"""Visualization stage — uses the *academic-plotting* skill."""

from __future__ import annotations

import time
from pathlib import Path

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader

_REQUIRED_FIGURES = [
    "fig_umap_patients",
    "fig_kaplan_meier",
    "fig_v7_external_roc",
    "fig_v7_ablation_auc",
    "fig_volcano",
]


class VisualizationStage(BaseStage):
    """Regenerate publication figures via the ``academic-plotting`` skill CLI."""

    @property
    def name(self) -> str:
        return "visualization"

    def _should_skip(self, config: ConfigLoader, cache: CacheManager) -> bool:
        figures_dir = config.resolve_path("figures_dir")
        # Skip only when every required figure already exists and data is unchanged.
        for stem in _REQUIRED_FIGURES:
            if not (figures_dir / f"{stem}.pdf").exists():
                return False
            if not (figures_dir / f"{stem}.png").exists():
                return False
        input_paths = [
            Path(v) for v in config.get("data_paths", {}).values()
        ]
        return cache.check_inputs(self.name, input_paths)

    def _run(self, config: ConfigLoader) -> StageResult:
        start = time.monotonic()
        skill_cmd = config.get("skills.academic_plotting", "academic-plotting")
        figures_dir = config.resolve_path("figures_dir")
        figures_dir.mkdir(parents=True, exist_ok=True)

        results_summary = (
            config.resolve_path("outputs_dir") / "model_tuning" / "results_summary.json"
        )
        cmd = [
            skill_cmd,
            "--output-dir", str(figures_dir),
            "--results-json", str(results_summary),
        ]
        for key, val in config.get("data_paths", {}).items():
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

        missing = []
        for stem in _REQUIRED_FIGURES:
            for ext in (".pdf", ".png"):
                p = figures_dir / f"{stem}{ext}"
                if not p.exists():
                    missing.append(str(p))

        if missing:
            return StageResult(
                stage=self.name,
                status=StageStatus.FAILED,
                elapsed_seconds=time.monotonic() - start,
                message=f"Required figures missing after visualization: {missing}",
            )

        artifacts = [str(p) for p in figures_dir.rglob("*.pdf")]
        artifacts += [str(p) for p in figures_dir.rglob("*.png")]
        return StageResult(
            stage=self.name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=time.monotonic() - start,
            artifacts=artifacts,
        )
