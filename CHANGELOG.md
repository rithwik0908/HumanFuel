# Changelog

## 1.1.0 — supervisor release
Portability, packaging, privacy, and maintainability hardening. The calibration method and the
So Pedestrian scientific outputs are unchanged (verified against the reference run).

- **Portable configuration:** `${ENV_VAR}` expansion in configs; `ARIA_DATA_ROOT` / `ARIA_OUTPUT_ROOT`
  / `ARIA_METADATA_FILE` and CLI overrides (`--data-root`/`--output-root`/`--metadata-file`); no
  machine-specific path committed. Committed `study_config.example.yml`; local config is git-ignored.
- **Installable execution:** orchestration moved into `aria_rig_calibration.pipeline`; `aria-rig-
  calibration` console command and `python -m aria_rig_calibration.cli` work without the `scripts/`
  folder; `scripts/run_analysis.py` is a thin wrapper. `main()` split into small, testable stages.
- **CLI:** removed `--mode`; added `--metadata-mode {auto,online,local,none}`,
  `--retain-metadata-snapshot`, and path overrides.
- **Privacy:** metadata retained as a fixed de-identified schema; online workbook downloaded to a temp
  file and deleted after normalisation (opt-in retention with a warning); forbidden-column guard on
  every export; expanded `.gitignore`; `docs/privacy.md`.
- **Integrity:** real SHA-256 source-integrity verification (before/after) replaces unchecked manifest
  claims; merged-config snapshot recorded.
- **Generalisation:** target-block and pairwise logic generalised to `N ≥ 2` targets (loops +
  `itertools.combinations`); three-target output byte-identical; example study made functional; added
  `targets/window_target_block_metrics.csv`.
- **Discover-all:** discovered PIDs (e.g. PID38+) included in processing, inventory, summaries,
  denominators, and the run label.
- **Outputs:** `png/svg/pdf/html` flags honoured independently; plot colours/labels from target config.
- **Excel validation:** sheet presence/order, row/column counts, header names/order, key totals, and a
  privacy scan.
- **Docs:** supervisor-facing README; neutral `docs/calibration_method.md`; corrected depth
  documentation; migration/parity history moved to `docs/internal/`.
- **Tests & CI:** portable `pytest` suite (unit/integration) with an opt-in `local_parity` marker;
  GitHub Actions matrix (ubuntu/windows × Python 3.11/3.12) with a synthetic end-to-end run.
- **Licensing:** placeholder license removed; `LICENSE_PENDING.md` added.

## 1.0.0
Initial Python toolkit (validated against the original PID1–19 outputs and the verified R PID1–37 run;
see `docs/internal/validation_history.md`).
