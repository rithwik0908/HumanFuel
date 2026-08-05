"""Legacy sliding-window calibration search (``legacy_reproduction`` mode).

Direct port of the original So Pedestrian ``select_window`` + ``review_status``. Scans every 15 s
window (start 0..min(35, duration-15), step 0.5 s), splits into three 5 s blocks, scores them, and
selects the max-score window (earliest on tie). Returns ALL scanned windows plus the selected one.
Does NOT classify full-session gaze, and introduces NO new no-calibration rejection rule.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def summarize_points(pts: np.ndarray) -> dict:
    """Centroid + dispersion of a block's (x,y,z) points (mean/median distance to centroid)."""
    if pts.shape[0] == 0:
        return {"n": 0, "centroid": np.array([np.nan, np.nan, np.nan]), "disp_mean": np.nan, "disp_median": np.nan}
    centroid = np.nanmean(pts, axis=0)
    d = np.linalg.norm(pts - centroid, axis=1)
    return {"n": int(pts.shape[0]), "centroid": centroid, "disp_mean": float(np.nanmean(d)), "disp_median": float(np.nanmedian(d))}


def scan_windows(work: pd.DataFrame, cfg: dict) -> dict:
    """Scan all candidate windows and select the legacy calibration window.

    :param work: DataFrame with rel_sec, x, y, z, yaw_deg, pitch_deg, depth_m (any rows; invalid dropped).
    :param cfg: config (calibration_search + window_quality.scoring + cluster_qc + target_blocks).
    :return: dict(all_windows: DataFrame, selected: dict|None, review: dict|None, file_dispersion: float).
    """
    cs = cfg["calibration_search"]; wq = cfg["window_quality"]["scoring"]
    nblk = cfg["target_blocks"].get("expected_count", 3)
    win = cs["window_length_sec"]; step = cs["window_step_sec"]; blk = win / nblk
    d = work[np.isfinite(work["rel_sec"]) & np.isfinite(work["x"]) & np.isfinite(work["y"]) & np.isfinite(work["z"])].reset_index(drop=True)
    if len(d) == 0:
        return {"all_windows": pd.DataFrame(), "selected": None, "review": review_status(None, np.nan, cfg), "file_dispersion": np.nan}
    xyz = d[["x", "y", "z"]].to_numpy()
    rel = d["rel_sec"].to_numpy()
    max_t = float(rel.max())
    latest = min(cs["search_end_sec"], max(0.0, max_t - win))
    starts = np.arange(cs["search_start_sec"], latest + 1e-3, step)
    gc = np.nanmean(xyz, axis=0)
    file_disp = float(np.nanmean(np.linalg.norm(xyz - gc, axis=1)))
    rows = []
    best = None
    for wid, s in enumerate(starts, start=1):
        summ = []
        for i in range(nblk):
            mask = (rel >= s + i * blk) & (rel < s + (i + 1) * blk)
            summ.append(summarize_points(xyz[mask]))
        counts = np.array([sm["n"] for sm in summ])
        cent = np.array([sm["centroid"] for sm in summ])
        if not np.isnan(cent).any():
            pair = [np.linalg.norm(cent[0] - cent[1]), np.linalg.norm(cent[0] - cent[2]), np.linalg.norm(cent[1] - cent[2])]
            min_dist = float(min(pair))
        else:
            min_dist = 0.0
        avg_disp = float(np.nanmean([sm["disp_mean"] for sm in summ]))
        if np.isnan(avg_disp):
            avg_disp = 999.0
        score = counts.sum() + wq["min_counts_weight"] * counts.min() + wq["min_dist_weight"] * min_dist - wq["avg_disp_weight"] * avg_disp
        rows.append({"window_id": wid, "window_start_sec": float(s), "window_end_sec": float(s + win),
                     "valid_sample_count": int(counts.sum()), "block_1_sample_count": int(counts[0]),
                     "block_2_sample_count": int(counts[1]), "block_3_sample_count": int(counts[2]),
                     "min_block_count": int(counts.min()), "min_centroid_distance": min_dist,
                     "avg_dispersion": avg_disp, "sum_counts": int(counts.sum()), "score": float(score)})
        # strict '>' keeps the earliest start on ties (legacy behaviour)
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
    review = review_status(best, file_disp, cfg)
    return {"all_windows": aw, "selected": best, "review": review, "file_dispersion": file_disp}


def review_status(sel: dict | None, file_disp: float, cfg: dict) -> dict:
    """Legacy QC / confidence for the selected window (ports ``review_status``)."""
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
