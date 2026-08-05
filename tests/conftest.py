"""Shared pytest fixtures and synthetic, de-identified data builders.

The suite uses only synthetic fixtures and never touches a private dataset, a participant tracker, or
the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aria_rig_calibration.config import load_study_config  # noqa: E402

EXAMPLE_CONFIG = ROOT / "studies" / "so_pedestrian" / "study_config.example.yml"


def synth_gaze_frame(seed: int = 1, holds=((0.0, 0.5, 0.0), (5.0, -0.3, -0.2), (10.0, 0.0, -0.5)),
                     tail_from: float = 15.0, hz: int = 10, hold_secs: int = 5) -> pd.DataFrame:
    """Build a synthetic gaze frame with distinct angular holds followed by a moving tail.

    Each hold is a steady yaw/pitch cluster (so the three blocks form separable centroids). The tail
    after the last hold sweeps, so the calibration window is the earliest three-hold span.
    """
    rng = np.random.default_rng(seed)
    parts = []
    for t0, yaw, pitch in holds:
        n = hz * hold_secs
        t = t0 + np.arange(n) / hz
        parts.append(pd.DataFrame({"t": t, "ly": yaw + rng.normal(0, 0.002, n), "ry": yaw + rng.normal(0, 0.002, n),
                                   "p": pitch + rng.normal(0, 0.002, n)}))
    n = hz * hold_secs
    t = tail_from + np.arange(n) / hz
    parts.append(pd.DataFrame({"t": t, "ly": 0.4 + rng.normal(0, 0.05, n), "ry": 0.4 + rng.normal(0, 0.05, n),
                               "p": 0.05 + rng.normal(0, 0.05, n)}))
    d = pd.concat(parts, ignore_index=True)
    return pd.DataFrame({"tracking_timestamp_us": (d.t * 1e6).round().astype(int),
                         "left_yaw_rads_cpf": d.ly, "right_yaw_rads_cpf": d.ry,
                         "pitch_rads_cpf": d.p, "depth_m": 1.0})


def write_session(root: Path, pid: int, trial: int, seed: int = 1, **kw) -> Path:
    """Write a synthetic ``general_eye_gaze.csv`` under a flat PID/trial layout and return its path."""
    d = root / f"PID_{pid}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"mps_{pid}-{trial}_vrs_general_eye_gaze.csv"
    synth_gaze_frame(seed=seed, **kw).to_csv(p, index=False)
    return p


@pytest.fixture(scope="session")
def cfg():
    """The merged So Pedestrian example config (three targets); used for pure-function unit tests."""
    return load_study_config(str(EXAMPLE_CONFIG))


@pytest.fixture
def fixture_path(tmp_path):
    """Path to a single synthetic three-hold gaze CSV."""
    p = tmp_path / "synthetic_general_eye_gaze.csv"
    synth_gaze_frame().to_csv(p, index=False)
    return str(p)


@pytest.fixture
def synthetic_dataset(tmp_path):
    """A synthetic data root: PID_1 (trials 0-2) and PID_99 (trial 0). Returns the root Path."""
    root = tmp_path / "data"
    for ti in (0, 1, 2):
        write_session(root, 1, ti, seed=10 + ti)
    write_session(root, 99, 0, seed=42)
    return root
