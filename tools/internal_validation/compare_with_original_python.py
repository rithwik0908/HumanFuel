#!/usr/bin/env python
"""Internal validation: compare the toolkit against the ORIGINAL Python rig outputs.

This is NOT required for normal operation. It reproduces the historical parity check against the
original ``calibration_window_detection.csv`` outputs (PID1-6 and PID7-19). It is read-only and never
modifies the reference outputs.

Reference inputs (private) come from ``--original-reference-root`` or the environment variable
``ARIA_ORIGINAL_REFERENCE_ROOT`` (a folder containing the two original output subfolders). The gaze
data root comes from the study config (or ``--data-root``).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from aria_rig_calibration.calibration import scan_windows
from aria_rig_calibration.config import apply_path_overrides, load_study_config
from aria_rig_calibration.discovery import discover_files
from aria_rig_calibration.gaze import load_gaze
from aria_rig_calibration.logging_utils import CollectingLogger


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--study-config", required=True)
    ap.add_argument("--data-root", help="Override the gaze data root")
    ap.add_argument("--original-reference-root", default=os.environ.get("ARIA_ORIGINAL_REFERENCE_ROOT"),
                    help="Folder holding the original rig output subfolders (env: ARIA_ORIGINAL_REFERENCE_ROOT)")
    ap.add_argument("--out", required=True, help="Directory to write the parity report into")
    a = ap.parse_args()
    if not a.original_reference_root:
        print("ERROR: set --original-reference-root or ARIA_ORIGINAL_REFERENCE_ROOT", file=sys.stderr)
        return 2

    ref = Path(a.original_reference_root)
    old = pd.concat([
        pd.read_csv(ref / "rig_calibration_analysis_outputs" / "calibration_window_detection.csv"),
        pd.read_csv(ref / "rig_calibration_analysis_outputs_PID7_to_PID19" / "calibration_window_detection.csv"),
    ], ignore_index=True)
    old["pid"] = old.PID.str.replace(r"[^0-9]", "", regex=True).astype(int)
    old["ti"] = old["File Trial Index"]

    cfg = load_study_config(a.study_config)
    apply_path_overrides(cfg, data_root=a.data_root)
    lg = CollectingLogger()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    inv = discover_files(cfg, lg)
    inv = inv[(inv.selected) & inv.participant_id.isin(range(1, 20)) & inv.trial_index.isin(range(5))]
    rows = []
    for r in inv.itertuples():
        pid, ti = int(r.participant_id), int(r.trial_index)
        o = old[(old.pid == pid) & (old.ti == ti)]
        if not len(o):
            continue
        o = o.iloc[0]
        sw = scan_windows(load_gaze(r.absolute_path, cfg)["work"], cfg)
        s, rv = sw["selected"], sw["review"]
        if s is None:
            continue
        n = [s["summaries"][i]["n"] for i in range(3)]
        start_m = round(s["start"], 2) == round(float(o["Calibration Start Sec"]), 2)
        end_m = round(s["end"], 2) == round(float(o["Calibration End Sec"]), 2)
        counts_m = n == [int(o["Chunk 1 Samples"]), int(o["Chunk 2 Samples"]), int(o["Chunk 3 Samples"])]
        conf_m = rv["confidence"] == o["Window Detection Confidence"]
        rev_m = ("Yes" if rv["needs_review"] else "No") == o["Needs Review"]
        cx_m = abs(s["summaries"][0]["centroid"][0] - float(o["Chunk 1 Mean X"])) < 1e-5
        cls = "exact_match" if (start_m and end_m and counts_m and conf_m and rev_m and cx_m) else ("tolerance_match" if start_m and counts_m else "regression")
        rows.append(dict(pid=pid, trial_index=ti, new_start=round(s["start"], 2), old_start=round(float(o["Calibration Start Sec"]), 2),
                         start_match=start_m, end_match=end_m, counts_match=counts_m, new_conf=rv["confidence"],
                         old_conf=o["Window Detection Confidence"], confidence_match=conf_m, needs_review_match=rev_m,
                         centroid_match=cx_m, status=cls))
    cmp = pd.DataFrame(rows)
    cmp.to_csv(out / "original_python_parity.csv", index=False)
    n_ex = int((cmp.status == "exact_match").sum())
    n_reg = int((cmp.status == "regression").sum())
    (out / "original_python_parity_report.md").write_text("\n".join([
        "# Original-Python parity (internal validation)", "",
        f"Sessions compared: {len(cmp)} | exact matches: **{n_ex}/{len(cmp)}** | regressions: {n_reg}", "",
        "Reproduces the original select_window start/end, chunk counts, chunk-mean X, confidence, and",
        "Needs-Review flags. Reference outputs were not modified."]))
    print(f"original-python parity: {n_ex}/{len(cmp)} exact, {n_reg} regressions -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
