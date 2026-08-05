# Manual review guide

Each run writes `review/manual_review_manifest.csv` listing every session whose `needs_review` is true
(confidence not High) plus the reason. Use it to triage sessions for a human look.

## When to review
- **`selected_with_qc_warning`** — a window was chosen but QC raised ≥1 note (low counts, weak block
  distinctness, or high dispersion). Confirm the three holds look like triview→dashboard→iPad in the
  session plots.
- **`multiple_similar_windows`** — best and second-best scores are close; the *timing* is ambiguous.
  Check `windows/top_candidate_windows.csv` and the candidate-score curve plot; the true calibration
  may be the second candidate.
- **`weak_target_separation`** — the three centroids are close in gaze space; verify the participant
  actually fixated three distinct targets.
- **`insufficient_samples`** — sparse/short data in one or more blocks.
- **`no_valid_window`** — no usable 15 s window; the recording may lack the calibration sequence or be
  too short.
- **`administrative_no_data`** — not a scientific failure; no recording exists (see the inventory).

## How to review
1. Open `plots/png/<pid>_trial<t>_*.png` (yaw/pitch timeline with the selected window, target scatter,
   candidate-score curve).
2. Cross-check `windows/all_scanned_windows.csv` to see why the selected window won.
3. If the automatic choice is wrong, record the corrected window externally — **do not edit source
   CSVs or run outputs**. Re-running is deterministic, so document overrides in your own notes.

## What review does NOT change
The method is fixed and reproducible. Review flags sessions for human judgement; it never alters the
scoring, and metadata never influences it.
