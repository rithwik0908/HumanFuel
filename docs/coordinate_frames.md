# Coordinate frames & depth

## Angular gaze space (primary)
The primary analysis lives in **yaw/pitch angular space**, derived directly from the Aria MPS
general-eye-gaze CSV in the **CPF (Central Pupil Frame)**:

- `yaw_rads = mean(left_yaw_rads_cpf, right_yaw_rads_cpf)` — combined yaw.
- `pitch_rads = pitch_rads_cpf`.
- Reported in degrees (`yaw_deg`, `pitch_deg`) for target centres, spread (SD/MAD), and pairwise
  angular separation.

## Gaze-ray points x/y/z (secondary)
For the legacy score and 3-D visualization, each sample is placed on a **gaze ray**:
```
x = depth · cos(pitch) · sin(yaw)
y = depth · sin(pitch)
z = depth · cos(pitch) · cos(yaw)
```
These are **CPF-relative gaze-ray points, NOT physical rig coordinates.** No rig/world transform is
applied; x/y/z are a direction (unit vector from yaw/pitch) scaled by `depth`. They must not be read
as "where the target is in the rig."

## Depth (exploratory QC only)
`depth_m` is the MPS **vergence** depth estimate — an eye-derived quantity, **not** a measured
screen-to-participant distance. It is used only as an exploratory QC signal and to scale the gaze-ray
points. When `depth_m` is absent, a unit depth is used and depth-based fields are reported as
exploratory/unavailable. Do not interpret depth as calibration ground truth.
