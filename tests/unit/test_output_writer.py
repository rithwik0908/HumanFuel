"""Unit tests: safe run-directory overwrite guards and Excel empty-sheet validation."""
import pandas as pd
import pytest

from aria_rig_calibration.excel_writer import validate_workbook, write_workbook
from aria_rig_calibration.logging_utils import CollectingLogger
from aria_rig_calibration.output_writer import _safe_delete_run_dir, make_run_dir


def test_make_run_dir_no_overwrite_fails(tmp_path):
    cfg = {"outputs": {"root": str(tmp_path)}}
    make_run_dir(cfg, run_id="run_x")
    with pytest.raises(FileExistsError):
        make_run_dir(cfg, run_id="run_x")


def test_make_run_dir_overwrite_cleans(tmp_path):
    cfg = {"outputs": {"root": str(tmp_path)}}
    paths = make_run_dir(cfg, run_id="run_x")
    stale = paths["windows"] / "selected_windows.csv"
    stale.write_text("stale")
    paths2 = make_run_dir(cfg, run_id="run_x", overwrite=True)
    assert not (paths2["windows"] / "selected_windows.csv").exists()   # stale removed
    assert paths2["run_root"].is_dir()


def test_safe_delete_refuses_output_root(tmp_path):
    with pytest.raises(ValueError):
        _safe_delete_run_dir(tmp_path, tmp_path)                        # deleting the root itself


def test_safe_delete_refuses_outside_root(tmp_path):
    other = tmp_path / "a" / "run"
    other.mkdir(parents=True)
    with pytest.raises(ValueError):
        _safe_delete_run_dir(other, tmp_path / "b")                     # not a child of out_root


def _wb(tmp_path, sheet_map):
    dest = tmp_path / "wb.xlsx"
    write_workbook(sheet_map, dest, CollectingLogger())
    return dest


def test_excel_empty_sheet_ok(tmp_path):
    sm = {"Data": pd.DataFrame({"a": [1]}), "Empty": pd.DataFrame()}
    dest = _wb(tmp_path, sm)
    v = validate_workbook(dest, sm, tmp_path / "v.csv", CollectingLogger())
    assert v.set_index("sheet").loc["Empty", "status"] == "empty_ok"
    assert v.set_index("sheet").loc["Data", "status"] == "pass"


def test_excel_empty_sheet_detects_stray_rows(tmp_path):
    from openpyxl import load_workbook
    sm = {"Empty": pd.DataFrame()}
    dest = _wb(tmp_path, sm)
    wb = load_workbook(dest)
    wb["Empty"]["A2"] = "unexpected"      # inject a stray row into a should-be-empty sheet
    wb.save(dest)
    v = validate_workbook(dest, sm, tmp_path / "v.csv", CollectingLogger())
    assert v.set_index("sheet").loc["Empty", "status"] == "row_mismatch"


def test_excel_non_empty_validation_passes(tmp_path):
    sm = {"Data": pd.DataFrame({"score": [1.0, 2.0], "id": [1, 2]})}
    dest = _wb(tmp_path, sm)
    v = validate_workbook(dest, sm, tmp_path / "v.csv", CollectingLogger())
    assert (v.status == "pass").all()
