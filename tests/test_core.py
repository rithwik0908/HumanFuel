"""Comprehensive tests for the Aria rig-calibration toolkit (Python)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aria_rig_calibration.config import validate_config, expand_pid_spec
from aria_rig_calibration.discovery import parse_pid_trial, reconcile
from aria_rig_calibration.gaze import load_gaze, infer_time_unit
from aria_rig_calibration.legacy_sliding_window import scan_windows
from aria_rig_calibration.target_blocks import analyze_targets
from aria_rig_calibration.metadata import admin_status_for


def test_config(cfg):
    assert cfg["calibration_search"]["window_length_sec"] == 15
    assert cfg["calibration_search"]["window_step_sec"] == 0.5
    assert cfg["calibration_search"]["search_end_sec"] == 35
    assert validate_config(cfg)[0]


def test_pid_spec():
    assert expand_pid_spec(["1-37"]) == list(range(1, 38))
    assert expand_pid_spec(["1-6", "35"])[-1] == 35


def test_parsing():
    assert reconcile(parse_pid_trial("E:/x/PID35/mps_35-0_vrs_general_eye_gaze.csv"))["pid"] == 35
    r = reconcile(parse_pid_trial("E:/x/PID_1/eyeTracking/mps_1-3_vrs/eye_gaze/general_eye_gaze.csv"))
    assert r["pid"] == 1 and r["trial_index"] == 3
    for v in ("PID99", "PID_99", "PID099", "pid_99"):
        assert parse_pid_trial(f"E:/x/{v}/mps_99-0_vrs_general_eye_gaze.csv")["pid_dir"] == 99
    assert reconcile(parse_pid_trial("E:/x/PID7/mps_8-0_vrs_general_eye_gaze.csv"))["parse_status"] == "pid_mismatch"


def test_timestamp_unit():
    assert infer_time_unit("tracking_timestamp_us", np.array([2.7e15, 2.7e15 + 1e8]))[0] == 1e6  # name-first
    assert infer_time_unit("timestamp", np.array([2.7e15, 2.7e15 + 1e8]))[0] == 1e9              # magnitude fallback


def test_gaze(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg)
    assert len(g["cols"]["yaw_cols"]) == 2 and g["cols"]["pitch"] is not None
    assert abs(np.nanmean(g["work"].yaw_rads[:50]) - 0.5) < 0.02          # combined yaw = mean(left,right)
    assert "microseconds" in g["meta"]["ts_unit"]


def test_sliding_window(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg); sw = scan_windows(g["work"], cfg); s = sw["selected"]
    assert s is not None
    assert abs(s["start"] - 0.0) < 1e-9                                    # calibration region found at start
    assert abs((s["end"] - s["start"]) - 15) < 1e-9
    assert len(s["blocks"]) == 3
    steps = np.diff(np.sort(sw["all_windows"].window_start_sec.unique()))
    assert np.allclose(steps, 0.5)                                        # exact 0.5 s step
    assert sw["all_windows"].iloc[0]["rank"] == 1 and bool(sw["all_windows"].iloc[0]["selected"])


def test_score_formula(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg); sw = scan_windows(g["work"], cfg)
    w = sw["all_windows"].iloc[0]
    expected = (w.sum_counts + 4 * w.min_block_count + 80 * w.min_centroid_distance - 25 * w.avg_dispersion)
    assert abs(w.score - expected) < 1e-6                                 # exact legacy score


def test_targets(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg); sw = scan_windows(g["work"], cfg)
    ta = analyze_targets(sw["selected"], cfg, 99, 0)
    assert list(ta["blocks"].target_id) == ["triview", "dashboard", "ipad"]   # confirmed order
    assert ta["pairwise"].angular_separation_deg.min() > 5                     # distinct


def test_determinism(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg)
    a, b = scan_windows(g["work"], cfg), scan_windows(g["work"], cfg)
    assert a["selected"]["start"] == b["selected"]["start"] and a["review"]["confidence"] == b["review"]["confidence"]


def test_admin_status(cfg):
    assert admin_status_for("cancelled", False, cfg["status_map"]) == "administrative_no_data_cancelled"
    assert admin_status_for(None, False, cfg["status_map"]) == "administrative_no_data_status_unknown"
    assert admin_status_for("cancelled", True, cfg["status_map"]) is None


def test_no_classification_dependency():
    src = "\n".join((ROOT / "src" / "aria_rig_calibration" / f).read_text() for f in ["legacy_sliding_window.py", "gaze.py", "target_blocks.py"])
    assert "gaze_screen_classification_pipeline" not in src
    assert "screen_region" not in src                                     # no full-session screen labels


def test_original_python_parity(cfg):
    """85-session parity is validated by scripts/compare_with_original_python.py; here spot-check PID1."""
    old = pd.read_csv(r"E:\rithwikS2026\rig_calibration_analysis_outputs\calibration_window_detection.csv")
    old = old[old.PID == "PID_1"]
    for ti in range(5):
        p = f"E:/rithwikS2026/PID_1/eyeTracking/mps_1-{ti}_vrs/eye_gaze/general_eye_gaze.csv"
        if not Path(p).exists():
            continue
        sw = scan_windows(load_gaze(p, cfg)["work"], cfg)
        o = old[old["File Trial Index"] == ti].iloc[0]
        assert round(sw["selected"]["start"], 2) == round(float(o["Calibration Start Sec"]), 2)
        assert sw["review"]["confidence"] == o["Window Detection Confidence"]
