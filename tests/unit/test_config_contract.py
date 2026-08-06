"""Unit tests: configuration contract validation (enums, target order/count)."""
import copy

import pytest

from aria_rig_calibration.config import load_study_config, validate_config
from tests.conftest import EXAMPLE_CONFIG


@pytest.fixture
def cfg_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    cfg["metadata"]["enabled"] = False
    return cfg


def test_valid_config_passes(cfg_ok):
    ok, problems = validate_config(cfg_ok)
    assert ok, problems


def test_reject_bad_method(cfg_ok):
    cfg_ok["calibration_search"]["method"] = "grid_search"
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("method" in p for p in problems)


def test_reject_bad_tie_policy(cfg_ok):
    cfg_ok["window_quality"]["tie_policy"] = "latest_start"
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("tie_policy" in p for p in problems)


def test_reject_bad_depth_behavior(cfg_ok):
    cfg_ok["depth"]["present_behavior"] = "ignore"
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("present_behavior" in p for p in problems)


def test_reject_target_orders_not_1_to_n(cfg_ok):
    cfg_ok["target"]["targets"][0]["order"] = 5
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("orders must be exactly" in p for p in problems)


def test_reject_target_count_mismatch(cfg_ok):
    cfg_ok["target"]["expected_count"] = 2   # target_blocks says 3
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("expected_count" in p for p in problems)


def test_reject_duplicate_target_ids(cfg_ok):
    cfg_ok["target"]["targets"][1]["id"] = cfg_ok["target"]["targets"][0]["id"]
    ok, problems = validate_config(cfg_ok)
    assert not ok and any("ids" in p for p in problems)


def test_targets_sorted_by_order_on_load(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    cfg = load_study_config(str(EXAMPLE_CONFIG))
    orders = [t["order"] for t in cfg["target"]["targets"]]
    assert orders == sorted(orders)
