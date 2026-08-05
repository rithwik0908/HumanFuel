# Coordinate frames & depth

## Angular gaze space (primary interpretation)
The primary interpretation is **yaw/pitch angular space**, taken from the Aria MPS general-eye-gaze
CSV in the **CPF (Central Pupil Frame)**:

- `yaw_rads = mean(left_yaw_rads_cpf, right_yaw_rads_cpf)` — combined yaw.
- `pitch_rads = pitch_rads_cpf`.
- Reported in degrees (`yaw_deg`, `pitch_deg`) for target centres, spread (SD/MAD), and pairwise
  angular separation.

## Gaze-ray points x/y/z
Each sample is placed on a **depth-scaled gaze ray**:
```
x = depth · cos(pitch) · sin(yaw)
y = depth · sin(pitch)
z = depth · cos(pitch) · cos(yaw)
```

> The calibration-window detector calculates depth-scaled CPF-relative gaze-ray points from yaw,
> pitch, and depth. These points are used in the centroid-separation and dispersion components of the
> candidate-window score. They are **not physical rig coordinates** and no rig transformation is
> applied.

So depth is **not** an output-only QC variable: when present it participates in the score through the
gaze-ray points. Yaw and pitch remain available as the primary angular interpretation, and `x/y/z`
must never be called physical screen coordinates.

## Depth handling
- **Depth column absent:** unit depth is used, so the points become gaze *directions* (still valid for
  centroid separation and dispersion, just unscaled).
- **Individual depth values missing (NaN):** the corresponding `x/y/z` become NaN and those rows are
  treated as invalid gaze and dropped by `valid_gaze`. Missing depth values are **not** imputed and
  the rows are **not** kept with a substitute depth.
- Depth (`depth_m`) is the MPS **vergence** estimate — an eye-derived quantity, **not** a measured
  screen-to-participant distance. Do not interpret it as calibration ground truth.
