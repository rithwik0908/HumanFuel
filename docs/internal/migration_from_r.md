# Migration from R

This Python toolkit is a **controlled language migration** of the verified R
`aria_rig_calibration_toolkit`. The scientific method, configuration schema, output layout, and the
sliding-window algorithm are unchanged. Only the software language and ecosystem changed.

## Module map (R → Python)
| R (`R/*.R`) | Python (`src/aria_rig_calibration/*.py`) |
|---|---|
| `config.R` | `config.py` (`load_study_config`, `_deep_merge`, `expand_pid_spec`, `validate_config`) |
| `gaze_processing.R` | `gaze.py` (`resolve_columns`, `infer_time_unit`, `load_gaze`) |
| `legacy_sliding_window.R` | `legacy_sliding_window.py` (`summarize_points`, `scan_windows`, `review_status`) |
| `target_blocks.R` | `target_blocks.py` (`analyze_targets`) |
| `discovery.R` | `discovery.py` (`parse_pid_trial`, `reconcile`, `discover_files`, `apply_scope`, `PRUNE`) |
| `metadata.R` | `metadata.py` (`resolve_metadata`, `normalize_metadata`, `admin_status_for`) |
| `output_writer.R` | `output_writer.py`, `excel_writer.py` |
| `visualization.R` | `visualization.py` (matplotlib + plotly) |
| `scripts/run_analysis.R` | `scripts/run_analysis.py` |
| `scripts/compare_with_legacy_outputs.R` | `scripts/compare_with_original_python.py` |
| — | `scripts/compare_with_r_reference.py` (new: Python-vs-R parity) |

## Deliberate ecosystem swaps (behaviour preserved)
- `readr::read_csv` → `pandas.read_csv`; `data.frame` → `pandas.DataFrame`.
- `ggplot2 + svglite` → `matplotlib` (PNG/SVG/PDF); `plotly`/`htmlwidgets` → `plotly` (HTML).
- `openxlsx` → `openpyxl` (same sheet set, bold headers, frozen panes, filters, widths).
- `readxl` metadata read → `openpyxl`/`pandas`; the online-then-local metadata fallback (magic-byte
  `PK` check) is preserved.
- 1-based R indexing / inclusive `seq` → 0-based Python / half-open ranges — the window-start grid and
  block boundaries were checked to produce identical values.

## Parity evidence
- **85/85 exact** vs the original PID1–19 Python outputs (`scripts/compare_with_original_python.py`;
  artifact `aria_rig_calibration_results_python/original_python_parity/`).
- **125/125 exact selected windows, 0 regressions** and **37/37 participant-status agreement** vs the
  verified R PID1–37 run (`scripts/compare_with_r_reference.py`; artifact `<run>/validation/`).

## What was intentionally NOT changed
The score weights (4/80/25), the 0–35 s / 0.5 s / 15 s / 5 s grid, earliest-wins-ties, the High/Medium/
Low QC thresholds, the triview→dashboard→iPad mapping, the administrative-no-data accounting, and the
privacy exclusions. `legacy_reproduction` mode adds no new rejection logic.
