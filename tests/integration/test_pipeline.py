"""Integration tests: end-to-end synthetic runs, CLI, discover-all, output flags, integrity, privacy."""
import os
from pathlib import Path

import pandas as pd
import pytest

from aria_rig_calibration.cli import main
from aria_rig_calibration.models import RunOptions
from aria_rig_calibration.pipeline import run_pipeline
from tests.conftest import EXAMPLE_CONFIG, EXAMPLE_STUDY_CONFIG, write_session


def _opts(dataset, out, **kw):
    base = dict(study_config=str(EXAMPLE_CONFIG), data_root=str(dataset), output_root=str(out),
                metadata_mode="none", trials="0-2")
    base.update(kw)
    return RunOptions(**base)


def test_end_to_end_from_other_cwd(synthetic_dataset, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                          # run from a different directory
    out = tmp_path / "out"
    res = run_pipeline(_opts(synthetic_dataset, out, pids="1"))
    run = Path(res.run_root)
    assert (run / "windows" / "selected_windows.csv").is_file()
    sel = pd.read_csv(run / "windows" / "selected_windows.csv")
    assert len(sel) == 3 and {"block_1_samples", "block_2_samples", "block_3_samples"} <= set(sel.columns)
    assert (run / "excel" / "aria_rig_calibration_analysis.xlsx").is_file()


def test_discover_all_includes_pid99(synthetic_dataset, tmp_path):
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", discover_all=True))
    assert 99 in res.reporting_pids and 1 in res.reporting_pids
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    assert 99 in set(inv.participant_id)                                 # newly discovered PID reported


def test_output_format_flags_svg_only(synthetic_dataset, tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_DATA_ROOT", str(synthetic_dataset))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path / "out"))
    from aria_rig_calibration.config import load_study_config, apply_path_overrides
    # Build options but flip output flags via a local config edit through run_pipeline is indirect;
    # instead assert the visualization gate by running with only svg enabled.
    from aria_rig_calibration import pipeline as pl

    real_load = pl.load_and_validate_config

    def patched(opts):
        cfg = real_load(opts)
        cfg["outputs"].update(png=False, svg=True, pdf=False, html=False)
        return cfg
    monkeypatch.setattr(pl, "load_and_validate_config", patched)
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    run = Path(res.run_root)
    assert any((run / "plots" / "svg").glob("*.svg"))
    assert not any((run / "plots" / "png").glob("*.png"))
    assert not any((run / "plots" / "html").glob("*.html"))


def test_integrity_sources_unmodified(synthetic_dataset, tmp_path):
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    assert res.sources_unmodified == "true"
    chk = pd.read_csv(Path(res.run_root) / "manifest" / "source_integrity_check.csv")
    assert (chk.status == "unchanged").all() and (chk.role == "source").any()


def test_processing_error_continues(synthetic_dataset, tmp_path):
    # Corrupt one session; the run should still complete and record a processing status for it.
    bad = synthetic_dataset / "PID_1" / "mps_1-1_vrs_general_eye_gaze.csv"
    bad.write_text("not,a,valid\n1,2\n")
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    status = pd.read_csv(Path(res.run_root) / "logs" / "session_status.csv")
    assert set(status.status) & {"processed"} and len(status) >= 3       # batch continued


def test_no_screen_region_outputs(synthetic_dataset, tmp_path):
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    for csv in Path(res.run_root).rglob("*.csv"):
        try:
            cols = pd.read_csv(csv, nrows=0).columns.str.lower()
        except pd.errors.EmptyDataError:
            continue                                                     # empty inventory file, no header
        assert not any("screen_region" in c for c in cols)              # not a full-session classifier


def test_validation_only_valid_data_status(synthetic_dataset, tmp_path):
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1", validate_only=True))
    run = Path(res.run_root)
    inv = pd.read_csv(run / "inventory" / "requested_participants.csv")
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0] == "validation_only"
    assert res.processed_sessions == 0
    assert not (run / "windows" / "selected_windows.csv").is_file()      # no selected-window outputs


def test_validation_only_invalid_data_status(synthetic_dataset, tmp_path):
    (synthetic_dataset / "PID_1" / "mps_1-0_vrs_general_eye_gaze.csv").write_text("bad,header\n1,2\n")
    (synthetic_dataset / "PID_1" / "mps_1-1_vrs_general_eye_gaze.csv").write_text("bad,header\n1,2\n")
    (synthetic_dataset / "PID_1" / "mps_1-2_vrs_general_eye_gaze.csv").write_text("bad,header\n1,2\n")
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1", validate_only=True))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0] == "invalid_data"


def test_validation_only_no_data_keeps_admin(synthetic_dataset, tmp_path):
    # PID 5 has no recording -> administrative status even in validation-only mode.
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1,5", validate_only=True))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    st5 = inv.loc[inv.participant_id == 5, "final_participant_status"].iloc[0]
    assert st5.startswith("administrative_no_data")


def test_normal_run_statuses_unchanged(synthetic_dataset, tmp_path):
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    # PID1 has 3 valid trials but expected_indices is 0-4 -> partial_data (unchanged behaviour)
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0] in {"processed", "partial_data"}


def test_cli_main_synthetic(synthetic_dataset, tmp_path, capsys):
    code = main(["--study-config", str(EXAMPLE_CONFIG), "--data-root", str(synthetic_dataset),
                 "--output-root", str(tmp_path / "out"), "--metadata-mode", "none",
                 "--pids", "1", "--trials", "0-2"])
    assert code == 0
    assert "RUN_ID=" in capsys.readouterr().out


