# Validation history (internal)

This file records the provenance and parity evidence for the toolkit. It is internal context for
maintainers; the user-facing README does not foreground migration or parity numbers.

## Provenance
The analysis originated as a set of study-specific Python scripts, was reimplemented and generalised
as an R toolkit, and then ported to this Python package. Each step was validated to reproduce the
previous one's scientific outputs. The R toolkit and the original scripts are retained outside this
repository as archived references.

## Parity evidence
- **Original Python outputs (PID1–19):** the toolkit reproduces the original `select_window`
  selected start/end, chunk sample counts, chunk-mean X, confidence, and Needs-Review flags —
  **85/85 exact**, 0 regressions. Reproduce with
  `tools/internal_validation/compare_with_original_python.py`.
- **Verified R reference run (PID1–37):** selected windows (start/end/score/block counts/confidence/
  needs-review) match **125/125 exact**, 0 regressions, and participant/administrative status agrees
  **37/37**. Reproduce with `tools/internal_validation/compare_with_r_reference.py`.

## Preserved after the supervisor-release refactor
The `cleanup/supervisor-release` refactor (portability, packaging, privacy, generalisation, docs) was
verified to preserve both results exactly: re-running the So Pedestrian PID1–37 analysis with the
refactored pipeline reproduced **125/125** selected windows, **37/37** status, and **85/85** original-
Python parity. The scientific method (search grid, three 5 s blocks, score `4/80/25`, earliest-wins-
ties, High/Medium/Low QC, administrative no-data accounting) was not changed.

## Intentional output changes (non-scientific)
- Added generic `targets/window_target_block_metrics.csv` (long-format per-target metrics).
- Manifest replaced the previously unverified `source_files_modified: false` and
  `r_toolkit_modified` / `classification_pipeline_modified` booleans with a **verified**
  `source_files_unmodified` (`true`/`false`/`not_checked`) backed by SHA-256 before/after hashing; the
  unrelated R/classification claims were removed (those paths are not hashed).
- The manual-review manifest no longer force-includes a specific hardcoded PID.
- `selected_windows.csv` block-count columns are emitted as `block_1..N_samples`; for the three-target
  So Pedestrian study these remain exactly `block_1/2/3_samples`.

See `migration_from_r.md`, `final_migration_report.md`, and `legacy_method_original.md` for the fuller
historical record.
