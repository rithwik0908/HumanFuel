# Privacy

This toolkit analyses de-identified gaze recordings and attaches only non-identifying metadata. This
page explains what must never be committed and what the code enforces.

## Never commit
- **Raw Aria data**: `.vrs`, `.rrd`, `general_eye_gaze.csv`, `mps_*` folders, `eyeTracking/` trees.
- **Participant Tracker workbooks**: any `*Participant*Tracker*.xlsx` / `.xls` (they contain names,
  emails, phone numbers, payment/gift-card details, addresses, and scheduling notes).
- **Local configuration**: `studies/**/study_config.local.yml`, `.env` files (they embed local paths).
- **Run outputs**: `results/`, `outputs/`, `aria_rig_calibration_results*/`, `run_*/`.
- **Video**: `.mp4`, `.mov`, `.avi`, `.mkv`.

All of the above are covered by `.gitignore`. Paths live in environment variables / local config, so
no machine-specific path is committed either.

## What the toolkit retains
Only these de-identified fields ever reach toolkit outputs: de-identified `participant_id`, trial
index/number, gaze-derived metrics, and the configured non-identifying metadata — **Williams Sequence**,
per-trial **LOD**, and administrative **status**. See `docs/data_dictionary.md`.

## What the code enforces
- **Metadata is retain-limited, not "never read".** To read the configured fields the tracker workbook
  must be opened. An online workbook is downloaded to a secure **temporary** file and **deleted after
  normalisation**; only the sanitised long table is kept. Use `--retain-metadata-snapshot` to keep the
  full workbook in the outputs — this prints a privacy warning and is off by default.
- **Fixed metadata schema.** `normalize_metadata` emits only the columns in
  `aria_rig_calibration.metadata.METADATA_COLUMNS`.
- **Forbidden-column guard.** Before writing the Excel workbook, every sheet is scanned for columns
  whose header matches a forbidden token (`forbidden_tokens` in `metadata_mapping.yml`:
  name/email/phone/payment/gift/claim/serial/address/pronoun/note). The run aborts rather than export
  one. The Excel validator repeats this check and reports `privacy_violation` if any slips through.
  (The toolkit's own analytic columns such as QC `notes` and `target_display_name` are allow-listed.)

## If private data was ever committed
Check history with:
```
git log --stat --all | Select-String -Pattern "Tracker|general_eye_gaze|\.vrs|\.xlsx"
git log --all --name-only --pretty=format: | Sort-Object -Unique
```
This repository's history was reviewed and contains only source code, configuration, docs, and tests
(no raw data or tracker workbooks). If a future commit introduces private data, remove it from history
with `git filter-repo` (preferred) or the BFG Repo-Cleaner, then force-update with project-owner
approval — do not simply delete the file in a new commit, as it remains in history.
