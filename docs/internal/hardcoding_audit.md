# Hardcoding & portability audit (Phase 1)

Baseline commit: `a8691625468ea8305ae5c6a6cd5a198e952d45ca` (branch `cleanup/supervisor-release`).
This audit records the state found before the supervisor-release cleanup. Per-item completion is
tracked in `hardcoding_inventory.csv` (`action_completed`) and in
`supervisor_release_validation.md`.

## Machine-specific paths (harmful — must be removed from user-facing files)
- `config/default_config.yml` → `outputs.root: "E:/rithwikS2026/aria_rig_calibration_results_python"`.
- `studies/so_pedestrian/study_config.yml` → `input.roots` (`E:/rithwikS2026`, `E:/rithwikS2026/eye tracking`),
  `metadata.local` (Participant Tracker absolute path), `outputs.root`, `legacy_comparison.reference_outputs`
  (original-Python output CSVs).
- `studies/example_study/study_config.yml` → `input.roots`, `outputs.root` (placeholder `E:/some_other_project`).
- `scripts/run_analysis.py` → `sys.path.insert` of a repository-relative `src` path (works but is a
  script-location dependency; the installed command must not rely on it).
- `tests/test_core.py` → absolute `E:\rithwikS2026\...` paths for the original-Python parity spot-check
  (`test_original_python_parity`) and `E:\rithwikS2026\rerun_tests\rerun_env` python used to run tests.
- `src/aria_rig_calibration/discovery.py` → `PRUNE` regex lists project-specific folder names
  (`rerun_env`, `.Rlibs`, `aria_rig_calibration_results`); harmless but study-flavoured.

## Fixed PID / trial ranges (study-specific configuration, not code)
- `studies/so_pedestrian/study_config.yml` → `participants.include: ["1-37"]`, `run_label:
  so_pedestrian_PID1_to_PID37`. Correct location (config), but the run label must reflect discovered
  scope when `--discover-all` finds later PIDs (Phase 9).

## Migration / parity / "legacy" terminology in user-facing files
- `README.md`, `CHANGELOG.md`, `pyproject.toml` description, `docs/legacy_method.md`,
  `docs/migration_from_r.md`, `docs/final_migration_report.md`, module docstrings, and the run manifest
  (`mode: legacy_reproduction`) foreground R migration and parity numbers (85/85, 125/125, 37/37).
  Move to internal docs; keep neutral method wording user-facing (Phases 19–20).

## Hardcoded target names / fixed three-target indexing in generic modules
- `src/aria_rig_calibration/visualization.py` → `TARGET_COL` hardcodes So Pedestrian colours; block
  boundary lines hardcode `start+5`, `start+10` (three blocks).
- `src/aria_rig_calibration/legacy_sliding_window.py` → emits `block_1/2/3_sample_count`; `counts[0..2]`,
  `cent[0..2]`, explicit 3-pair min-distance.
- `src/aria_rig_calibration/target_blocks.py` → explicit pairwise list `[(0,1),(0,2),(1,2)]`.
- `scripts/run_analysis.py` → `s["summaries"][0..2]`, `block_1/2/3_samples`.
- `studies/example_study` advertises **two** targets but the engine assumes three → non-functional
  example (Phase 8).

## Inaccurate / unverified claims
- Depth described as "QC/exploratory only" in README/docs, but depth **scales the x/y/z gaze-ray points
  used in the score's centroid-separation and dispersion terms** → inaccurate (Phase 7).
- Privacy: "names/emails/… are never read" while the whole tracker workbook is loaded by
  `pandas.ExcelFile` → the workbook *is* read; only sanitised fields should be *retained* (Phase 10).
- Manifest writes `source_files_modified: false`, `r_toolkit_modified: false`,
  `classification_pipeline_modified: false` without hashing anything → unverified claims (Phase 14).
- Excel validation compares only row/column counts and passes empty sheets → too weak (Phase 15).

## Unused / documentation-only configuration
- `input.accepted_file_patterns`, `input.accepted_folder_patterns`, `input.recursive`,
  `input.duplicate_policy` — discovery hardcodes the `general_eye_gaze.csv` pattern and always
  excludes-and-flags duplicates; these keys are not read.
- `metadata.source_priority`, `metadata.sheet`, `metadata.preferred_gid` — not read
  (sheet selection is by `candidate_sheets_contain` / header match).
- `metadata_mapping.forbidden_tokens` / `candidate_sheets_contain` — declared but not enforced.
- `target_blocks.expected_duration_sec`, `target_blocks.block_definition`, `window_quality.metrics`,
  `window_quality.scoring.formula`, `window_quality.thresholds.sample_qc_reference` — informational only.
- `integrity.hash_sources`, `integrity.compare_legacy_outputs`, `integrity.preserve_sources` — declared,
  never acted on.
- `gaze.combined_yaw_method`, `gaze.angle_output_unit`, `timestamps.*`, `depth.enabled/role` —
  informational; behaviour is fixed in code.

## Output flags ignored
- `outputs.png/svg/pdf/html` are only partly honoured: `do_plots` gates on `png` alone; HTML is written
  whenever plotly imports regardless of `html: false` (Phase 13).

## CLI issues
- `--mode` accepts an arbitrary string but only `legacy_reproduction` exists.
- Metadata is controlled by two overlapping flags (`--refresh-metadata`, `--offline-metadata`) rather
  than a single `--metadata-mode` (Phase 16).

## Test-suite portability
- Default `pytest` imports succeed offline, but `test_original_python_parity` requires the private
  `E:\rithwikS2026` dataset → must move to an opt-in `local_parity` marker (Phase 17).
