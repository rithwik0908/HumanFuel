"""Optional parity tests against the private dataset and reference runs.

These are marked ``local_parity`` and are NOT part of the default suite. Run them explicitly with
``pytest -m local_parity``. They skip cleanly when the required environment variables are unset:

    ARIA_PARITY_DATA_ROOT   - the private gaze data root
    ARIA_METADATA_FILE      - the Participant Tracker workbook (optional; metadata disabled if unset)
    ARIA_R_REFERENCE_RUN    - a verified R reference run folder to compare against
"""
import os
from pathlib import Path

import pandas as pd
import pytest

from aria_rig_calibration.models import RunOptions
from aria_rig_calibration.pipeline import run_pipeline
from tests.conftest import EXAMPLE_CONFIG

pytestmark = pytest.mark.local_parity

DATA = os.environ.get("ARIA_PARITY_DATA_ROOT")
RREF = os.environ.get("ARIA_R_REFERENCE_RUN")


@pytest.mark.skipif(not (DATA and RREF), reason="set ARIA_PARITY_DATA_ROOT and ARIA_R_REFERENCE_RUN")
def test_so_pedestrian_matches_reference(tmp_path):
    meta = os.environ.get("ARIA_METADATA_FILE")
    opts = RunOptions(study_config=str(EXAMPLE_CONFIG), data_root=DATA, output_root=str(tmp_path),
                      metadata_file=meta, metadata_mode="local" if meta else "none",
                      pids="1-37", trials="0-4")
    res = run_pipeline(opts)
    py = pd.read_csv(Path(res.run_root) / "windows" / "selected_windows.csv")
    r = pd.read_csv(Path(RREF) / "windows" / "selected_windows.csv")
    m = r.merge(py, on=["participant_id", "trial_number"], suffixes=("_r", "_py"))
    assert len(m) > 0
    assert (abs(m.calibration_start_sec_r - m.calibration_start_sec_py) < 1e-6).all()
    assert (abs(m.score_r - m.score_py) < 1e-3).all()
    assert (m.confidence_r == m.confidence_py).all()
