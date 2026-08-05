# Data dictionary (key output columns)

## `windows/selected_windows.csv` (one row per analyzed session)
| Column | Meaning |
|---|---|
| `participant_id` | De-identified PID (integer). |
| `trial_number` | Trial index (0–4). |
| `calibration_start_sec` / `calibration_end_sec` | Selected 15 s window bounds (`rel_sec`). |
| `score` | Legacy score of the selected window. |
| `block_1_samples` / `block_2_samples` / `block_3_samples` | Valid gaze samples per 5 s block. |
| `min_centroid_distance` | Min pairwise distance between the three block centroids (gaze-ray units). |
| `avg_dispersion` | Mean of the three block dispersions. |
| `confidence` | `High` / `Medium` / `Low`. |
| `needs_review` | Boolean; true when confidence is not High. |
| `exploratory_result` | `selected_clear`, `selected_with_qc_warning`, `multiple_similar_windows`, `weak_target_separation`, `insufficient_samples`, `no_valid_window`, `administrative_no_data`. |

## `windows/all_scanned_windows.csv`
Every candidate window: `window_start_sec`, `sum_counts`, `min_block_count`, `min_centroid_distance`,
`avg_dispersion`, `score`, `rank`, `selected`. Fully reproduces the selection.

## `targets/*.csv`
- `block_samples` — per-target sample points/counts.
- `centres` — per-target `yaw_deg`/`pitch_deg`/`depth_m` median/mean/SD/MAD and centroid x/y/z.
- `pairwise_separation` — `angular_separation_deg` and xyz separation between target pairs.
- `quality_summary` — within-target dispersion and distinctness flags.

## `inventory/*.csv`
- `requested_participants` — one row per requested PID with `final_participant_status`.
- `discovered_files`, `administrative_no_data`, `missing_trials`, `duplicate_files`, `ambiguous_files`.

## Coordinate note
x/y/z are **CPF-relative gaze-ray points**, not physical rig coordinates; depth is exploratory QC. See
[coordinate_frames.md](coordinate_frames.md).

## Privacy note
No names, emails, phones, payment/gift-card, or scheduling data appear in any output.
