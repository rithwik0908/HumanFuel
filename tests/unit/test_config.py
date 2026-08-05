"""Unit tests: environment-variable expansion, override precedence, and validation."""
import pytest

from aria_rig_calibration.config import (apply_path_overrides, expand_env, expand_pid_spec,
                                         load_study_config, validate_config)
from tests.conftest import EXAMPLE_CONFIG


def test_env_expansion_recursive(monkeypatch):
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", "/tmp/out")
    obj = {"a": "${ARIA_OUTPUT_ROOT}/x", "b": ["${ARIA_OUTPUT_ROOT}", 3], "c": {"d": "${ARIA_OUTPUT_ROOT}"}}
    missing = set()
    out = expand_env(obj, missing)
    assert out["a"] == "/tmp/out/x" and out["b"][0] == "/tmp/out" and out["c"]["d"] == "/tmp/out"
    assert not missing


def test_env_missing_recorded():
    missing = set()
    out = expand_env("${ARIA_DATA_ROOT}/z", missing)
    assert out == "${ARIA_DATA_ROOT}/z" and "ARIA_DATA_ROOT" in missing   # left literal, recorded


def test_config_load_and_output_root(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path / "out"))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    assert cfg["outputs"]["root"] == str(tmp_path / "out")
    assert "ARIA_DATA_ROOT" in cfg["_unresolved_env"]                     # still unresolved


def test_cli_override_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_DATA_ROOT", "env_root")
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    assert cfg["input"]["roots"] == ["env_root"]
    apply_path_overrides(cfg, data_root="cli_root")
    assert cfg["input"]["roots"] == ["cli_root"]                          # CLI beats env


def test_validation_missing_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("ARIA_DATA_ROOT", raising=False)
    ok, problems = validate_config(load_study_config(str(EXAMPLE_CONFIG)))
    assert not ok and any("ARIA_DATA_ROOT is not set" in p for p in problems)


def test_validation_passes_with_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    cfg["metadata"]["enabled"] = False   # avoid requiring a metadata file
    ok, problems = validate_config(cfg)
    assert ok, problems


def test_validation_rejects_bad_target_count(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    cfg["target_blocks"]["expected_count"] = 1
    ok, problems = validate_config(cfg)
    assert not ok and any(">= 2" in p for p in problems)


def test_pid_spec():
    assert expand_pid_spec(["1-37"]) == list(range(1, 38))
    assert expand_pid_spec(["1-6", "35"])[-1] == 35
