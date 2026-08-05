"""Unit tests: administrative status, privacy-safe metadata normalisation, snapshot handling."""
from pathlib import Path

import pandas as pd

from aria_rig_calibration import metadata as md
from aria_rig_calibration.logging_utils import CollectingLogger


def test_admin_status(cfg):
    sm = cfg["status_map"]
    assert md.admin_status_for("cancelled", False, sm) == "administrative_no_data_cancelled"
    assert md.admin_status_for(None, False, sm) == "administrative_no_data_status_unknown"
    assert md.admin_status_for("cancelled", True, sm) is None             # has data -> no admin status


def test_check_forbidden_columns_flags_personal():
    df = pd.DataFrame(columns=["participant_id", "email_address", "notes"])
    leaked = md.check_forbidden_columns(df, ["email", "name", "note"])
    assert leaked == ["email_address"]                                    # 'notes' is allow-listed


def _tracker(path: Path):
    """A synthetic tracker workbook with de-identified fields AND forbidden personal columns."""
    df = pd.DataFrame({"PID": [1, 2], "Williams' Sequence": ["A", "B"], "Status": ["completed", "cancelled"],
                       "Trial 1": ["low", "high"], "Trial 2": ["high", "low"], "Trial 3": ["low", "low"],
                       "Trial 4": ["high", "high"], "Trial 5": ["low", "high"],
                       "Participant Name": ["Alice X", "Bob Y"], "Phone": ["555-1", "555-2"],
                       "Scheduling Notes": ["call am", "reschedule"]})
    df.to_excel(path, index=False)


def test_normalized_metadata_is_deidentified(tmp_path, cfg):
    wb = tmp_path / "tracker.xlsx"
    _tracker(wb)
    out = md.normalize_metadata(str(wb), cfg["metadata_map"], "local", CollectingLogger())
    assert list(out.columns) == md.METADATA_COLUMNS                       # fixed safe schema only
    assert md.check_forbidden_columns(out, cfg["metadata_map"]["forbidden_tokens"]) == []
    assert set(out.participant_id) == {1, 2} and (out.trial_number.max() == 5)


def test_resolve_local_mode(tmp_path, cfg):
    wb = tmp_path / "tracker.xlsx"
    _tracker(wb)
    cfg2 = dict(cfg)
    cfg2["metadata"] = {"enabled": True, "local": str(wb)}
    r = md.resolve_metadata(cfg2, tmp_path, CollectingLogger(), mode="local")
    assert r["source"] == "local" and r["temp_path"] is None


def test_resolve_none_mode(cfg, tmp_path):
    r = md.resolve_metadata(cfg, tmp_path, CollectingLogger(), mode="none")
    assert r["source"] == "none" and r["workbook"] is None


def test_online_snapshot_temp_deletable(tmp_path, cfg, monkeypatch):
    # Simulate an online download; with retain=False the workbook is the temp file (pipeline deletes it).
    wb = tmp_path / "dl.xlsx"
    _tracker(wb)
    monkeypatch.setattr(md, "_download_workbook", lambda url, log: str(wb))
    cfg2 = dict(cfg)
    cfg2["metadata"] = {"enabled": True, "online": {"document_id": "abc"}, "local": None}
    r = md.resolve_metadata(cfg2, tmp_path / "snap", CollectingLogger(), mode="online", retain_snapshot=False)
    assert r["source"] == "online" and r["temp_path"] == str(wb)
    assert not (tmp_path / "snap" / "online_tracker_snapshot.xlsx").exists()   # nothing retained
