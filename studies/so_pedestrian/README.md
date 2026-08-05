# So Pedestrian study profile

## Purpose
Locate the rig-calibration interval and the gaze-space locations of the three calibration targets
(**Triview/Road → Dashboard → iPad**) for every So Pedestrian PID/trial Aria recording.

## Dataset organization
Recordings live under `E:/rithwikS2026` (`PID_1/eyeTracking/mps_1-0_vrs/...`) and
`E:/rithwikS2026/eye tracking` (`PID7/mps_7-0_vrs_general_eye_gaze.csv`). PID folders take several
forms; trials are indexed 0–4 (human trial numbers 1–5).

## Target order
Confirmed: `triview (target_1) → dashboard (target_2) → iPad (target_3)`, assigned by time to the
three window blocks (see `target_config.yml`).

## Tracker fields (privacy-limited)
Only PID, `Williams' Sequence`, per-trial LOD (`Trial 1..5`), and `Status` are read
(`metadata_mapping.yml`). Names, emails, phone, payment, gift-card, and scheduling notes are never
extracted. Metadata is attached AFTER analysis and never changes the calibration result.

## Administrative statuses
Empty/absent PID folders are administrative no-data cases, taken only from an explicit tracker
`Status` (e.g. "cancelled" → `administrative_no_data_cancelled`); otherwise
`administrative_no_data_status_unknown` (never guessed). They are excluded from scientific denominators.

## Run commands
```
$env:R_LIBS_USER='E:\rithwikS2026\.Rlibs'
$R='C:\Program Files\R\R-4.6.1\bin\Rscript.exe'; $S='studies\so_pedestrian\study_config.yml'
& $R scripts\run_analysis.R --study-config $S --pids 1-37 --trials 0-4 --refresh-metadata   # PID1-37
& $R scripts\run_analysis.R --study-config $S --discover-all --refresh-metadata             # + future PIDs
& $R scripts\compare_with_legacy_outputs.R --study-config $S                                # validate reproduction
```

## Interpreting outputs
`windows/selected_windows.csv` — one selected calibration window per recorded session (start/end,
score, confidence, `exploratory_result`). `targets/target_centres.csv` — per-target yaw/pitch centres
and dispersion. `targets/target_pairwise_separation.csv` — how distinct the three targets are.
`review/manual_review_manifest.csv` — sessions needing human video/log confirmation.

## Adding new PIDs
Drop `PID38/...` (any supported layout) under a root and run `--discover-all`. No code edits.
