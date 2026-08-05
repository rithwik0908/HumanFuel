"""Integration tests: end-to-end synthetic runs, CLI, discover-all, output flags, integrity, privacy."""
import os
from pathlib import Path

import pandas as pd
import pytest

from aria_rig_calibration.cli import main
from aria_rig_calibration.models import RunOptions
from aria_rig_calibration.pipeline import run_pipeline
from tests.conftest import EXAMPLE_CONFIG


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


def test_cli_main_synthetic(synthetic_dataset, tmp_path, capsys):
    code = main(["--study-config", str(EXAMPLE_CONFIG), "--data-root", str(synthetic_dataset),
                 "--output-root", str(tmp_path / "out"), "--metadata-mode", "none",
                 "--pids", "1", "--trials", "0-2"])
    assert code == 0
    assert "RUN_ID=" in capsys.readouterr().out


def test_cli_config_error_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ARIA_DATA_ROOT", raising=False)
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    code = main(["--study-config", str(EXAMPLE_CONFIG), "--metadata-mode", "none"])
    assert code == 2 and "ARIA_DATA_ROOT is not set" in capsys.readouterr().err
