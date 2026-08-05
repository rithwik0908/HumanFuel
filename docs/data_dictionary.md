# Data dictionary (key output columns)

## `windows/selected_windows.csv` (one row per analysed session)
| Column | Meaning |
|---|---|
| `participant_id` | De-identified PID (integer). |
| `trial_number` | Trial index + 1 (1..5). |
| `calibration_start_sec` / `calibration_end_sec` | Selected window bounds (`rel_sec`). |
| `score` | Score of the selected window. |
| `block_1_samples` .. `block_N_samples` | Valid gaze samples per target block (block_1/2/3 for three targets). |
| `min_centroid_distance` | Min pairwise distance between block centroids (gaze-ray units). |
| `avg_dispersion` | Mean of the block dispersions. |
| `confidence` | `High` / `Medium` / `Low`. |
| `needs_review` | `Yes` / `No`. |
| `exploratory_result` | `selected_clear`, `selected_with_qc_warning`, `multiple_similar_windows`, `weak_target_separation`, `insufficient_samples`, `no_valid_window`, `administrative_no_data`. |
| `sequence_number`, `lod` | Non-identifying metadata (Williams Sequence, per-trial LOD), if enabled. |
| `notes` | QC review notes (analytic; not personal data). |

## `windows/all_scanned_windows.csv`
Every candidate window: `window_start_sec`, `window_end_sec`, `valid_sample_count`,
`block_i_sample_count`, `min_block_count`, `min_centroid_distance`, `avg_dispersion`, `sum_counts`,
`score`, `rank`, `selected`. Fully reproduces the selection.

## `targets/*.csv`
- `target_block_samples` / `window_target_block_metrics` — per-target metrics (long format; works for any target count).
- `target_centres` — per-target `yaw_deg`/`pitch_deg`/`depth_m` centre and centroid x/y/z.
- `target_pairwise_separation` — `angular_separation_deg` and xyz separation for each target pair.
- `target_quality_summary` — within-target dispersion and distinctness per target.

## `inventory/*.csv`
- `requested_participants` — one row per reporting PID with `final_participant_status`.
- `discovered_files`, `administrative_no_data`, `missing_trials`, `duplicate_files`, `ambiguous_files`.

## `manifest/*`
- `run_manifest.json` — run id, git info, reporting scope, method parameters, metadata source,
  `source_files_unmodified` (`true`/`false`/`not_checked`).
- `source_file_hashes_before.csv` / `source_file_hashes_after.csv` / `source_integrity_check.csv` —
  SHA-256 of the selected gaze files and config, before and after processing.
- `config_snapshot/merged_config.yml` — the effective configuration for the run.

## Coordinate & depth note
`x/y/z` are **CPF-relative gaze-ray points** scaled by depth — not physical rig coordinates. Depth
participates in the score via these points; it is not an output-only QC field. See
[coordinate_frames.md](coordinate_frames.md).

## Privacy note
No names, emails, phones, payment/gift-card, or scheduling data appear in any output. See
[privacy.md](privacy.md).
