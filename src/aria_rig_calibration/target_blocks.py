"""Target-block analysis. Maps the three temporal window blocks to study targets
(So Pedestrian: triview -> dashboard -> iPad) and computes per-target and pairwise-separation
statistics in yaw/pitch angular space (primary) and the legacy CPF gaze-ray x/y/z space.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _mad(v: np.ndarray) -> float:
    v = v[np.isfinite(v)]
    return float(np.median(np.abs(v - np.median(v)))) if v.size else np.nan


def analyze_targets(sel: dict, cfg: dict, pid: int, trial_index: int) -> dict:
    """Per-target centres/dispersion + pairwise separation for the selected window."""
    targets = cfg["target"]["targets"]
    ids = [t["id"] for t in targets]
    names = [t["display_name"] for t in targets]
    blk_len = cfg["calibration_search"]["window_length_sec"] / len(sel["blocks"])
    rows, centres = [], []
    for i, c in enumerate(sel["blocks"]):
        sm = sel["summaries"][i]
        yaw, pit, dep = c["yaw_deg"].to_numpy(), c["pitch_deg"].to_numpy(), c["depth_m"].to_numpy()
        ang = (float(np.nanmedian(yaw)) if len(c) else np.nan, float(np.nanmedian(pit)) if len(c) else np.nan)
        within = float(np.sqrt(np.nanmean((yaw - ang[0]) ** 2 + (pit - ang[1]) ** 2))) if len(c) > 1 else np.nan
        centres.append({"yaw": ang[0], "pitch": ang[1], "xyz": sm["centroid"]})
        rows.append(dict(participant_id=pid, trial_index=trial_index, trial_number=trial_index + 1,
            target_order=i + 1, target_id=ids[i], target_display_name=names[i],
            block_start_sec=sel["start"] + i * blk_len, block_end_sec=sel["start"] + (i + 1) * blk_len, duration_sec=blk_len,
            total_samples=sm["n"], valid_samples=int(len(c)),
            median_yaw_deg=round(float(np.nanmedian(yaw)), 4) if len(c) else np.nan, mean_yaw_deg=round(float(np.nanmean(yaw)), 4) if len(c) else np.nan,
            sd_yaw_deg=round(float(np.nanstd(yaw, ddof=1)), 4) if len(c) > 1 else np.nan, mad_yaw_deg=round(_mad(yaw), 4),
            median_pitch_deg=round(float(np.nanmedian(pit)), 4) if len(c) else np.nan, mean_pitch_deg=round(float(np.nanmean(pit)), 4) if len(c) else np.nan,
            sd_pitch_deg=round(float(np.nanstd(pit, ddof=1)), 4) if len(c) > 1 else np.nan, mad_pitch_deg=round(_mad(pit), 4),
            median_depth_m=round(float(np.nanmedian(dep)), 4) if np.isfinite(dep).any() else np.nan,
            mean_depth_m=round(float(np.nanmean(dep)), 4) if np.isfinite(dep).any() else np.nan, mad_depth_m=round(_mad(dep), 4),
            centroid_x=round(float(sm["centroid"][0]), 6), centroid_y=round(float(sm["centroid"][1]), 6), centroid_z=round(float(sm["centroid"][2]), 6),
            within_target_dispersion_deg=round(within, 4), xyz_dispersion=round(sm["disp_mean"], 6),
            qc_status="ok" if sm["n"] >= cfg["target_blocks"].get("minimum_samples_per_block", 25) else "low_samples"))
    bdf = pd.DataFrame(rows)
    pr = []
    for a, b in [(0, 1), (0, 2), (1, 2)]:
        ca, cb = centres[a], centres[b]
        ang_sep = float(np.sqrt((ca["yaw"] - cb["yaw"]) ** 2 + (ca["pitch"] - cb["pitch"]) ** 2))
        xyz_sep = float(np.linalg.norm(np.asarray(ca["xyz"]) - np.asarray(cb["xyz"])))
        disp_ab = np.nanmean([bdf.within_target_dispersion_deg.iloc[a], bdf.within_target_dispersion_deg.iloc[b]])
        pr.append(dict(participant_id=pid, trial_index=trial_index, trial_number=trial_index + 1,
            target_a=ids[a], target_b=ids[b], yaw_diff_deg=round(ca["yaw"] - cb["yaw"], 4), pitch_diff_deg=round(ca["pitch"] - cb["pitch"], 4),
            angular_separation_deg=round(ang_sep, 4), xyz_separation=round(xyz_sep, 6),
            optional_depth_diff_m=round(float(bdf.median_depth_m.iloc[a] - bdf.median_depth_m.iloc[b]), 4),
            separation_to_dispersion_ratio=round(ang_sep / disp_ab, 3) if np.isfinite(disp_ab) and disp_ab > 0 else np.nan))
    return {"blocks": bdf, "pairwise": pd.DataFrame(pr)}
