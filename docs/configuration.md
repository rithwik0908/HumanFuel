# Configuration

The toolkit is configured with two layers: a generic `config/default_config.yml` and a study profile
under `studies/<id>/`. A study profile `extends:` the default and overrides what it needs.

## Local configuration & paths
No machine-specific path is committed. Path values use `${ENV_VAR}` placeholders resolved at load
time. To run:

1. Copy the example profile to a local, git-ignored file:
   `studies/so_pedestrian/study_config.example.yml` → `study_config.local.yml`.
2. Provide paths by **either** setting environment variables **or** editing the local file, **or**
   passing CLI overrides (highest precedence):

| Variable | CLI override | Meaning |
|---|---|---|
| `ARIA_DATA_ROOT` | `--data-root` | Folder containing the participant recordings. |
| `ARIA_OUTPUT_ROOT` | `--output-root` | Folder to write run outputs into. |
| `ARIA_METADATA_FILE` | `--metadata-file` | Local Participant Tracker `.xlsx` (only if metadata enabled). |
| `ARIA_TRACKER_DOCUMENT_ID` | — | Optional online tracker id (only for `--metadata-mode online/auto`). |

Precedence: **CLI override > environment variable > YAML value**. Missing required paths fail with a
clear message (e.g. `ARIA_DATA_ROOT is not set. ...`).

## Key study-profile fields
- `input.roots` — one or more data roots (walked recursively).
- `participants.include` — PID spec (e.g. `["1-37"]`); `discovery_mode` — `requested_only`,
  `discovered_only`, or `requested_plus_discovered`.
- `trials.expected_indices` — expected trial indices (e.g. `[0,1,2,3,4]`).
- `target_config` → `calibration_targets.targets` — ordered target `id`/`display_name`/`color`.
- `metadata_mapping` — de-identified tracker columns and `forbidden_tokens`.
- `participant_status_mapping` — tracker status → administrative status.

## Method parameters (in `default_config.yml`)
`calibration_search` (search range, window length, step), `target_blocks.expected_count`,
`window_quality.scoring` weights (4/80/25), `cluster_qc` review thresholds. These are the validated
defaults; changing them changes the method.

## Output & integrity
`outputs.{csv,xlsx,png,svg,pdf,html}` toggle each format independently (e.g. `svg: true` with the rest
`false` writes SVG only). `integrity.hash_sources` enables SHA-256 source verification.

## Validation
The configuration is validated before a run: positive window length/step, `search_end >=
search_start`, target count `>= 2` matching the target list with unique orders, block duration
consistent with the count, resolved input roots, and a resolved output root.
