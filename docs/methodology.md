# Methodology

## Goal
For each Aria participant/trial gaze recording, (1) locate the multi-target **rig-calibration
interval** and (2) characterise **where each calibration target sits in gaze space** and how distinct
and stable those targets are. This is an **exploratory characterisation**, not a calibration-accuracy
certification.

## Pipeline
1. **Discovery** — auto-find `general_eye_gaze.csv` files across supported PID/trial layouts
   (`discovery.py`), reconciling folder vs filename PID/trial and flagging (never guessing)
   disagreements. Directory pruning skips virtual-envs, results folders, `site-packages`, etc.
2. **Schema validation + timestamp normalisation** — resolve required columns from candidate lists;
   infer the timestamp unit name-first (`ns/us/ms/s`), else by magnitude; produce `rel_sec`.
3. **Gaze processing** — `yaw = mean(left, right)`, `pitch`, optional `depth`; build CPF gaze-ray
   `x/y/z`; mark `valid_gaze`.
4. **Calibration-window search** — see [calibration_method.md](calibration_method.md). Fixed-length
   window, fixed step, `N` equal-duration blocks, deterministic score, earliest-wins-ties.
5. **Target-block analysis** — per-target yaw/pitch/depth median/mean/SD/MAD, gaze-ray centroids,
   within-target dispersion, and pairwise angular + xyz separation (`target_blocks.py`).
6. **QC & review** — High/Medium/Low confidence and a manual-review manifest.
7. **Diagnostics** — every scanned window and the top candidates, for full auditability.
8. **Integrity & outputs** — SHA-256 source-integrity verification, CSVs, an Excel workbook, plots,
   summaries, and a run manifest with the merged-config snapshot.

## Two-layer design
A **generic engine** works with `target_1..N` and a generic `participant_id`. A **study profile**
(`studies/<id>/`) maps generic targets to study names and supplies metadata and status mappings.
So Pedestrian maps `target_1 → triview`, `target_2 → dashboard`, `target_3 → iPad`.

## Determinism & reproducibility
Given the same input and config, results are identical (no randomness in selection). Each run records
its merged-config snapshot and source-file hashes, so results are reproducible and inputs are verified
unmodified.

## Scope
The toolkit does not classify the full recording into screen regions and is independent of any
separate gaze-screen classification pipeline. See [calibration_method.md](calibration_method.md) and
[coordinate_frames.md](coordinate_frames.md).
