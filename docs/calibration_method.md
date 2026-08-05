# Calibration-window detection method

This is the method implemented in `aria_rig_calibration.calibration`. It is validated for the
So Pedestrian study (three equal-duration targets).

## Search
- Candidate window **start** times: `search_start_sec .. min(search_end_sec, duration - window_length)`
  in `window_step_sec` steps (So Pedestrian: `0 .. min(35, duration-15)` in 0.5 s steps).
- Each `window_length_sec` window (15 s) is split into `expected_count` consecutive equal-duration
  blocks (three 5 s blocks). Block membership uses a half-open interval `[block_start, block_end)`, so
  a sample exactly on a boundary belongs to exactly one target block.

## Per-block summary
For each block, over valid gaze samples, compute the 3-D gaze-ray centroid, the sample count, and the
dispersion (mean distance of points to the block centroid). Gaze-ray points are
`x = depth·cos(pitch)·sin(yaw)`, `y = depth·sin(pitch)`, `z = depth·cos(pitch)·cos(yaw)` with
`yaw = mean(left, right)`.

## Score
```
score = sum(counts)
      + 4  · min(counts)              # min_counts_weight
      + 80 · min_centroid_distance    # min_dist_weight (min distance over all target-pair centroids)
      - 25 · avg_dispersion           # avg_disp_weight (mean of the block dispersions)
```
The **maximum-score** window is selected; on an exact tie the **earliest** start wins (strict `>`
while scanning in ascending start order). Pairwise centroid distances are taken over all target pairs,
so the method generalises to any target count `N >= 2` while reproducing the three-target result
exactly.

## Target mapping
Blocks map by time order to the configured targets. For So Pedestrian: block 1 → **triview/road**,
block 2 → **dashboard**, block 3 → **iPad**. Metadata (Williams Sequence, LOD, status) never affects
scoring, selection, or QC.

## QC / confidence
Review notes accumulate from: low total or per-block sample counts, a late window start, weak block
distinctness (small minimum centroid distance relative to `max(multiplier·avg_dispersion,
minimum_separation)`), and window dispersion far above the whole-session dispersion. Confidence is
`High` (0 notes), `Medium` (1), or `Low` (>= 2).

## Auditability
Every scanned window is written to `windows/all_scanned_windows.csv` with its component terms, so the
selection is fully reproducible. `windows/top_candidate_windows.csv` supports the
`multiple_similar_windows` flag when the best and second-best scores are close.

## Coordinate note
`x/y/z` are CPF-relative gaze-ray points that depth scales; they are **not** physical rig coordinates.
See `coordinate_frames.md`.
