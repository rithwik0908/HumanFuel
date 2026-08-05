# Internal validation tools

These scripts are **not required for normal operation** of the toolkit. They were used to validate
that the analysis reproduces the earlier reference implementations, and they require private reference
inputs that are not part of this repository.

## compare_with_original_python.py
Compares the toolkit against the original Python rig outputs (`calibration_window_detection.csv` for
PID1–6 and PID7–19).

```
python tools/internal_validation/compare_with_original_python.py \
  --study-config studies/so_pedestrian/study_config.local.yml \
  --data-root  <gaze data root> \
  --original-reference-root  <folder with the two original output subfolders> \
  --out <report dir>
# or set ARIA_ORIGINAL_REFERENCE_ROOT instead of --original-reference-root
```

## compare_with_r_reference.py
Compares a toolkit run folder against a verified R reference run folder (selected windows +
participant inventory).

```
python tools/internal_validation/compare_with_r_reference.py \
  --r-run <R reference run folder> \
  --python-run <toolkit run folder> \
  --out <report dir>
```

Both tools are read-only with respect to the reference data. See
`docs/internal/validation_history.md` for the recorded parity results.
