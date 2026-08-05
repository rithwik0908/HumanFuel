# Final report — R → Python migration of the Aria Rig-Calibration Toolkit

**Date:** 2026-08-05 · **Version:** 1.0.0 (Python) · **Status:** parity-validated; Python is now the
primary toolkit, R is the archived reference.

## 1. Objective
Port the completed R `aria_rig_calibration_toolkit` to Python as a **controlled language migration,
not a redesign**: same scientific method, same configuration, same outputs — only the language and
ecosystem change.

## 2. Acceptance criteria (both MET)
The user set two gates before Python could become primary:

| Gate | Requirement | Result |
|---|---|---|
| 1 | **85/85 parity** with the original PID1–19 Python outputs | **85/85 exact, 0 regressions** ✅ |
| 2 | Parity with the verified **PID1–37 R run** | **125/125 exact selected windows, 0 regressions; 37/37 participant-status agreement** ✅ |

Evidence:
- `aria_rig_calibration_results_python/original_python_parity/original_python_parity_report.md`
- `.../run_20260805_123810_so_pedestrian_PID1_to_PID37/validation/r_reference_parity_report.md`

## 3. What was delivered
- **Package** `src/aria_rig_calibration/` — 12 modules (config, gaze, legacy_sliding_window,
  target_blocks, discovery, metadata, logging_utils, output_writer, excel_writer, visualization, cli,
  `__init__`), Python 3.11+, type hints + docstrings.
- **Scripts** — `run_analysis.py` (orchestrator), `compare_with_original_python.py` (85/85),
  `compare_with_r_reference.py` (R parity).
- **Config** — generic `config/default_config.yml` + study profiles `studies/so_pedestrian/` and
  `studies/example_study/`, repointed to the `_python` results root.
- **Tests** — `pytest` suite, **12/12 passing** (config, PID spec, path parsing, timestamp inference,
  gaze, sliding-window step/blocks/score/tie, target blocks, determinism, admin status,
  no-classification-dependency, original-Python parity spot-check).
- **Packaging & docs** — `pyproject.toml`, `requirements-dev.txt`, `.gitignore`, `LICENSE`,
  `CHANGELOG.md`, `README.md`, `docs/` (methodology, migration_from_r, legacy_method,
  coordinate_frames, data_dictionary, metadata_integration, manual_review_guide, troubleshooting,
  this report), `examples/` (quickstart, new_study_setup).
- **Full run** — `run_20260805_123810_so_pedestrian_PID1_to_PID37` (125 selected windows; inventory,
  targets, diagnostics, Excel, plots, manifest).

## 4. Method fidelity (unchanged from R / original Python)
Sliding window: starts `0 .. min(35, dur−15)` in **0.5 s** steps, **15 s** window, **three 5 s
blocks**; score `= sum(counts) + 4·min(counts) + 80·min_centroid_dist − 25·avg_dispersion`;
**max-score, earliest-wins-ties**; QC High(0)/Medium(1)/Low(≥2); coordinates
`x=depth·cos(pitch)·sin(yaw)`, `y=depth·sin(pitch)`, `z=depth·cos(pitch)·cos(yaw)`,
`yaw=mean(left,right)`. `legacy_reproduction` adds **no** new rejection logic. Metadata (Williams
Sequence, LOD, admin status) **never** affects scoring/selection/QC.

## 5. Scope & privacy (preserved)
- x/y/z are **CPF-relative gaze-ray points**, not physical rig coordinates; primary analysis is
  yaw/pitch angular space; depth is exploratory QC only.
- No full-session screen classification; **separate** from `gaze_screen_classification_pipeline`.
- Administrative no-data is taken only from explicit tracker Status, else
  `administrative_no_data_status_unknown` — **never guessed**; excluded from scientific denominators
  but fully reconciled in the inventory.
- **No** names, emails, phones, payment/gift-card, or scheduling notes are ever exported.
- No source data, VRS/MPS, the Participant Tracker, original Python scripts, original rig output
  folders, the R toolkit, R result folders, or the classification pipeline were modified or
  overwritten. The R toolkit is retained as the archived reference.

## 6. Conclusion
The Python toolkit is a parity-validated port of the verified R implementation and original
rig-calibration analysis. It identifies and characterizes the triview, dashboard, and iPad
calibration targets in Project Aria gaze space. The migration changes the software language and
ecosystem, not the underlying scientific method.
