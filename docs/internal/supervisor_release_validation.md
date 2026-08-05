# Supervisor-release validation

Branch: `cleanup/supervisor-release`. Baseline commit: `a8691625` (v1.0.0). Release: v1.1.0.

## Test results
- **Portable suite:** `pytest` → **40 passed, 1 deselected** (the deselected test is the opt-in
  `local_parity` case). Run in a clean `py -3.12` venv with the package installed **non-editable**.
- **Coverage:** `--cov=aria_rig_calibration` → **89%** overall (all modules ≥ 72%).
- **Packaging:** `pip install .` and a built wheel `aria_rig_calibration-1.1.0-py3-none-any.whl` both
  install into site-packages. `aria-rig-calibration --help` and `python -m aria_rig_calibration.cli
  --help` work from a **neutral directory** (no `scripts/`, no `src/`).
- **Synthetic end-to-end:** the wheel-installed console command processed a synthetic 3-trial dataset
  and produced `selected_windows.csv`, the Excel workbook, and `run_manifest.json`
  (`sources_unmodified=true`).
- **CI:** GitHub Actions matrix ubuntu-latest + windows-latest × Python 3.11 + 3.12; installs the
  package, runs the portable suite with coverage, and runs a synthetic CLI end-to-end. No private data
  or secrets required.

## Real-data parity (scientific invariant preserved)
Re-running the So Pedestrian PID1–37 analysis with the **refactored** pipeline
(`run_20260805_153819_so_pedestrian_PID1_to_PID37`) and comparing to the verified reference run
(`run_20260805_095103...`):

- **Selected windows: 125/125 exact**, 0 regressions (start/end/score/block counts/confidence/needs-review).
- **Participant/administrative status: 37/37** agreement.
- **Original Python outputs (PID1–19): 85/85 exact**, 0 regressions
  (`tools/internal_validation/compare_with_original_python.py`).

The calibration method, So Pedestrian selected windows, target centres, confidence, review flags, and
participant statuses are unchanged.

## Intentional output-schema changes (non-scientific, documented)
1. `manifest/run_manifest.json`: unverified `source_files_modified` / `r_toolkit_modified` /
   `classification_pipeline_modified` booleans replaced by a **verified** `source_files_unmodified`
   (`true`/`false`/`not_checked`) backed by SHA-256 before/after hashing; the unrelated R/classification
   claims removed. New `git`, `reporting_pids`, `discover_all` fields.
2. New `targets/window_target_block_metrics.csv` (generic long-format per-target metrics).
3. `selected_windows.csv` block columns are `block_1..N_samples`; identical to `block_1/2/3_samples`
   for the three-target So Pedestrian study.
4. The manual-review manifest no longer force-includes a specific hardcoded PID (metadata/PID must not
   drive selection or review membership beyond QC).
5. New `validation/excel_validation_report.md`; `excel_validation.csv` gained header/order/key/privacy
   columns.

## Warnings / unresolved items
- **GitHub repository visibility** could not be flipped to private automatically (the stored git
  credential is not accessible to this process and `gh` is not installed). **Action for the owner:**
  set the repo to private in GitHub Settings before sharing. Tracked in `docs/licensing_status`/README.
- **License** is intentionally unset (`LICENSE_PENDING.md`); confirm with supervisors.
- `--discover-all` reporting is implemented and unit-tested with synthetic PID99; it has not been
  exercised against a real future PID beyond PID37 (none exists yet).
- The `local_parity` test requires the private dataset and reference run and is skipped by default.
