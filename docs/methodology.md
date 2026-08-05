# Methodology

## Goal
For each Aria participant/trial gaze recording, (1) locate the multi-target **rig-calibration
interval** and (2) characterize **where each calibration target sits in gaze space** and how distinct
and stable those targets are. This is an **exploratory characterization**, not a calibration-accuracy
certification.

## Pipeline
1. **Discovery** — auto-find `general_eye_gaze.csv` files across supported PID/trial layouts
   (`discovery.py`), reconciling folder vs filename PID/trial and flagging (never guessing)
   disagreements. Directory pruning skips `.venv`, results folders, `site-packages`, `__pycache__`.
2. **Schema validation + timestamp normalization** — resolve required columns from candidate lists;
   infer the timestamp unit name-first (`ns/us/ms/s`), else by magnitude; produce `rel_sec`.
3. **Gaze processing** — `yaw = mean(left,right)`, `pitch`, optional `depth`; build CPF gaze-ray
   x/y/z; mark `valid_gaze`.
4. **Legacy sliding-window search** — see [legacy_method.md](legacy_method.md). Fixed 15 s window,
   0.5 s step over 0–35 s, three 5 s blocks, deterministic score, earliest-wins-ties.
5. **Target-block analysis** — per-target yaw/pitch/depth median/mean/SD/MAD, gaze-ray centroids,
   within-target dispersion, and pairwise angular + xyz separation (`target_blocks.py`).
6. **QC & review** — High/Medium/Low confidence and a manual-review manifest.
7. **Diagnostics** — every scanned window and the top candidates, for full auditability.
8. **Outputs** — CSVs, an Excel workbook, plots (PNG/SVG/PDF + one interactive HTML), summaries,
   and a run manifest with the config snapshot.

## Two-layer design
A **generic engine** works in `target_1/2/3` and a generic `participant_id`. A **study profile**
(`studies/<id>/`) maps generic targets to study names and supplies metadata mapping and status
mapping. So Pedestrian maps `target_1→triview`, `target_2→dashboard`, `target_3→ipad`.

## Determinism
Given the same input and config, results are identical (no randomness in selection). Each run records
its config snapshot so results are reproducible. See [migration_from_r.md](migration_from_r.md) for
parity evidence.
