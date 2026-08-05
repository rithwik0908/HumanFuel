# Troubleshooting

## "ARIA_DATA_ROOT is not set" (or ARIA_OUTPUT_ROOT / ARIA_METADATA_FILE)
Provide the path by setting the environment variable, passing the CLI override (`--data-root`,
`--output-root`, `--metadata-file`), or editing your `study_config.local.yml`. See
[configuration.md](configuration.md). If you do not have a tracker, run with `--metadata-mode none`.

## Discovery is slow / seems to hang
Point `input.roots` (or `--data-root`) at the participant data root, not a whole drive. Discovery
prunes virtual-envs, results folders, `site-packages`, `__pycache__`, etc., but a very broad root
still walks a lot. Prefer `--pids 1-37` over `--discover-all` when you know the range.

## "No files found" for a PID
Confirm the layout is supported (README "Inputs"). Folder-vs-filename PID/trial disagreements are
**flagged in `inventory/ambiguous_files.csv`**, not guessed — inspect that file.

## Timestamp looks wrong (huge `rel_sec`)
The unit is inferred name-first (`_us`/`_ns`/`_ms`/`_s`), else by magnitude. If a timestamp column is
generically named and unusually scaled, add the correct candidate name in the study config `columns`.

## Metadata came back empty / online export failed
The online export needs auth; the toolkit falls back to the local file (`--metadata-mode auto`). Use
`--metadata-mode local` to require the local workbook, or `none` to disable metadata (analysis still
completes — metadata never affects scoring).

## Excel run aborted with "forbidden columns"
A sheet contained a column whose header matched a personal-data token (`forbidden_tokens`). This is the
privacy guard. The toolkit's own analytic columns (e.g. `notes`, `target_display_name`) are
allow-listed; if you added a custom column with a personal-data-like name, rename it.

## Output formats
Set `outputs.{png,svg,pdf,html}` independently. HTML aggregate plots also require the optional
`plotly` extra (`pip install ".[reports]"`); without it the HTML is skipped and other outputs proceed.

## `pytest` can't import `aria_rig_calibration` or `tests`
Run from the repository root, or `pip install -e ".[dev]"`. The default suite excludes `local_parity`
and `network` markers; opt in with `pytest -m local_parity` (requires the private dataset env vars).

## `projectaria-tools` errors
It is optional (VRS/video only). CSV analysis does not need it.
