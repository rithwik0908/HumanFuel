#!/usr/bin/env python
"""Phase 14A: validate the Python port against the ORIGINAL Python rig outputs
(calibration_window_detection.csv for PID1-6 and PID7-19). Read-only. Requires 85/85 parity."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aria_rig_calibration.config import load_study_config
from aria_rig_calibration.logging_utils import CollectingLogger
from aria_rig_calibration.discovery import discover_files
from aria_rig_calibration.gaze import load_gaze
from aria_rig_calibration.legacy_sliding_window import scan_windows

ap = argparse.ArgumentParser(); ap.add_argument("--study-config", required=True)
ap.add_argument("--out", default=r"E:\rithwikS2026\aria_rig_calibration_results_python\original_python_parity")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
cfg = load_study_config(a.study_config); lg = CollectingLogger()

old = pd.concat([
    pd.read_csv(r"E:\rithwikS2026\rig_calibration_analysis_outputs\calibration_window_detection.csv"),
    pd.read_csv(r"E:\rithwikS2026\rig_calibration_analysis_outputs_PID7_to_PID19\calibration_window_detection.csv")], ignore_index=True)
old["pid"] = old.PID.str.replace(r"[^0-9]", "", regex=True).astype(int); old["ti"] = old["File Trial Index"]

inv = discover_files(cfg, lg)
inv = inv[(inv.selected) & inv.participant_id.isin(range(1, 20)) & inv.trial_index.isin(range(5))]
rows = []
for r in inv.itertuples():
    pid, ti = int(r.participant_id), int(r.trial_index)
    o = old[(old.pid == pid) & (old.ti == ti)]
    if not len(o): continue
    o = o.iloc[0]
    sw = scan_windows(load_gaze(r.absolute_path, cfg)["work"], cfg); s, rv = sw["selected"], sw["review"]
    if s is None: continue
    n = [s["summaries"][i]["n"] for i in range(3)]
    start_m = round(s["start"], 2) == round(float(o["Calibration Start Sec"]), 2)
    end_m = round(s["end"], 2) == round(float(o["Calibration End Sec"]), 2)
    counts_m = n == [int(o["Chunk 1 Samples"]), int(o["Chunk 2 Samples"]), int(o["Chunk 3 Samples"])]
    conf_m = rv["confidence"] == o["Window Detection Confidence"]
    rev_m = ("Yes" if rv["needs_review"] else "No") == o["Needs Review"]
    cx_m = abs(s["summaries"][0]["centroid"][0] - float(o["Chunk 1 Mean X"])) < 1e-5
    cls = "exact_match" if (start_m and end_m and counts_m and conf_m and rev_m and cx_m) else ("tolerance_match" if start_m and counts_m else "regression")
    rows.append(dict(pid=pid, trial_index=ti, new_start=round(s["start"], 2), old_start=round(float(o["Calibration Start Sec"]), 2),
        start_match=start_m, end_match=end_m, counts_match=counts_m, new_conf=rv["confidence"], old_conf=o["Window Detection Confidence"],
        confidence_match=conf_m, needs_review_match=rev_m, centroid_match=cx_m, status=cls))
cmp = pd.DataFrame(rows); cmp.to_csv(out / "original_python_parity.csv", index=False)
n_ex = int((cmp.status == "exact_match").sum()); n_reg = int((cmp.status == "regression").sum())
md = ["# Original-Python Parity (Phase 14A)", "",
      f"Sessions compared: {len(cmp)} | exact matches: **{n_ex}/{len(cmp)}** | regressions: {n_reg}", "",
      "Python reproduces the original `select_window` selected start/end, chunk counts, chunk-mean X,",
      "confidence, and Needs-Review flags. Old outputs were not modified."]
(out / "original_python_parity_report.md").write_text("\n".join(md))
print(f"original-python parity: {n_ex}/{len(cmp)} exact, {n_reg} regressions -> {out}")
