# The legacy sliding-window method (exact reproduction)

This is the algorithm from the original So Pedestrian rig-calibration Python scripts, reproduced
byte-for-behaviour in `src/aria_rig_calibration/legacy_sliding_window.py`. `legacy_reproduction` mode
does **not** add any new rejection logic (e.g. no new "no-calibration" reject); it is the baseline.

## Search
- Candidate window **start** times: `0, 0.5, 1.0, …` up to `min(35, duration − 15)` seconds
  (`search_start_sec=0`, `search_end_sec=35`, `window_step_sec=0.5`, `window_length_sec=15`).
  In code: `latest = min(search_end_sec, max(0, max_t − window)); starts = arange(0, latest+1e-3, step)`.
- Each 15 s window is split into **three consecutive 5 s blocks** (`n_blocks=3`, `block_length_sec=5`):
  `blocks[i] = rows where (start + i·5) ≤ rel_sec < (start + (i+1)·5)`.

## Per-block summary
For each block, over valid gaze samples, compute the 3-D gaze-ray centroid
(`x=depth·cos(pitch)·sin(yaw)`, `y=depth·sin(pitch)`, `z=depth·cos(pitch)·cos(yaw)`, with
`yaw=mean(left,right)`), the sample `count`, and a `dispersion` (mean distance of points to the block
centroid).

## Score (exact legacy weights)
```
score = sum(counts)
      + 4  · min(counts)              # min_counts_weight
      + 80 · min_centroid_distance    # min_dist_weight (min pairwise distance between the 3 centroids)
      - 25 · avg_dispersion           # avg_disp_weight (mean of the 3 block dispersions)
```
The **maximum-score** window is selected; on exact ties the **earliest** start wins (strict `>` when
scanning in ascending start order).

## Target mapping
Blocks map by time order to the configured targets. For So Pedestrian: block 1 → **triview**, block 2
→ **dashboard**, block 3 → **iPad** (the confirmed presentation order). Metadata (Williams Sequence,
LOD, admin status) is **never** used in scoring, selection, or QC.

## QC / confidence
Reviewer notes accumulate from: low sample counts, weak block distinctness (small min centroid
distance), and high dispersion. `High` = 0 notes, `Medium` = 1, `Low` = ≥2. Reported as
`Window Detection Confidence` and `needs_review`.

## Diagnostics
Every scanned window is written to `windows/all_scanned_windows.csv` with its component terms, so the
selection is fully auditable. `top_candidate_windows.csv` flags `multiple_similar_windows` when the
best and second-best scores are close (ambiguous timing).
