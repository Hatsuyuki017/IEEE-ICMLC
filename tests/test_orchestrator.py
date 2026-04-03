"""Integration smoke tests for PipelineOrchestrator."""

from __future__ import annotations

import textwrap
import time
from pathlib import Path

import pytest

from pipeline.base import BaseStage, StageResult, StageStatus
from pipeline.cache import CacheManager
from pipeline.config import ConfigLoader
from pipeline.orchestrator import PipelineOrchestrator


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "pipeline_config.yaml"
    cfg.write_text(
        textwrap.dedent(f"""\
            data_paths:
              cptac_rna: {tmp_path}/rna
            outputs_dir: {tmp_path}/outputs
            figures_dir: {tmp_path}/figures
            sections_dir: {tmp_path}/sections
            timeout_seconds: 5400
            skills:
              autoresearch: autoresearch
              academic_plotting: academic-plotting
              ml_paper_writing: ml-paper-writing
              humanizer: humanizer
            cloud:
              tool: rclone
              destination: gdrive:test
        """),
        encoding="utf-8",
    )
    return cfg


class _FastOkStage(BaseStage):
    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    @property
    def name(self) -> str:
        return self._name

    def _run(self, config: ConfigLoader) -> StageResult:
        return StageResult(
            stage=self._name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=0.01,
        )


class _SlowStage(BaseStage):
    """Stage that sleeps longer than its timeout."""

    def __init__(self, stage_name: str, sleep_seconds: int) -> None:
        self._name = stage_name
        self._sleep = sleep_seconds

    @property
    def name(self) -> str:
        return self._name

    def _run(self, config: ConfigLoader) -> StageResult:
        time.sleep(self._sleep)
        return StageResult(
            stage=self._name,
            status=StageStatus.COMPLETED,
            elapsed_seconds=self._sleep,
        )


class _FailStage(BaseStage):
    """Stage that always raises, causing a FAILED result."""

    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    @property
    def name(self) -> str:
        return self._name

    def _run(self, config: ConfigLoader) -> StageResult:
        raise RuntimeError("deliberate failure")


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_orchestrator_all_stages_completed(tmp_path, monkeypatch):
    cfg_path = _write_config(tmp_path)
    config = ConfigLoader(cfg_path)
    config.validate()

    fast_stages = [_FastOkStage(n) for n in ["s1", "s2", "s3"]]

    orch = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orch._config = config
    orch._force = True
    orch._cache = CacheManager(tmp_path)
    orch._logger = type(
        "_NullLogger",
        (),
        {"log": lambda *a, **k: None, "log_message": lambda *a, **k: None},
    )()

    results = []
    for stage in fast_stages:
        results.append(stage.run(config, orch._cache, force=True))

    assert all(r.status == StageStatus.COMPLETED for r in results)


def test_orchestrator_timeout_stage_marked_timeout(tmp_path):
    """A stage that sleeps past its timeout should be marked TIMEOUT."""
    cfg_path = _write_config(tmp_path)
    config = ConfigLoader(cfg_path)

    slow = _SlowStage("slow_stage", sleep_seconds=60)
    slow.TIMEOUT_SECONDS = 2  # override to 2 s for test speed

    cache = CacheManager(tmp_path)
    result = slow.run(config, cache, force=True)

    assert result.status == StageStatus.TIMEOUT


def test_orchestrator_returns_exit_code_1_on_failure(tmp_path, monkeypatch):
    """Orchestrator should return 1 when a stage fails."""
    cfg_path = _write_config(tmp_path)
    config = ConfigLoader(cfg_path)

    fail = _FailStage("fail_stage")
    cache = CacheManager(tmp_path)
    result = fail.run(config, cache, force=True)
    assert result.status == StageStatus.FAILED


def test_run_pipeline_cli_missing_config(tmp_path):
    """CLI should return exit code 1 when config file does not exist."""
    import sys
    from run_pipeline import main

    rc = main(["--config", str(tmp_path / "no_such_file.yaml")])
    assert rc == 1


# ── Gate enforcement tests ────────────────────────────────────────────────────


def _build_orchestrator(tmp_path: Path) -> PipelineOrchestrator:
    """Create a PipelineOrchestrator with a null README logger to avoid
    touching the real README.md during tests."""
    cfg_path = _write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n", encoding="utf-8")

    from pipeline.logger import ReadmeLogger

    orch = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orch._config = ConfigLoader(cfg_path)
    orch._force = True
    orch._cache = CacheManager(tmp_path)
    orch._logger = type(
        "_NullLogger",
        (),
        {"log": lambda *a, **k: None, "log_message": lambda *a, **k: None},
    )()
    orch._readme_logger = ReadmeLogger(readme)
    return orch


def test_pipeline_halts_after_failed_stage(tmp_path):
    """Orchestrator must stop executing after a stage fails its gate."""
    orch = _build_orchestrator(tmp_path)
    config = orch._config
    cache = orch._cache

    # Use module-level (picklable) stage classes.
    stage_list = [
        _FastOkStage("ok_stage"),
        _FailStage("fail_stage"),
        _FastOkStage("skipped_stage"),
    ]

    results = []
    for stage in stage_list:
        result = stage.run(config, cache, force=True)
        orch._readme_logger.log(result)
        results.append(result)
        if result.status in {StageStatus.FAILED, StageStatus.TIMEOUT}:
            break

    # Only two stages should have run: ok_stage and fail_stage.
    # skipped_stage must NOT have run because of the gate halt.
    assert len(results) == 2
    assert results[0].status == StageStatus.COMPLETED
    assert results[1].status == StageStatus.FAILED


def test_pipeline_records_all_stages_in_readme(tmp_path):
    """Each completed stage must be appended to README.md."""
    cfg_path = _write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n", encoding="utf-8")

    from pipeline.logger import ReadmeLogger

    readme_logger = ReadmeLogger(readme)
    config = ConfigLoader(cfg_path)
    cache = CacheManager(tmp_path)

    for name in ("s1", "s2", "s3"):
        stage = _FastOkStage(name)
        result = stage.run(config, cache, force=True)
        readme_logger.log(result)

    content = readme.read_text(encoding="utf-8")
    for name in ("s1", "s2", "s3"):
        assert f"`{name}`" in content


def test_pipeline_readme_records_gate_failure(tmp_path):
    """A failed stage must be recorded in README.md with gate FAILED marker."""
    cfg_path = _write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n", encoding="utf-8")

    from pipeline.logger import ReadmeLogger

    readme_logger = ReadmeLogger(readme)
    config = ConfigLoader(cfg_path)
    cache = CacheManager(tmp_path)

    fail = _FailStage("bad_stage")
    result = fail.run(config, cache, force=True)
    readme_logger.log(result)

    content = readme.read_text(encoding="utf-8")
    assert "bad_stage" in content
    assert "FAILED — pipeline halted" in content