def test_example_study_runs(tmp_path):
    # The committed example study (three targets, metadata disabled) must run without a KeyError.
    data = tmp_path / "data"
    for ti in (0, 1, 2):
        write_session(data, 7, ti, seed=3 + ti)
    res = run_pipeline(RunOptions(study_config=str(EXAMPLE_STUDY_CONFIG), data_root=str(data),
                                  output_root=str(tmp_path / "out"), metadata_mode="none", discover_all=True))
    run = Path(res.run_root)
    for rel in ["windows/selected_windows.csv", "targets/target_centres.csv",
                "inventory/requested_participants.csv", "manifest/run_manifest.json"]:
        assert (run / rel).is_file(), f"missing {rel}"


def test_empty_data_root(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    res = run_pipeline(_opts(empty, tmp_path / "out", pids="1"))
    assert res.recorded_sessions == 0 and res.processed_sessions == 0
    run = Path(res.run_root)
    assert (run / "manifest" / "run_manifest.json").is_file()
    inv = pd.read_csv(run / "inventory" / "requested_participants.csv")
    assert 1 in set(inv.participant_id)                                  # requested PID still reported
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0].startswith("administrative_no_data")


def test_short_recording_no_window(synthetic_dataset, tmp_path):
    # Replace PID1 trial 0 with a < 15 s recording; it must not produce a selected window.
    write_session(synthetic_dataset, 1, 0, seed=5,
                  holds=((0.0, 0.5, 0.0), (3.0, -0.3, -0.2), (6.0, 0.0, -0.5)), tail_from=9.0, hold_secs=3)
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    run = Path(res.run_root)
    status = pd.read_csv(run / "logs" / "session_status.csv")
    row = status[(status.participant_id == 1) & (status.trial_index == 0)].iloc[0]
    assert row.status == "no_window" and row.reason == "insufficient_duration"
    sel = pd.read_csv(run / "windows" / "selected_windows.csv")
    assert not ((sel.participant_id == 1) & (sel.trial_number == 1)).any()   # no row for the short session
    assert ((sel.participant_id == 1) & (sel.trial_number == 2)).any()       # other trials still analysed


def test_overwrite_cleans_stale(synthetic_dataset, tmp_path):
    out = tmp_path / "out"
    run_pipeline(_opts(synthetic_dataset, out, pids="1", run_id="run_fixed"))
    stale = out / "run_fixed" / "windows" / "selected_windows.csv"
    assert stale.is_file()
    # Re-run validation-only with the same id + overwrite: old selected windows/excel must be gone.
    run_pipeline(_opts(synthetic_dataset, out, pids="1", run_id="run_fixed", overwrite=True, validate_only=True))
    assert not stale.exists()
    assert not (out / "run_fixed" / "excel" / "aria_rig_calibration_analysis.xlsx").exists()


def test_xlsx_flag_disabled(synthetic_dataset, tmp_path, monkeypatch):
    from aria_rig_calibration import pipeline as pl
    real = pl.load_and_validate_config
    monkeypatch.setattr(pl, "load_and_validate_config",
                        lambda o: {**(c := real(o)), "outputs": {**c["outputs"], "xlsx": False}})
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    assert not (Path(res.run_root) / "excel" / "aria_rig_calibration_analysis.xlsx").exists()


def test_integrity_flag_disabled(synthetic_dataset, tmp_path, monkeypatch):
    from aria_rig_calibration import pipeline as pl
    real = pl.load_and_validate_config
    monkeypatch.setattr(pl, "load_and_validate_config",
                        lambda o: {**(c := real(o)), "integrity": {"hash_sources": False}})
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    assert res.sources_unmodified == "not_checked"
    assert not (Path(res.run_root) / "manifest" / "source_integrity_check.csv").exists()


def test_all_invalid_is_invalid_data(synthetic_dataset, tmp_path):
    for ti in (0, 1, 2):
        (synthetic_dataset / "PID_1" / f"mps_1-{ti}_vrs_general_eye_gaze.csv").write_text("x,y\n1,2\n")
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0] == "invalid_data"


def test_one_invalid_two_valid_not_processing_failed(synthetic_dataset, tmp_path):
    (synthetic_dataset / "PID_1" / "mps_1-0_vrs_general_eye_gaze.csv").write_text("x,y\n1,2\n")
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    st = inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0]
    assert st == "partial_data"                                         # not processing_failed


def test_processing_exception_is_processing_failed(synthetic_dataset, tmp_path, monkeypatch):
    from aria_rig_calibration import pipeline as pl
    real = pl.scan_windows

    def boom(work, cfg):
        if len(work) and float(work.rel_sec.max()) > 0 and boom.calls == 0:
            boom.calls += 1
            raise RuntimeError("synthetic failure")
        return real(work, cfg)
    boom.calls = 0
    monkeypatch.setattr(pl, "scan_windows", boom)
    res = run_pipeline(_opts(synthetic_dataset, tmp_path / "out", pids="1"))
    inv = pd.read_csv(Path(res.run_root) / "inventory" / "requested_participants.csv")
    assert inv.loc[inv.participant_id == 1, "final_participant_status"].iloc[0] == "processing_failed"


def test_cli_config_error_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ARIA_DATA_ROOT", raising=False)
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    code = main(["--study-config", str(EXAMPLE_CONFIG), "--metadata-mode", "none"])
    assert code == 2 and "ARIA_DATA_ROOT is not set" in capsys.readouterr().err
