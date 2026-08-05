"""Unit tests: scoring formula, block boundaries, tie-break, determinism, target analysis, N targets."""
import copy

import numpy as np

from aria_rig_calibration.calibration import _min_pairwise_distance, scan_windows
from aria_rig_calibration.gaze import load_gaze
from aria_rig_calibration.target_blocks import analyze_targets


def test_window_found_and_step(cfg, fixture_path):
    sw = scan_windows(load_gaze(fixture_path, cfg)["work"], cfg)
    s = sw["selected"]
    assert s is not None and abs(s["start"] - 0.0) < 1e-9 and abs((s["end"] - s["start"]) - 15) < 1e-9
    steps = np.diff(np.sort(sw["all_windows"].window_start_sec.unique()))
    assert np.allclose(steps, 0.5)


def test_score_formula(cfg, fixture_path):
    sw = scan_windows(load_gaze(fixture_path, cfg)["work"], cfg)
    w = sw["all_windows"].iloc[0]
    expected = w.sum_counts + 4 * w.min_block_count + 80 * w.min_centroid_distance - 25 * w.avg_dispersion
    assert abs(w.score - expected) < 1e-6


def test_half_open_block_boundaries(cfg, fixture_path):
    # Each sample belongs to exactly one block: block sample counts sum to the window total.
    sw = scan_windows(load_gaze(fixture_path, cfg)["work"], cfg)
    w = sw["all_windows"][sw["all_windows"].selected].iloc[0]
    assert w.block_1_sample_count + w.block_2_sample_count + w.block_3_sample_count == w.valid_sample_count


def test_tie_breaks_to_earliest():
    # Two equal-score windows: the earlier start must win (strict '>').
    import pandas as pd
    # flat identical gaze -> every window scores the same; earliest start selected.
    n = 400
    t = np.arange(n) / 10
    work = pd.DataFrame({"rel_sec": t, "x": 0.1, "y": 0.0, "z": 0.9,
                         "yaw_deg": 0.0, "pitch_deg": 0.0, "depth_m": 1.0})
    sw = scan_windows(work, {**_min_cfg()})
    assert sw["selected"]["start"] == 0.0


def _min_cfg():
    return {"calibration_search": {"search_start_sec": 0.0, "search_end_sec": 35.0, "window_length_sec": 15.0, "window_step_sec": 0.5},
            "target_blocks": {"expected_count": 3, "minimum_samples_per_block": 25},
            "window_quality": {"scoring": {"min_counts_weight": 4.0, "min_dist_weight": 80.0, "avg_disp_weight": 25.0}},
            "cluster_qc": {"minimum_separation": 0.02, "dispersion_rule": {"multiplier": 1.5},
                           "review_thresholds": {"min_total_samples": 100, "min_chunk_samples": 25, "late_start_sec": 35}}}


def test_determinism(cfg, fixture_path):
    w = load_gaze(fixture_path, cfg)["work"]
    a, b = scan_windows(w, cfg), scan_windows(w, cfg)
    assert a["selected"]["start"] == b["selected"]["start"] and a["review"]["confidence"] == b["review"]["confidence"]


def test_targets_order_and_separation(cfg, fixture_path):
    sw = scan_windows(load_gaze(fixture_path, cfg)["work"], cfg)
    ta = analyze_targets(sw["selected"], cfg, 99, 0)
    assert list(ta["blocks"].target_id) == ["triview", "dashboard", "ipad"]
    assert ta["pairwise"].angular_separation_deg.min() > 5
    assert len(ta["pairwise"]) == 3                                       # 3 choose 2


def test_min_pairwise_distance_generic():
    c = np.array([[0, 0, 0], [1, 0, 0], [0, 3, 0], [0, 0, 5]])
    assert abs(_min_pairwise_distance(c) - 1.0) < 1e-9                    # over all pairs
    assert _min_pairwise_distance(np.array([[np.nan, 0, 0], [1, 0, 0]])) == 0.0


def test_two_target_generalization(cfg, fixture_path):
    two = copy.deepcopy(cfg)
    two["target_blocks"]["expected_count"] = 2
    two["target"]["targets"] = cfg["target"]["targets"][:2]
    sw = scan_windows(load_gaze(fixture_path, cfg)["work"], two)
    w = sw["all_windows"].iloc[0]
    assert "block_2_sample_count" in w.index and "block_3_sample_count" not in w.index
    ta = analyze_targets(sw["selected"], two, 1, 0)
    assert len(ta["blocks"]) == 2 and len(ta["pairwise"]) == 1
