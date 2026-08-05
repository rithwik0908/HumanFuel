"""Pytest fixtures: config + a de-identified synthetic gaze fixture (triview->dashboard->iPad)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aria_rig_calibration.config import load_study_config


@pytest.fixture(scope="session")
def cfg():
    return load_study_config(str(ROOT / "studies" / "so_pedestrian" / "study_config.yml"))


@pytest.fixture(scope="session")
def fixture_path():
    """A minimal de-identified fixture: three distinct 5 s holds (10 Hz) + 5 s task tail."""
    rng = np.random.default_rng(1)
    def hold(t0, yaw, pitch, n=50):
        t = t0 + np.arange(n) / 10
        return pd.DataFrame({"t": t, "ly": yaw + rng.normal(0, 0.002, n), "ry": yaw + rng.normal(0, 0.002, n),
                             "p": pitch + rng.normal(0, 0.002, n)})
    d = pd.concat([hold(0, 0.5, 0.0), hold(5, -0.3, -0.2), hold(10, 0.0, -0.5), hold(15, 0.4, 0.05)], ignore_index=True)
    df = pd.DataFrame({"tracking_timestamp_us": (d.t * 1e6).round().astype(int),
                       "left_yaw_rads_cpf": d.ly, "right_yaw_rads_cpf": d.ry, "pitch_rads_cpf": d.p, "depth_m": 1.0})
    fdir = ROOT / "tests" / "fixtures"; fdir.mkdir(parents=True, exist_ok=True)
    p = fdir / "synthetic_triview_dashboard_ipad_general_eye_gaze.csv"
    df.to_csv(p, index=False)
    return str(p)
