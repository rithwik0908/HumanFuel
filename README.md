# Project Aria Rig-Calibration Analysis Toolkit

A configurable Python toolkit that **locates the rig-calibration interval** in Project Aria eye-gaze
recordings and **characterises where each configured calibration target appears in gaze space**.

## Purpose
For each participant/trial gaze recording, the toolkit finds the short interval in which the
participant fixates a sequence of calibration targets, then reports where each target sits in gaze
space (yaw/pitch), how tightly clustered each target's samples are, and how well separated the targets
are — with quality-control flags for sessions that need a human look.

## So Pedestrian study
The included study profile (`studies/so_pedestrian/`) is configured for the So Pedestrian protocol:

- Three ordered calibration targets: **triview/road → dashboard → iPad**.
- Up to **five trials** per participant where available.
- Non-identifying metadata attached for context: **Williams Sequence** and per-trial **LOD**.
- **Automatic PID/trial discovery** across the supported folder layouts, including future participants.

## Method overview
The detector scans candidate calibration windows across each recording, splits each window into fixed
equal-duration target blocks, and scores windows by how many samples they contain, how distinct the
target clusters are, and how tightly each cluster holds. It selects the best-scoring window (earliest
on a tie), maps the blocks to the configured targets, and computes per-target centres, dispersion, and
pairwise separation, plus QC confidence. Every scanned window is saved for auditability. Full detail:
[docs/calibration_method.md](docs/calibration_method.md).

## Installation
```powershell
# Windows PowerShell
python -m pip install .
```
```bat
:: Windows Command Prompt
python -m pip install .
```
```bash
# macOS / Linux
python3 -m pip install .
```
Add `".[dev]"` for the test tools and `".[reports]"` for interactive HTML plots. Python 3.11+ is
required. `projectaria-tools` is optional and not needed for CSV analysis.

## Configuration
Paths are supplied at runtime, so nothing machine-specific is committed. Copy the example profile and
provide paths via environment variables or CLI flags (see [docs/configuration.md](docs/configuration.md)):
```powershell
Copy-Item studies\so_pedestrian\study_config.example.yml studies\so_pedestrian\study_config.local.yml
$env:ARIA_DATA_ROOT   = "D:\aria\participants"
$env:ARIA_OUTPUT_ROOT = "D:\aria\results"
$env:ARIA_METADATA_FILE = "D:\aria\Participant Tracker.xlsx"   # only if metadata enabled
```
CLI overrides (`--data-root`, `--output-root`, `--metadata-file`) take precedence over environment
variables and the config file.

## Running
```powershell
$S = "studies\so_pedestrian\study_config.local.yml"
aria-rig-calibration --study-config $S --pids 35                     # one participant
aria-rig-calibration --study-config $S --pids 1-37 --trials 0-4      # a range
aria-rig-calibration --study-config $S --pids 1-6,35                 # selected participants
aria-rig-calibration --study-config $S --discover-all                # every discovered participant
aria-rig-calibration --study-config $S --pids 35 --metadata-mode none   # metadata disabled
aria-rig-calibration --study-config $S --pids 35 --validate-only     # discovery + schema only
```
`python -m aria_rig_calibration.cli ...` and `python scripts/run_analysis.py ...` are equivalent.

**Validation-only runs** (`--validate-only`) perform discovery and schema validation but skip the
calibration analysis: no selected-window outputs are written, participants with valid discovered data
are marked `validation_only`, schema-invalid data is marked `invalid_data`, and participants with no
recording keep their administrative status.

## Inputs
Required gaze columns (resolved from configurable candidates): a timestamp
(`tracking_timestamp_us`/…), `left_yaw_rads_cpf`, `right_yaw_rads_cpf`, `pitch_rads_cpf`. Optional:
`depth_m`. Supported layouts include
`PID_1/eyeTracking/mps_1-0_vrs/general_eye_gaze.csv`, `.../eye_gaze/general_eye_gaze.csv`,
`PID_1/mps_1-0_vrs_general_eye_gaze.csv`, `PID1/trial_0/general_eye_gaze.csv`, and flat
`mps_1-0_vrs_general_eye_gaze.csv`. PID/trial disagreements are flagged, never guessed.

## Outputs (per run, under `ARIA_OUTPUT_ROOT/run_<timestamp>_...`)
- `windows/` — `selected_windows.csv`, `all_scanned_windows.csv`, `top_candidate_windows.csv`.
- `targets/` — per-target centres, block metrics, pairwise separation, quality summary.
- `inventory/` — participant inventory, discovered files, administrative no-data, missing/duplicate/ambiguous.
- `summaries/`, `diagnostics/`, `review/` — cohort summaries, per-session diagnostics, manual-review manifest.
- `excel/aria_rig_calibration_analysis.xlsx` — the formatted workbook.
- `plots/{png,svg,pdf,html}/` — figures (formats toggle independently).
- `validation/` — schema and Excel validation reports.
- `manifest/` — run manifest, merged-config snapshot, and source-integrity hashes.
- `metadata/`, `logs/`. See [docs/data_dictionary.md](docs/data_dictionary.md).

## Quality-control interpretation
Each analysed session is given a human-readable quality outcome (the machine-readable values in
parentheses appear in the output files and the data dictionary for backward compatibility):
- **Clear** — a distinct calibration window was found (`selected_clear`, High confidence).
- **Review recommended** — a window was chosen but a QC note was raised (`selected_with_qc_warning`).
- **Similar candidate windows** — the timing is ambiguous; check the candidate-score plot
  (`multiple_similar_windows`).
- **Weak target separation** — the target clusters are close together (`weak_target_separation`).
- **Insufficient data** — sparse/short data in a block (`insufficient_samples`).
- **Administrative no data** — no recording exists; not an analysis failure (`administrative_no_data`;
  see the inventory). Details in [docs/manual_review_guide.md](docs/manual_review_guide.md).

## Coordinate-frame note
`x/y/z` are **CPF-relative gaze-ray points** (yaw/pitch scaled by depth). Depth participates in the
scoring via these points; they are **not** physical rig coordinates. Yaw/pitch angular space is the
primary interpretation. See [docs/coordinate_frames.md](docs/coordinate_frames.md).

## Future participants & other studies
With `--discover-all`, new PIDs (e.g. PID38+) are discovered, processed, and reported automatically —
no code change. The current validated implementation supports **three ordered calibration targets**;
the engine is written generically for `N ≥ 2` targets, but only the three-target configuration is
validated (see [examples/new_study_setup.md](examples/new_study_setup.md)).

## Privacy
Raw gaze files and Participant Tracker workbooks must **not** be committed; `.gitignore` covers them,
and paths live in local config / environment variables. Only de-identified fields are retained in
outputs. See [docs/privacy.md](docs/privacy.md).

## Testing
```bash
pytest     # portable unit + integration tests (no private data, no network)
```

## Troubleshooting
See [docs/troubleshooting.md](docs/troubleshooting.md).

## Citation / acknowledgements
Please confirm citation and acknowledgement details with the project maintainers.
