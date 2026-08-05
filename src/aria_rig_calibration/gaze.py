"""Gaze-signal processing.

Role in the pipeline
--------------------
Resolve the timestamp/yaw/pitch/depth columns from configurable candidate lists, normalise the
timestamp to seconds relative to the first valid sample, and build the CPF gaze-ray points used by the
scorer and the target analysis.

Scientific assumptions
----------------------
* Combined yaw is the mean of the present left/right CPF yaw columns.
* Gaze-ray points are ``x = depth*cos(pitch)*sin(yaw)``, ``y = depth*sin(pitch)``,
  ``z = depth*cos(pitch)*cos(yaw)``. These are **CPF-relative gaze-ray points, not physical rig
  coordinates**, and depth scales them.
* Depth handling: when the depth column is absent, unit depth is used (direction-only points). When
  individual depth values are missing (NaN), the corresponding x/y/z become NaN and those rows are
  treated as invalid gaze (dropped by ``valid_gaze``); they are not imputed.
* Timestamp unit is inferred name-first (``ns``/``us``/``ms``/``s`` in the column name), else by
  magnitude.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd


def resolve_columns(df: pd.DataFrame, cfg: dict) -> dict:
    """Resolve timestamp/yaw/pitch/depth columns from configured candidate lists (case-insensitive)."""
    low = {c.lower(): c for c in df.columns}
    cols = cfg["columns"]

    def pick(cands):
        for c in cands or []:
            if c.lower() in low:
                return low[c.lower()]
        return None

    ly, ry = pick(cols["left_yaw_candidates"]), pick(cols["right_yaw_candidates"])
    yaw_cols = [c for c in (ly, ry) if c]
    return {"timestamp": pick(cols["timestamp_candidates"]), "yaw_cols": yaw_cols,
            "pitch": pick(cols["pitch_candidates"]), "depth": pick(cols["depth_candidates"])}


def infer_time_unit(col_name: str | None, values: np.ndarray) -> tuple[float, str]:
    """Infer the timestamp unit using the established name-first, magnitude-second rule."""
    cl = (col_name or "").lower()
    if "ns" in cl:
        return 1e9, "nanoseconds_from_column_name"
    if "us" in cl or "micro" in cl:
        return 1e6, "microseconds_from_column_name"
    if "ms" in cl or "milli" in cl:
        return 1e3, "milliseconds_from_column_name"
    if cl in ("time_s", "seconds"):
        return 1.0, "seconds_from_column_name"
    finite = values[np.isfinite(values)]
    mag = np.abs(finite).max() if finite.size else np.nan
    if not np.isfinite(mag):
        return 1.0, "unknown"
    if mag > 1e14:
        return 1e9, "nanoseconds_inferred_from_magnitude"
    if mag > 1e11:
        return 1e6, "microseconds_inferred_from_magnitude"
    if mag > 1e8:
        return 1e3, "milliseconds_inferred_from_magnitude"
    return 1.0, "seconds_inferred_from_magnitude"


def load_gaze(path: str | Path, cfg: dict) -> dict:
    """Load a gaze CSV and build the work frame (CPF gaze-ray points + angular fields).

    :return: dict with ``work`` DataFrame, ``cols`` mapping, and ``meta`` (ts unit, coord source).
    """
    df = pd.read_csv(path)
    cols = resolve_columns(df, cfg)
    n = len(df)
    ts_raw = pd.to_numeric(df[cols["timestamp"]], errors="coerce").to_numpy() if cols["timestamp"] else np.full(n, np.nan)
    scale, unit = infer_time_unit(cols["timestamp"], ts_raw)
    finite_idx = np.where(np.isfinite(ts_raw))[0]
    first = ts_raw[finite_idx[0]] if finite_idx.size else np.nan
    rel = (ts_raw - first) / scale
    if cols["yaw_cols"]:
        yaw = np.nanmean(np.column_stack([pd.to_numeric(df[c], errors="coerce") for c in cols["yaw_cols"]]), axis=1)
    else:
        yaw = np.full(n, np.nan)
    pitch = pd.to_numeric(df[cols["pitch"]], errors="coerce").to_numpy() if cols["pitch"] else np.full(n, np.nan)
    depth_present = cols["depth"] is not None
    depth = pd.to_numeric(df[cols["depth"]], errors="coerce").to_numpy() if depth_present else np.ones(n)
    # CPF gaze-ray point (depth-scaled unit direction)
    x = depth * np.cos(pitch) * np.sin(yaw)
    y = depth * np.sin(pitch)
    z = depth * np.cos(pitch) * np.cos(yaw)
    work = pd.DataFrame({
        "source_row_number": np.arange(1, n + 1),
        "original_timestamp": df[cols["timestamp"]] if cols["timestamp"] else np.nan,
        "rel_sec": rel, "x": x, "y": y, "z": z,
        "yaw_rads": yaw, "pitch_rads": pitch,
        "yaw_deg": np.degrees(yaw), "pitch_deg": np.degrees(pitch),
        "depth_m": depth if depth_present else np.full(n, np.nan),
    })
    work["valid_gaze"] = np.isfinite(work["rel_sec"]) & np.isfinite(work["x"]) & np.isfinite(work["y"]) & np.isfinite(work["z"])
    coord_source = (f"approx_gaze_point_from_yaw_pitch_depth:{','.join(cols['yaw_cols'])},{cols['pitch']},{cols['depth']}"
                    if depth_present else f"unit_gaze_direction_from_yaw_pitch_no_depth:{','.join(cols['yaw_cols'])},{cols['pitch']}")
    return {"work": work, "cols": cols,
            "meta": {"ts_col": cols["timestamp"] or "", "ts_unit": unit, "coord_source": coord_source,
                     "depth_present": depth_present, "n_rows": n}}


def validate_schema(path: str | Path, rec: dict, cfg: dict) -> dict:
    """Schema/timestamp/quality report for one file (does not raise on bad files)."""
    try:
        g = load_gaze(path, cfg)
    except Exception as e:  # noqa: BLE001
        return {"participant_id": rec["participant_id"], "trial_index": rec["trial_index"],
                "source_path": str(path), "row_count": 0, "validation_status": "read_error", "exclusion_reason": str(e)}
    w = g["work"]; tv = w["rel_sec"][np.isfinite(w["rel_sec"])]
    req_ok = bool(g["cols"]["yaw_cols"]) and g["cols"]["pitch"] is not None and g["cols"]["timestamp"] is not None
    dt = float(np.median(np.diff(np.sort(tv)))) if len(tv) > 1 else np.nan
    return {"participant_id": rec["participant_id"], "trial_index": rec["trial_index"],
            "trial_number": rec["trial_index"] + 1, "source_path": str(path), "row_count": g["meta"]["n_rows"],
            "resolved_timestamp": g["meta"]["ts_col"], "resolved_left_yaw": (g["cols"]["yaw_cols"][:1] or [None])[0],
            "resolved_right_yaw": g["cols"]["yaw_cols"][1] if len(g["cols"]["yaw_cols"]) > 1 else None,
            "resolved_pitch": g["cols"]["pitch"], "resolved_depth": g["cols"]["depth"],
            "inferred_timestamp_unit": g["meta"]["ts_unit"],
            "session_duration_sec": round(float(tv.max() - tv.min()), 3) if len(tv) else np.nan,
            "median_sampling_interval_sec": round(dt, 5) if np.isfinite(dt) else np.nan,
            "estimated_rate_hz": round(1 / dt, 2) if np.isfinite(dt) and dt > 0 else np.nan,
            "missing_yaw": int((~np.isfinite(w["yaw_rads"])).sum()), "missing_pitch": int((~np.isfinite(w["pitch_rads"])).sum()),
            "missing_depth": int((~np.isfinite(w["depth_m"])).sum()) if g["meta"]["depth_present"] else None,
            "duplicate_timestamps": int(pd.Series(tv).duplicated().sum()), "non_monotonic": int((np.diff(tv) < 0).sum()),
            "validation_status": "ok" if (req_ok and w["valid_gaze"].sum() > 0) else "missing_columns",
            "exclusion_reason": (None if req_ok and w["valid_gaze"].sum() > 0 else "missing required or no valid rows")}
