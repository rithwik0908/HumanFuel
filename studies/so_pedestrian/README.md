# So Pedestrian study profile

## Purpose
Locate the rig-calibration interval and the gaze-space locations of the three calibration targets
(**Triview/Road → Dashboard → iPad**) for every So Pedestrian participant/trial Aria recording.

## Dataset organization
Recordings live under the folder given by `ARIA_DATA_ROOT` (or `--data-root`). PID folders take
several forms (`PID_1/eyeTracking/mps_1-0_vrs/...`, `PID7/mps_7-0_vrs_general_eye_gaze.csv`, etc.);
trials are indexed 0–4 (human trial numbers 1–5).

## Target order
`triview (target_1) → dashboard (target_2) → iPad (target_3)`, assigned by time to the three window
blocks (see `target_config.yml`).

## Tracker fields (privacy-limited)
Only PID, `Williams' Sequence`, per-trial LOD (`Trial 1..5`), and `Status` are retained in outputs
(`metadata_mapping.yml`). A forbidden-column guard aborts any export that would include a personal
column. Metadata is attached AFTER analysis and never changes the calibration result. See
`../../docs/privacy.md`.

## Administrative statuses
Empty/absent PID folders are administrative no-data cases, taken only from an explicit tracker
`Status` (e.g. "cancelled" → `administrative_no_data_cancelled`); otherwise
`administrative_no_data_status_unknown` (never guessed). They are excluded from scientific denominators.

## Run commands
```powershell
Copy-Item study_config.example.yml study_config.local.yml   # then set ARIA_DATA_ROOT / ARIA_OUTPUT_ROOT
$S = "studies\so_pedestrian\study_config.local.yml"
aria-rig-calibration --study-config $S --pids 1-37 --trials 0-4     # a range
aria-rig-calibration --study-config $S --discover-all               # + future PIDs
aria-rig-calibration --study-config $S --pids 1-37 --validate-only  # discovery + schema only
```

## Interpreting outputs
`windows/selected_windows.csv` — one selected calibration window per recorded session (start/end,
score, confidence, `exploratory_result`). `targets/target_centres.csv` — per-target yaw/pitch centres
and dispersion. `targets/target_pairwise_separation.csv` — how distinct the three targets are.
`review/manual_review_manifest.csv` — sessions needing human video/log confirmation.

## Adding new PIDs
Drop `PID38/...` (any supported layout) under the data root and run `--discover-all`. No code edits.
