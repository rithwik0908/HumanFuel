"""Unit tests: discovery/parsing and gaze processing (timestamps, missing eyes/depth)."""
import numpy as np
import pandas as pd

from aria_rig_calibration.discovery import parse_pid_trial, reconcile
from aria_rig_calibration.gaze import infer_time_unit, load_gaze, validate_schema
from tests.conftest import synth_gaze_frame


def _schema(tmp_path, cfg, frame):
    p = tmp_path / "g.csv"
    frame.to_csv(p, index=False)
    return validate_schema(str(p), {"participant_id": 1, "trial_index": 0}, cfg)


def test_schema_reports_left_only(tmp_path, cfg):
    s = _schema(tmp_path, cfg, synth_gaze_frame().drop(columns=["right_yaw_rads_cpf"]))
    assert s["resolved_left_yaw"] == "left_yaw_rads_cpf" and s["resolved_right_yaw"] is None


def test_schema_reports_right_only(tmp_path, cfg):
    s = _schema(tmp_path, cfg, synth_gaze_frame().drop(columns=["left_yaw_rads_cpf"]))
    assert s["resolved_left_yaw"] is None and s["resolved_right_yaw"] == "right_yaw_rads_cpf"  # not mislabelled left


def test_schema_reports_both(tmp_path, cfg):
    s = _schema(tmp_path, cfg, synth_gaze_frame())
    assert s["resolved_left_yaw"] == "left_yaw_rads_cpf" and s["resolved_right_yaw"] == "right_yaw_rads_cpf"


def test_schema_reports_neither(tmp_path, cfg):
    s = _schema(tmp_path, cfg, synth_gaze_frame().drop(columns=["left_yaw_rads_cpf", "right_yaw_rads_cpf"]))
    assert s["resolved_left_yaw"] is None and s["resolved_right_yaw"] is None and s["validation_status"] != "ok"


def test_parse_layouts():
    assert reconcile(parse_pid_trial("x/PID35/mps_35-0_vrs_general_eye_gaze.csv"))["pid"] == 35
    r = reconcile(parse_pid_trial("x/PID_1/eyeTracking/mps_1-3_vrs/eye_gaze/general_eye_gaze.csv"))
    assert r["pid"] == 1 and r["trial_index"] == 3
    for v in ("PID99", "PID_99", "PID099", "pid_99"):
        assert parse_pid_trial(f"x/{v}/mps_99-0_vrs_general_eye_gaze.csv")["pid_dir"] == 99


def test_pid99_discoverable():
    assert reconcile(parse_pid_trial("x/PID_99/mps_99-0_vrs_general_eye_gaze.csv"))["pid"] == 99


def test_filename_folder_disagreement_flagged():
    r = reconcile(parse_pid_trial("x/PID7/mps_8-0_vrs_general_eye_gaze.csv"))
    assert r["parse_status"] == "pid_mismatch" and r["pid"] is None      # flagged, not guessed


def test_timestamp_units():
    assert infer_time_unit("tracking_timestamp_us", np.array([2.7e15, 2.7e15 + 1e8]))[0] == 1e6  # name first
    assert infer_time_unit("timestamp", np.array([2.7e15, 2.7e15 + 1e8]))[0] == 1e9              # magnitude


def test_combined_yaw_mean(cfg, fixture_path):
    g = load_gaze(fixture_path, cfg)
    assert abs(np.nanmean(g["work"].yaw_rads[:50]) - 0.5) < 0.02          # mean(left,right)


def _load_frame(tmp_path, cfg, frame):
    p = tmp_path / "g.csv"
    frame.to_csv(p, index=False)
    return load_gaze(str(p), cfg)["work"]


def test_missing_left_eye(tmp_path, cfg):
    f = synth_gaze_frame().drop(columns=["left_yaw_rads_cpf"])
    w = _load_frame(tmp_path, cfg, f)
    assert w.valid_gaze.sum() > 0 and abs(np.nanmean(w.yaw_rads[:50]) - 0.5) < 0.05  # right eye only


def test_missing_right_eye(tmp_path, cfg):
    f = synth_gaze_frame().drop(columns=["right_yaw_rads_cpf"])
    assert _load_frame(tmp_path, cfg, f).valid_gaze.sum() > 0


def test_missing_both_eyes(tmp_path, cfg):
    f = synth_gaze_frame().drop(columns=["left_yaw_rads_cpf", "right_yaw_rads_cpf"])
    assert _load_frame(tmp_path, cfg, f).valid_gaze.sum() == 0            # no yaw -> no valid points


def test_missing_depth_column_uses_unit_depth(tmp_path, cfg):
    f = synth_gaze_frame().drop(columns=["depth_m"])
    w = _load_frame(tmp_path, cfg, f)
    assert w.valid_gaze.sum() > 0                                        # unit-depth directions still valid


def test_partial_depth_rows_invalid(tmp_path, cfg):
    f = synth_gaze_frame()
    f.loc[0:9, "depth_m"] = np.nan
    w = _load_frame(tmp_path, cfg, f)
    assert (~np.isfinite(w.x[:10])).all()                                # NaN depth -> NaN xyz, dropped
    assert w.valid_gaze.iloc[0] == False  # noqa: E712
