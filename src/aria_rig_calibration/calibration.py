"""Sliding-window calibration search.

Role in the pipeline
--------------------
Given a per-session *work* frame of gaze samples (relative time plus CPF gaze-ray points), scan every
candidate window, score it, and select the calibration window. Returns the full table of scanned
windows (for auditability) alongside the selected window and its QC review.

Scientific method (validated for the So Pedestrian study)
--------------------------------------------------------
* Candidate window starts: ``search_start_sec .. min(search_end_sec, duration - window_length)`` in
  ``window_step_sec`` steps.
* Each window is split into ``expected_count`` consecutive equal-duration blocks (three 5 s blocks for
  So Pedestrian). Block membership uses a half-open interval ``[block_start, block_end)`` so a sample
  exactly on a boundary belongs to exactly one block.
* Per block, over valid samples, compute the 3-D gaze-ray centroid, the sample count, and the mean
  distance of points to the centroid (dispersion).
* ``score = sum(counts) + min_counts_weight*min(counts) + min_dist_weight*min_pairwise_centroid_dist``
  ``- avg_disp_weight*avg_dispersion``.
* Select the maximum-score window; a strict ``>`` comparison keeps the earliest start on an exact tie.

The engine is generic in the number of blocks (``N >= 2``); pairwise centroid distances are taken over
all target pairs via :func:`itertools.combinations`. For ``N = 3`` the results and the
``all_scanned_windows`` schema are identical to the original validated implementation.

This module does NOT classify full-session gaze and introduces no additional rejection rule.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


def summarize_points(pts: np.ndarray) -> dict:
    """Summarise one block's 3-D gaze-ray points.

    :param pts: array of shape ``(n, 3)`` of ``(x, y, z)`` gaze-ray points (may contain NaN rows).
    :return: dict with ``n`` (int sample count), ``centroid`` (mean point, NaNs if empty),
             ``disp_mean`` and ``disp_median`` (mean/median Euclidean distance to the centroid).
    """
    if pts.shape[0] == 0:
        return {"n": 0, "centroid": np.array([np.nan, np.nan, np.nan]), "disp_mean": np.nan, "disp_median": np.nan}
    centroid = np.nanmean(pts, axis=0)
    d = np.linalg.norm(pts - centroid, axis=1)
    return {"n": int(pts.shape[0]), "centroid": centroid, "disp_mean": float(np.nanmean(d)), "disp_median": float(np.nanmedian(d))}


def _min_pairwise_distance(centroids: np.ndarray) -> float:
    """Minimum Euclidean distance between any two block centroids (0.0 if any centroid is undefined)."""
    if np.isnan(centroids).any() or len(centroids) < 2:
        return 0.0
    return float(min(np.linalg.norm(centroids[a] - centroids[b]) for a, b in combinations(range(len(centroids)), 2)))


def scan_windows(work: pd.DataFrame, cfg: dict) -> dict:
    """Scan all candidate windows and select the calibration window.

    :param work: DataFrame with columns ``rel_sec, x, y, z`` (plus yaw/pitch/depth); invalid rows are
        dropped internally. Times are in seconds relative to the first valid sample.
    :param cfg: merged config (``calibration_search`` + ``window_quality.scoring`` + ``cluster_qc`` +
        ``target_blocks``).
    :return: dict with ``all_windows`` (ranked DataFrame), ``selected`` (dict or None), ``review``
        (QC dict), and ``file_dispersion`` (whole-session dispersion, for QC context).
    """
    cs = cfg["calibration_search"]
    wq = cfg["window_quality"]["scoring"]
    nblk = int(cfg["target_blocks"].get("expected_count", 3))
    win = cs["window_length_sec"]
    step = cs["window_step_sec"]
    blk = win / nblk

    valid = np.isfinite(work["rel_sec"]) & np.isfinite(work["x"]) & np.isfinite(work["y"]) & np.isfinite(work["z"])
    d = work[valid].reset_index(drop=True)
    if len(d) == 0:
        return {"all_windows": pd.DataFrame(), "selected": None, "review": review_status(None, np.nan, cfg),
                "file_dispersion": np.nan, "reason": "no_valid_gaze"}

    xyz = d[["x", "y", "z"]].to_numpy()
    rel = d["rel_sec"].to_numpy()
    max_t = float(rel.max())
    # A complete candidate window must fit inside the recording. If the recording is shorter than one
    # window, scan nothing and report insufficient duration rather than scoring a partial window.
    if max_t < win:
        return {"all_windows": pd.DataFrame(), "selected": None, "review": review_status(None, np.nan, cfg),
                "file_dispersion": np.nan, "reason": "insufficient_duration"}
    # Last candidate start is capped both by search_end_sec and by the recording length.
    latest = min(cs["search_end_sec"], max(0.0, max_t - win))
    starts = np.arange(cs["search_start_sec"], latest + 1e-3, step)

    grand_centroid = np.nanmean(xyz, axis=0)
    file_disp = float(np.nanmean(np.linalg.norm(xyz - grand_centroid, axis=1)))

    rows: list[dict] = []
    best: dict | None = None
    for wid, s in enumerate(starts, start=1):
        summ = []
        for i in range(nblk):
            mask = (rel >= s + i * blk) & (rel < s + (i + 1) * blk)  # half-open [start, end)
            summ.append(summarize_points(xyz[mask]))
        counts = np.array([sm["n"] for sm in summ])
        centroids = np.array([sm["centroid"] for sm in summ])
        min_dist = _min_pairwise_distance(centroids)
        avg_disp = float(np.nanmean([sm["disp_mean"] for sm in summ]))
        if np.isnan(avg_disp):
            avg_disp = 999.0  # large penalty used by the standard method so empty windows cannot win
        score = counts.sum() + wq["min_counts_weight"] * counts.min() + wq["min_dist_weight"] * min_dist - wq["avg_disp_weight"] * avg_disp

        # Build the row preserving the original column order; per-block counts expand to N columns
        # (block_1..block_N), which is exactly block_1/2/3 for the three-target So Pedestrian study.
        row = {"window_id": wid, "window_start_sec": float(s), "window_end_sec": float(s + win),
               "valid_sample_count": int(counts.sum())}
        for i in range(nblk):
            row[f"block_{i + 1}_sample_count"] = int(counts[i])
        row.update({"min_block_count": int(counts.min()), "min_centroid_distance": min_dist,
                    "avg_dispersion": avg_disp, "sum_counts": int(counts.sum()), "score": float(score)})
        rows.append(row)

        # strict '>' keeps the earliest start on an exact score tie (validated behaviour)
        if best is None or score > best["score"]:
            blocks = [d[(rel >= s + i * blk) & (rel < s + (i + 1) * blk)].copy() for i in range(nblk)]
            best = {"start": float(s), "end": float(s + win), "score": float(score),
                    "summaries": summ, "min_dist": min_dist, "avg_disp": avg_disp,
                    "total_samples": int(counts.sum()), "blocks": blocks}

    aw = pd.DataFrame(rows)
    aw["input_sample_count"] = aw["valid_sample_count"]
    aw = aw.sort_values(["score", "window_start_sec"], ascending=[False, True]).reset_index(drop=True)
    aw["rank"] = np.arange(1, len(aw) + 1)
    aw["selected"] = aw["window_start_sec"] == best["start"]
    return {"all_windows": aw, "selected": best, "review": review_status(best, file_disp, cfg), "file_dispersion": file_disp}


def review_status(sel: dict | None, file_disp: float, cfg: dict) -> dict:
    """Assign QC review notes and a confidence label to the selected window.

    Notes accumulate for: too few total samples, too few samples in any block, a late window start,
    block centroids that are not clearly distinct (min pairwise distance below
    ``max(multiplier*avg_dispersion, minimum_separation)``), and window dispersion far above the
    whole-session dispersion. Confidence is ``High`` (0 notes), ``Medium`` (1), or ``Low`` (>= 2).

    :param sel: the selected-window dict from :func:`scan_windows`, or None if none was found.
    :param file_disp: whole-session dispersion for the "unusually high" comparison.
    :param cfg: merged config (``cluster_qc``).
    :return: dict with ``confidence`` (str), ``needs_review`` (bool), and ``notes`` (list[str]).
    """
    th = cfg["cluster_qc"]["review_thresholds"]
    if sel is None:
        return {"confidence": "Low", "needs_review": True, "notes": ["calibration window could not be selected"]}
    notes: list[str] = []
    if sel["total_samples"] < th["min_total_samples"]:
        notes.append(f"total calibration samples <{th['min_total_samples']} ({sel['total_samples']})")
    for i, sm in enumerate(sel["summaries"], start=1):
        if sm["n"] < th["min_chunk_samples"]:
            notes.append(f"chunk {i} has <{th['min_chunk_samples']} samples ({sm['n']})")
    if sel["start"] > th["late_start_sec"]:
        notes.append(f"selected calibration window starts after {th['late_start_sec']}s ({sel['start']:.2f})")
    mult = cfg["cluster_qc"]["dispersion_rule"]["multiplier"]
    floor = cfg["cluster_qc"]["minimum_separation"]
    threshold = max(sel["avg_disp"] * mult, floor)
    if sel["min_dist"] < threshold:
        notes.append(f"chunk centroids not clearly distinct (min distance {sel['min_dist']:.4f}, threshold {threshold:.4f})")
    if np.isfinite(file_disp) and sel["avg_disp"] > file_disp * mult:
        notes.append(f"calibration dispersion unusually high compared with file ({sel['avg_disp']:.4f} vs {file_disp:.4f})")
    conf = "High" if not notes else "Medium" if len(notes) == 1 else "Low"
    return {"confidence": conf, "needs_review": len(notes) > 0, "notes": notes}
