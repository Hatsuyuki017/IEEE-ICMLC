"""Tests for CacheManager."""

from __future__ import annotations

from pathlib import Path

from pipeline.cache import CacheManager


def _make_file(path: Path, content: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_check_inputs_returns_false_when_no_cache(tmp_path):
    f = _make_file(tmp_path / "a.txt")
    cache = CacheManager(tmp_path)
    assert cache.check_inputs("stage1", [f]) is False


def test_check_inputs_returns_true_after_record(tmp_path):
    f = _make_file(tmp_path / "a.txt")
    cache = CacheManager(tmp_path)
    cache.record_inputs("stage1", [f])
    assert cache.check_inputs("stage1", [f]) is True


def test_check_inputs_returns_false_after_modification(tmp_path):
    f = _make_file(tmp_path / "a.txt", "original")
    cache = CacheManager(tmp_path)
    cache.record_inputs("stage1", [f])
    f.write_text("modified", encoding="utf-8")
    assert cache.check_inputs("stage1", [f]) is False


def test_check_inputs_returns_false_for_missing_file(tmp_path):
    f = tmp_path / "nonexistent.txt"
    cache = CacheManager(tmp_path)
    assert cache.check_inputs("stage1", [f]) is False


def test_record_outputs_persists_across_instances(tmp_path):
    f = _make_file(tmp_path / "out.txt", "result")
    cache1 = CacheManager(tmp_path)
    cache1.record_outputs("stage1", [f])

    # Reload from disk.
    cache2 = CacheManager(tmp_path)
    assert cache2.check_inputs("stage1", [f]) is True
