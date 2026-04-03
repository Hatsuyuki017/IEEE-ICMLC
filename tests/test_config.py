"""Tests for ConfigLoader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pipeline.config import ConfigLoader, ConfigError


def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "pipeline_config.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


_VALID_YAML = """\
    data_paths:
      cptac_rna: /data/rna
    outputs_dir: outputs
    figures_dir: figures
    sections_dir: sections
    timeout_seconds: 5400
    skills:
      autoresearch: autoresearch
    cloud:
      tool: rclone
      destination: gdrive:test
"""


def test_valid_config_loads(tmp_path):
    cfg_path = _write_config(tmp_path, _VALID_YAML)
    cfg = ConfigLoader(cfg_path)
    cfg.validate()  # should not raise
    assert cfg.timeout_seconds == 5400


def test_get_nested_key(tmp_path):
    cfg_path = _write_config(tmp_path, _VALID_YAML)
    cfg = ConfigLoader(cfg_path)
    assert cfg.get("cloud.tool") == "rclone"
    assert cfg.get("cloud.destination") == "gdrive:test"


def test_get_missing_key_returns_default(tmp_path):
    cfg_path = _write_config(tmp_path, _VALID_YAML)
    cfg = ConfigLoader(cfg_path)
    assert cfg.get("nonexistent.key", "fallback") == "fallback"


_CONFIGS_WITH_MISSING_KEY = {
    "data_paths": """\
        outputs_dir: outputs
        figures_dir: figures
        sections_dir: sections
        timeout_seconds: 5400
        skills:
          autoresearch: autoresearch
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "outputs_dir": """\
        data_paths:
          cptac_rna: /data/rna
        figures_dir: figures
        sections_dir: sections
        timeout_seconds: 5400
        skills:
          autoresearch: autoresearch
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "figures_dir": """\
        data_paths:
          cptac_rna: /data/rna
        outputs_dir: outputs
        sections_dir: sections
        timeout_seconds: 5400
        skills:
          autoresearch: autoresearch
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "sections_dir": """\
        data_paths:
          cptac_rna: /data/rna
        outputs_dir: outputs
        figures_dir: figures
        timeout_seconds: 5400
        skills:
          autoresearch: autoresearch
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "timeout_seconds": """\
        data_paths:
          cptac_rna: /data/rna
        outputs_dir: outputs
        figures_dir: figures
        sections_dir: sections
        skills:
          autoresearch: autoresearch
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "skills": """\
        data_paths:
          cptac_rna: /data/rna
        outputs_dir: outputs
        figures_dir: figures
        sections_dir: sections
        timeout_seconds: 5400
        cloud:
          tool: rclone
          destination: gdrive:test
    """,
    "cloud": """\
        data_paths:
          cptac_rna: /data/rna
        outputs_dir: outputs
        figures_dir: figures
        sections_dir: sections
        timeout_seconds: 5400
        skills:
          autoresearch: autoresearch
    """,
}


@pytest.mark.parametrize("missing_key", list(_CONFIGS_WITH_MISSING_KEY.keys()))
def test_validate_raises_for_missing_key(tmp_path, missing_key):
    cfg_path = _write_config(tmp_path, _CONFIGS_WITH_MISSING_KEY[missing_key])
    cfg = ConfigLoader(cfg_path)
    with pytest.raises(ConfigError, match=missing_key):
        cfg.validate()


def test_resolve_relative_path(tmp_path):
    cfg_path = _write_config(tmp_path, _VALID_YAML)
    cfg = ConfigLoader(cfg_path)
    resolved = cfg.resolve_path("outputs_dir")
    assert resolved.is_absolute()
    assert resolved == tmp_path / "outputs"


def test_file_not_found_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ConfigLoader(tmp_path / "does_not_exist.yaml")
