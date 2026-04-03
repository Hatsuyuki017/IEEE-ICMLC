"""Tests for ProgressLogger."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.base import StageResult, StageStatus
from pipeline.logger import ProgressLogger


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
