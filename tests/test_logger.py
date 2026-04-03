"""Tests for ProgressLogger."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.base import StageResult, StageStatus
from pipeline.logger import ProgressLogger, ReadmeLogger


def test_log_writes_json_record(tmp_path):
    log_path = tmp_path / "pipeline.log"
    logger = ProgressLogger(log_path)
    result = StageResult(
        stage="model_tuning",
        status=StageStatus.COMPLETED,
        elapsed_seconds=12.5,
        message="ok",
        artifacts=["outputs/a.json"],
    )
    logger.log(result)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["stage"] == "model_tuning"
    assert record["status"] == "completed"
    assert record["elapsed_seconds"] == 12.5
    assert record["message"] == "ok"
    assert "outputs/a.json" in record["artifacts"]
    assert "timestamp" in record


def test_log_message_writes_json_record(tmp_path):
    log_path = tmp_path / "pipeline.log"
    logger = ProgressLogger(log_path)
    logger.log_message("visualization", "WARNING", "Figure missing")

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["stage"] == "visualization"
    assert record["level"] == "WARNING"
    assert "Figure missing" in record["message"]


def test_log_appends_multiple_records(tmp_path):
    log_path = tmp_path / "pipeline.log"
    logger = ProgressLogger(log_path)
    for status in (StageStatus.COMPLETED, StageStatus.FAILED):
        logger.log(
            StageResult(
                stage="s",
                status=status,
                elapsed_seconds=1.0,
            )
        )
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


# ── ReadmeLogger tests ────────────────────────────────────────────────────────


def test_readme_logger_appends_markdown_section(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n", encoding="utf-8")
    logger = ReadmeLogger(readme)
    result = StageResult(
        stage="model_tuning",
        status=StageStatus.COMPLETED,
        elapsed_seconds=7.3,
        message="all good",
        artifacts=["outputs/results_summary.json"],
    )
    logger.log(result)

    content = readme.read_text(encoding="utf-8")
    assert "## Stage `model_tuning`" in content
    assert "COMPLETED" in content
    assert "7.3s" in content
    assert "all good" in content
    assert "outputs/results_summary.json" in content
    assert "Gate" in content
    assert "PASSED" in content


def test_readme_logger_records_gate_failed_on_failure(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n", encoding="utf-8")
    logger = ReadmeLogger(readme)
    result = StageResult(
        stage="visualization",
        status=StageStatus.FAILED,
        elapsed_seconds=1.0,
        message="subprocess error",
    )
    logger.log(result)

    content = readme.read_text(encoding="utf-8")
    assert "FAILED" in content
    assert "FAILED — pipeline halted" in content


def test_readme_logger_appends_multiple_stages(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n", encoding="utf-8")
    logger = ReadmeLogger(readme)
    for name, status in [("s1", StageStatus.COMPLETED), ("s2", StageStatus.COMPLETED)]:
        logger.log(StageResult(stage=name, status=status, elapsed_seconds=0.1))

    content = readme.read_text(encoding="utf-8")
    assert content.count("## Stage") == 2
    assert "`s1`" in content
    assert "`s2`" in content


def test_readme_logger_creates_file_if_missing(tmp_path):
    readme = tmp_path / "README.md"
    # File does not exist yet — logger should create it.
    logger = ReadmeLogger(readme)
    logger.log(
        StageResult(stage="paper_writing", status=StageStatus.SKIPPED, elapsed_seconds=0.0)
    )
    assert readme.exists()
    content = readme.read_text(encoding="utf-8")
    assert "paper_writing" in content
