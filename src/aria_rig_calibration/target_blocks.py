"""Target-block characterisation.

Role in the pipeline
--------------------
Maps the temporal blocks of the selected calibration window to the study's configured targets (for
So Pedestrian: triview -> dashboard -> iPad) and computes, for each target, its centre and spread in
yaw/pitch angular space (the primary interpretation) and in the CPF gaze-ray x/y/z space, plus the
pairwise separation between every pair of targets.

The analysis is generic in the number of targets (``N >= 2``); pairwise combinations are enumerated
with :func:`itertools.combinations`. For ``N = 3`` the outputs match the original implementation.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


def _mad(v: np.ndarray) -> float:
    """Median absolute deviation of the finite values in ``v`` (NaN if none)."""
    v = v[np.isfinite(v)]
    return float(np.median(np.abs(v - np.median(v)))) if v.size else np.nan


def analyze_targets(sel: dict, cfg: dict, pid: int, trial_index: int) -> dict:
    """Compute per-target centres/spread and pairwise separations for one selected window.

    :param sel: selected-window dict from :func:`aria_rig_calibration.calibration.scan_windows`
        (provides ``blocks`` — a list of per-block DataFrames — and ``summaries`` — centroid/count/
        dispersion per block — and ``start``).
    :param cfg: merged config (``target`` mapping, ``calibration_search.window_length_sec``,
        ``target_blocks.minimum_samples_per_block``).
    :param pid: participant id (de-identified integer).
    :param trial_index: zero-based trial index (trial_number = trial_index + 1).
    :return: dict with ``blocks`` (per-target DataFrame) and ``pairwise`` (per-pair DataFrame).
        Angles are in degrees; depth in metres; x/y/z in CPF gaze-ray units.
    """
    targets = cfg["target"]["targets"]
    ids = [t["id"] for t in targets]
    names = [t["display_name"] for t in targets]
    n = len(sel["blocks"])
    blk_len = cfg["calibration_search"]["window_length_sec"] / n
    min_samples = cfg["target_blocks"].get("minimum_samples_per_block", 25)

    rows, centres = [], []
    for i, block in enumerate(sel["blocks"]):
        sm = sel["summaries"][i]
        yaw, pit, dep = block["yaw_deg"].to_numpy(), block["pitch_deg"].to_numpy(), block["depth_m"].to_numpy()
        med_yaw = float(np.nanmedian(yaw)) if len(block) else np.nan
        med_pit = float(np.nanmedian(pit)) if len(block) else np.nan
        # RMS angular distance of samples to the target's median direction (within-target spread).
        within = float(np.sqrt(np.nanmean((yaw - med_yaw) ** 2 + (pit - med_pit) ** 2))) if len(block) > 1 else np.nan
        centres.append({"yaw": med_yaw, "pitch": med_pit, "xyz": sm["centroid"]})
        rows.append(dict(
            participant_id=pid, trial_index=trial_index, trial_number=trial_index + 1,
            target_order=i + 1, target_id=ids[i], target_display_name=names[i],
            block_start_sec=sel["start"] + i * blk_len, block_end_sec=sel["start"] + (i + 1) * blk_len, duration_sec=blk_len,
            total_samples=sm["n"], valid_samples=int(len(block)),
            median_yaw_deg=round(med_yaw, 4) if len(block) else np.nan, mean_yaw_deg=round(float(np.nanmean(yaw)), 4) if len(block) else np.nan,
            sd_yaw_deg=round(float(np.nanstd(yaw, ddof=1)), 4) if len(block) > 1 else np.nan, mad_yaw_deg=round(_mad(yaw), 4),
            median_pitch_deg=round(med_pit, 4) if len(block) else np.nan, mean_pitch_deg=round(float(np.nanmean(pit)), 4) if len(block) else np.nan,
            sd_pitch_deg=round(float(np.nanstd(pit, ddof=1)), 4) if len(block) > 1 else np.nan, mad_pitch_deg=round(_mad(pit), 4),
            median_depth_m=round(float(np.nanmedian(dep)), 4) if np.isfinite(dep).any() else np.nan,
            mean_depth_m=round(float(np.nanmean(dep)), 4) if np.isfinite(dep).any() else np.nan, mad_depth_m=round(_mad(dep), 4),
            centroid_x=round(float(sm["centroid"][0]), 6), centroid_y=round(float(sm["centroid"][1]), 6), centroid_z=round(float(sm["centroid"][2]), 6),
            within_target_dispersion_deg=round(within, 4), xyz_dispersion=round(sm["disp_mean"], 6),
            qc_status="ok" if sm["n"] >= min_samples else "low_samples"))
    bdf = pd.DataFrame(rows)

    pr = []
    for a, b in combinations(range(n), 2):
        ca, cb = centres[a], centres[b]
        ang_sep = float(np.sqrt((ca["yaw"] - cb["yaw"]) ** 2 + (ca["pitch"] - cb["pitch"]) ** 2))
        xyz_sep = float(np.linalg.norm(np.asarray(ca["xyz"]) - np.asarray(cb["xyz"])))
        disp_ab = np.nanmean([bdf.within_target_dispersion_deg.iloc[a], bdf.within_target_dispersion_deg.iloc[b]])
        pr.append(dict(
            participant_id=pid, trial_index=trial_index, trial_number=trial_index + 1,
            target_a=ids[a], target_b=ids[b], yaw_diff_deg=round(ca["yaw"] - cb["yaw"], 4), pitch_diff_deg=round(ca["pitch"] - cb["pitch"], 4),
            angular_separation_deg=round(ang_sep, 4), xyz_separation=round(xyz_sep, 6),
            optional_depth_diff_m=round(float(bdf.median_depth_m.iloc[a] - bdf.median_depth_m.iloc[b]), 4),
            separation_to_dispersion_ratio=round(ang_sep / disp_ab, 3) if np.isfinite(disp_ab) and disp_ab > 0 else np.nan))
    return {"blocks": bdf, "pairwise": pd.DataFrame(pr)}
