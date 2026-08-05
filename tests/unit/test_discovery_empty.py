"""Unit tests: empty-discovery stable schema and empty-safe scoping."""
from aria_rig_calibration.discovery import (DISCOVERY_COLUMNS, apply_scope, discover_files,
                                            discovered_pids)
from aria_rig_calibration.logging_utils import CollectingLogger


def test_empty_directory_stable_schema(tmp_path):
    inv = discover_files({"input": {"roots": [str(tmp_path)]}}, CollectingLogger())
    assert list(inv.columns) == DISCOVERY_COLUMNS and len(inv) == 0


def test_unrelated_files_only(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    inv = discover_files({"input": {"roots": [str(tmp_path)]}}, CollectingLogger())
    assert len(inv) == 0 and list(inv.columns) == DISCOVERY_COLUMNS


def test_apply_scope_on_empty(tmp_path):
    inv = discover_files({"input": {"roots": [str(tmp_path)]}}, CollectingLogger())
    scoped = apply_scope(inv, [1, 2, 3], [0, 1, 2])
    assert "in_scope" in scoped.columns and len(scoped) == 0
    assert discovered_pids(inv) == []


def test_missing_root_directory():
    inv = discover_files({"input": {"roots": ["Z:/does/not/exist"]}}, CollectingLogger())
    assert len(inv) == 0 and list(inv.columns) == DISCOVERY_COLUMNS
