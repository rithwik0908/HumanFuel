# Troubleshooting

## Discovery is slow / seems to hang
Point `input_roots` at the participant data root, not the drive root. The engine prunes `.venv`,
`*_results*`, `site-packages`, `__pycache__`, `.Rlibs`, etc. (`discovery.PRUNE`), but a very broad
root still walks a lot. Prefer `--pids 1-37` over `--discover-all` when you know the range.

## "No files found" for a PID
Check the layout is one of the supported ones (README §10). Folder-vs-filename PID/trial mismatches
are **flagged in `inventory/ambiguous_files.csv`**, not silently guessed — inspect that file.

## Timestamp looks wrong (huge `rel_sec`)
The unit is inferred name-first (`_us`, `_ns`, `_ms`, `_s`), else by magnitude. If a column is named
generically and has unusual scale, add the correct candidate name/unit hint in the study config.

## Excel write fails / empty column widths
Fixed: all-NaN columns fall back to width 8. If `openpyxl` is missing, install it
(`pip install openpyxl`) — Excel export is otherwise skipped with a warning; CSVs still write.

## Metadata came back empty / got an HTML login page
The online tracker export returned non-`.xlsx` (401/HTML). Use `--offline-metadata` to force the local
`Participant Tracker-So Pedestrian.xlsx`. Metadata never affects scoring, so analysis still completes.

## Parity check reports a regression
Re-run `compare_with_r_reference.py`/`compare_with_original_python.py` and open the emitted
`*_parity.csv`. Confirm you compared the intended runs. The validated baseline is 85/85 (original
Python) and 125/125 windows + 37/37 status (R PID1–37).

## pytest can't import `aria_rig_calibration`
Run from the toolkit root, or `pip install -e .`. `conftest.py`/tests add `src/` to `sys.path`, but an
editable install is cleanest.

## `projectaria-tools` errors
It is optional (VRS/video only). CSV analysis does not need it; ignore install issues unless you use
the VRS helpers.
