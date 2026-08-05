# Metadata integration

## Source
So Pedestrian metadata comes from the **Participant Tracker** (`Participant Tracker-So
Pedestrian.xlsx`). The toolkit resolves it in two steps (`metadata.py`):
1. **Online** export of the tracker sheet (if configured). The response is validated by magic bytes —
   a real `.xlsx` starts with `PK`; a 401/HTML login page fails the check.
2. **Local `.xlsx` fallback** when the online export is unavailable or invalid.

`--offline-metadata` forces the local path; `--refresh-metadata` prefers a fresh online pull.

## What is used
Only **non-identifying** fields: **Williams Sequence** (counterbalancing order), per-trial **LOD**,
and administrative **Status**. These are attached for context and reporting.

## What metadata must NOT do
Metadata **never** affects scoring, window selection, or QC. The engine computes the calibration
window from gaze alone; metadata is joined afterward for labeling. This is enforced by
`test_no_classification_dependency` and by the fact that `scan_windows` receives no metadata.

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
