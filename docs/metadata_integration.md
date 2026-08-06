# Metadata integration

## Source
So Pedestrian metadata comes from the Participant Tracker workbook. The toolkit resolves it according
to `--metadata-mode` (`metadata.py`):
1. **Online** export of the tracker sheet (if a document id is configured). The response is validated
   by magic bytes — a real `.xlsx` starts with `PK`; a 401/HTML login page fails the check.
2. **Local `.xlsx`** file.

Modes: `--metadata-mode auto` (online then local), `online` (require online), `local` (require the
local file), `none` (disable metadata). `--metadata-file` sets the local workbook path;
`--retain-metadata-snapshot` keeps the downloaded workbook (off by default, with a privacy warning).

## What is used
Only **non-identifying** fields: **Williams Sequence** (counterbalancing order), per-trial **LOD**,
and administrative **Status**. These are attached for context and reporting.

## What metadata must NOT do
Metadata **never** affects scoring, window selection, or QC. The engine computes the calibration
window from gaze alone; metadata is joined afterward for labelling — `scan_windows` receives no
metadata.

## Administrative status (never guessed)
An empty/absent participant folder is an **administrative** case, not a scientific failure. Status is
taken **only** from the explicit tracker `Status` (mapped in `participant_status_mapping.yml`); when
the tracker gives no status, the case is recorded as `administrative_no_data_status_unknown` — it is
**never** inferred. Administrative cases are excluded from scientific denominators but fully accounted
for in the inventory: `recorded_sessions + admin_unrecorded + missing_within = theoretical`.

## Privacy
To read the configured fields the tracker workbook must be opened, so the toolkit does not claim the
forbidden fields are "never read". Instead, **only the configured de-identified fields are retained**
in outputs: `participant_id`, trial, gaze metrics, and the three non-identifying metadata fields
(Williams Sequence, LOD, status). An online workbook is downloaded to a temporary file and deleted
after normalisation (unless `--retain-metadata-snapshot` is given), and a forbidden-column guard
aborts any export that would include a personal column. See [privacy.md](privacy.md).
