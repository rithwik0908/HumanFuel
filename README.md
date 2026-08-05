# Aria Rig-Calibration Toolkit (Python)

A standalone, reusable Python toolkit that **locates the multi-target rig-calibration interval** in
Project Aria eye-gaze recordings and characterizes **where each calibration target appears in gaze
space**. It is a **parity-validated port of the verified R toolkit** and reproduces the original So
Pedestrian rig-calibration analysis exactly.

> **Parity (validated):** **85/85 exact** vs the original PID1–19 Python outputs · **125/125 exact
> selected windows (0 regressions)** vs the verified R PID1–37 run · **37/37 participant-status
> agreement**. The migration changes the software language and ecosystem, not the underlying
> scientific method.

> This toolkit identifies the calibration interval and characterizes the gaze-space locations of the
> triview, dashboard, and iPad targets. It does **not** classify the complete recording and does not
> claim calibration accuracy without independent video or log validation.

## 1. Purpose
Detect and analyze the multi-target rig-calibration sequence in each Aria participant/trial gaze
recording, and describe the gaze-space location, stability, and distinctness of each target.

## 2. Relationship to the R toolkit
This is a **controlled migration**, not a redesign. Method parameters, config schema, output layout,
and the sliding-window algorithm are identical to `aria_rig_calibration_toolkit` (R). The R version is
kept as the **archived reference implementation**; this Python version is now the primary toolkit.
See [docs/migration_from_r.md](docs/migration_from_r.md).

## 3. So Pedestrian use case
Three calibration targets, confirmed order **Triview/Road → Dashboard → iPad**; PID/trial recordings
(`PID_1/eyeTracking/mps_1-0_vrs/...` etc.); metadata (Williams Sequence + per-trial LOD) from the
Participant Tracker.

## 4. What it does
```
Aria gaze CSV
  -> file discovery (PID/trial, many layouts)
  -> schema validation + timestamp normalization
  -> gaze-angle processing (yaw = mean(left,right); pitch; optional depth)
  -> LEGACY sliding-window search (0..35s start, 15s window, 0.5s step, three 5s blocks)
  -> three target blocks -> centres, dispersion, pairwise separation
  -> QC + all scanned windows + alternative-window diagnostics
  -> plots, summaries, Excel, review report
```

## 5. What it does NOT do
It does **not**: classify the full recording into screen regions; guarantee correct manual ground
truth; reconstruct physical rig coordinates; validate RGB projection; make causal claims about poor
calibration; or confirm target identity beyond the configured temporal order. It is **separate** from
`gaze_screen_classification_pipeline` and does not import that pipeline's detector.

## 6. Structure
`config/` (generic defaults) · `studies/<id>/` (study profiles: `study_config.yml`,
`target_config.yml`, `metadata_mapping.yml`, `participant_status_mapping.yml`) ·
`src/aria_rig_calibration/` (engine) · `scripts/` (run/compare) · `tests/` (pytest) · `docs/` ·
`examples/`. Run outputs go to `aria_rig_calibration_results_python/run_<timestamp>_...` (never inside
the source tree).

## 7. Requirements
Python **3.11+**. Packages: `pandas, numpy, scipy, matplotlib, plotly, pyyaml, openpyxl, jinja2`
(runtime) and `pytest` (tests). Install: `pip install -e ".[dev]"` or `pip install -r
requirements-dev.txt`. `projectaria-tools` is optional (VRS/video helpers only) and not required for
CSV analysis.

## 8. Install
```powershell
Set-Location 'E:\rithwikS2026\aria_rig_calibration_toolkit_python'
python -m pip install -e ".[dev]"
```

## 9. Input data
Required columns: a timestamp (`tracking_timestamp_us`/…), `left_yaw_rads_cpf`, `right_yaw_rads_cpf`,
`pitch_rads_cpf`. Optional: `depth_m` (QC/exploratory only). Column names are resolved from
configurable candidate lists.

