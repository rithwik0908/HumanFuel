# Quickstart

```powershell
Set-Location 'E:\rithwikS2026\aria_rig_calibration_toolkit_python'
python -m pip install -e ".[dev]"

$S = 'studies\so_pedestrian\study_config.yml'

# 1) One participant (fast smoke test)
python scripts\run_analysis.py --study-config $S --pids 35

# 2) Full So Pedestrian cohort
python scripts\run_analysis.py --study-config $S --mode legacy_reproduction --pids 1-37 --trials 0-4 --refresh-metadata

# 3) All current + future PIDs, no code edits
python scripts\run_analysis.py --study-config $S --discover-all --refresh-metadata
```

Outputs land in `E:\rithwikS2026\aria_rig_calibration_results_python\run_<timestamp>_so_pedestrian_...`.
Start with `windows\selected_windows.csv`, `targets\centres.csv`,
`excel\aria_rig_calibration_analysis.xlsx`, and `plots\png\`.

## Verify parity
```powershell
python scripts\compare_with_original_python.py                    # -> 85/85 exact
python scripts\compare_with_r_reference.py `
  --r-run  'E:\rithwikS2026\aria_rig_calibration_results\run_20260805_095103_so_pedestrian_PID1_to_PID37' `
  --python-run '<your new python run folder>'                     # -> 125/125 windows, 37/37 status
```

## Run the tests
```powershell
pytest            # 12/12
```
