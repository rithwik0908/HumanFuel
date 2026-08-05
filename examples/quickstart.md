# Quickstart

```powershell
# 1) Install
python -m pip install ".[dev]"

# 2) Configure paths (env vars, or edit a local config, or use CLI overrides)
Copy-Item studies\so_pedestrian\study_config.example.yml studies\so_pedestrian\study_config.local.yml
$env:ARIA_DATA_ROOT     = "D:\aria\participants"
$env:ARIA_OUTPUT_ROOT   = "D:\aria\results"
$env:ARIA_METADATA_FILE = "D:\aria\Participant Tracker.xlsx"   # only if metadata enabled
$S = "studies\so_pedestrian\study_config.local.yml"

# 3) Run
aria-rig-calibration --study-config $S --pids 35                    # one participant (smoke test)
aria-rig-calibration --study-config $S --pids 1-37 --trials 0-4     # full cohort
aria-rig-calibration --study-config $S --discover-all               # every discovered participant
```

Outputs land in `ARIA_OUTPUT_ROOT/run_<timestamp>_so_pedestrian_...`. Start with
`windows\selected_windows.csv`, `targets\target_centres.csv`,
`excel\aria_rig_calibration_analysis.xlsx`, and `plots\png\`.

## Without a tracker
```powershell
aria-rig-calibration --study-config $S --pids 35 --metadata-mode none --data-root D:\aria\participants --output-root D:\aria\results
```

## Tests
```powershell
pytest                    # portable tests
pytest -m local_parity    # optional; needs ARIA_PARITY_DATA_ROOT / ARIA_R_REFERENCE_RUN
```