## 10. Supported layouts
`PID_1/eyeTracking/mps_1-0_vrs/general_eye_gaze.csv`,
`.../mps_1-0_vrs/eye_gaze/general_eye_gaze.csv`, `PID_1/mps_1-0_vrs_general_eye_gaze.csv`,
`PID1/trial_0/general_eye_gaze.csv`, flat `mps_1-0_vrs_general_eye_gaze.csv`. PID folders:
`PID1/PID_1/PID01/PID_01/pid1`. A `-vrs` separator typo is tolerated; filename/folder disagreements
are flagged, not guessed.

## 11. Running (PowerShell)
```powershell
Set-Location 'E:\rithwikS2026\aria_rig_calibration_toolkit_python'
$S = 'studies\so_pedestrian\study_config.yml'
# PID1-37
python scripts\run_analysis.py --study-config $S --mode legacy_reproduction --pids 1-37 --trials 0-4 --refresh-metadata
# one PID / selected PIDs / trials
python scripts\run_analysis.py --study-config $S --pids 35
# all current + future PIDs (no code edits needed)
python scripts\run_analysis.py --study-config $S --discover-all --refresh-metadata
# offline metadata
python scripts\run_analysis.py --study-config $S --pids 1-37 --offline-metadata
# parity checks
python scripts\compare_with_original_python.py
python scripts\compare_with_r_reference.py --r-run <R_RUN> --python-run <PY_RUN>
```
The installed console command `aria-rig-calibration <same args>` is equivalent to
`python scripts\run_analysis.py`.

## 12. Output guide (per run)
`inventory/` (requested_participants [1 row/requested PID], discovered_files, administrative_no_data,
missing_trials, duplicate_files, ambiguous_files) · `validation/` (schema, r_reference_parity,
excel_validation) · `windows/` (all_scanned_windows, top_candidate_windows, selected_windows) ·
`targets/` (block_samples, centres, pairwise_separation, quality_summary) · `diagnostics/` ·
`metadata/` · `summaries/` · `review/` · `excel/aria_rig_calibration_analysis.xlsx` · `plots/{png,
svg,pdf,html}/` · `reports/` · `logs/` · `manifest/`.

## 13. How the legacy sliding-window method works
Scan window starts `0 .. min(35, duration−15)` in **0.5 s** steps. Each **15 s** window splits into
**three 5 s blocks**. Score `= sum(counts) + 4·min(count) + 80·min_centroid_distance −
25·avg_dispersion` (3-D gaze-ray centroids). Pick the **max-score** window (earliest wins ties).
Blocks map by time to **triview → dashboard → iPad**. QC/confidence (High/Medium/Low) from sample
counts, block distinctness, dispersion. See [docs/legacy_method.md](docs/legacy_method.md).

## 14. Interpreting results (`exploratory_result`)
`selected_clear` (High confidence) · `selected_with_qc_warning` · `multiple_similar_windows`
(best≈second-best score — timing is ambiguous) · `weak_target_separation` · `insufficient_samples` ·
`no_valid_window` · `administrative_no_data`.

## 15. Coordinate frames & depth
x/y/z are **CPF-relative gaze-ray points** (unit direction from yaw/pitch, ×depth) — **not** physical
rig coordinates; no rig transform is applied. Primary analysis is yaw/pitch angular space; depth is
QC/exploratory. See [docs/coordinate_frames.md](docs/coordinate_frames.md).

## 16. Adding a new Aria study
Copy `studies/example_study/`, edit `study_config.yml` (input roots), `target_config.yml` (target
names/order/count), and `metadata_mapping.yml` (or disable metadata). Run with `--discover-all`. No
engine (`src/`) edits are required. See [examples/new_study_setup.md](examples/new_study_setup.md).

## 17. Testing / reproducibility / privacy / license
`pytest` (12/12). Reproducibility: fixed method + config snapshot in each run manifest; parity
validated 85/85 (original Python) and 125/125 windows + 37/37 status (R PID1–37). **Privacy:** no
names, emails, phones, payment, gift-card, or scheduling notes are ever exported — only de-identified
`participant_id`, trial, gaze-derived metrics, and non-identifying metadata (Williams Sequence, LOD,
admin status). **Limitation:** the legacy algorithm assumes exactly **three fixed-duration blocks**; a
different target count is a generalization beyond the validated baseline. License: see `LICENSE`.
See also [docs/troubleshooting.md](docs/troubleshooting.md).
