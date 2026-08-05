# Changelog

## 1.0.0 (Python)
- Python port of the verified R `aria_rig_calibration_toolkit`. **Controlled language migration, not a
  redesign** — same scientific method, same config, same outputs.
- Faithful reproduction of the original Python sliding-window method (`legacy_reproduction` mode):
  0–35 s start search, 15 s window, 0.5 s step, three 5 s blocks, score
  `sum(counts)+4·min(count)+80·min_dist−25·avg_disp`, High/Medium/Low QC, earliest-wins-ties.
- **Parity validated three ways:**
  - **85/85 exact** vs the original PID1–19 Python outputs (start/end/counts/confidence/needs-review).
  - **125/125 exact selected windows, 0 regressions** vs the verified R PID1–37 run.
  - **37/37 participant-status agreement** vs the R inventory (incl. administrative no-data cases).
- Two-layer design carried over unchanged: generic engine (`src/aria_rig_calibration/`) + study
  profiles (`studies/so_pedestrian`, `studies/example_study`). Configs are byte-for-byte the same
  method parameters as R, repointed to the `_python` results root.
- Automatic PID1–37 (+ future) discovery; So Pedestrian metadata (Williams Sequence, LOD); admin
  no-data handling; all-scanned-window + alternative-window diagnostics; yaw/pitch angular target
  analysis; QC + manual-review manifest; CSV/Excel/plots; pytest (12/12).
- Kept separate from `gaze_screen_classification_pipeline`; no full-session screen classification.
- The R toolkit remains as the archived reference implementation.
