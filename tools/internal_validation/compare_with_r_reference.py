#!/usr/bin/env python
"""Internal validation: compare a toolkit run against the verified R reference run.

NOT required for normal operation. Compares selected windows (start/end/score/block counts/confidence/
needs-review) and the participant inventory / administrative status. Read-only on both runs; never
modifies the reference.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--r-run", required=True)
    ap.add_argument("--python-run", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    rr, pr = Path(a.r_run), Path(a.python_run)
    out = Path(a.out) if a.out else pr / "validation"
    out.mkdir(parents=True, exist_ok=True)

    r_sel = pd.read_csv(rr / "windows" / "selected_windows.csv")
    p_sel = pd.read_csv(pr / "windows" / "selected_windows.csv")
    key = ["participant_id", "trial_number"]
    m = r_sel.merge(p_sel, on=key, suffixes=("_r", "_py"))
    rows = []
    for _, x in m.iterrows():
        start_m = abs(x.calibration_start_sec_r - x.calibration_start_sec_py) < 1e-6
        end_m = abs(x.calibration_end_sec_r - x.calibration_end_sec_py) < 1e-6
        score_m = abs(x.score_r - x.score_py) < 1e-3
        counts_m = (x.block_1_samples_r == x.block_1_samples_py and x.block_2_samples_r == x.block_2_samples_py and x.block_3_samples_r == x.block_3_samples_py)
        conf_m = x.confidence_r == x.confidence_py
        rev_m = x.needs_review_r == x.needs_review_py
        cls = "exact_match" if (start_m and end_m and counts_m and conf_m and rev_m) else ("tolerance_match" if start_m and counts_m and score_m else "regression")
        rows.append(dict(participant_id=int(x.participant_id), trial_number=int(x.trial_number),
                         r_start=x.calibration_start_sec_r, py_start=x.calibration_start_sec_py, start_match=start_m,
                         score_match=score_m, counts_match=counts_m, confidence_match=conf_m, needs_review_match=rev_m, status=cls))
    cmp = pd.DataFrame(rows)
    cmp.to_csv(out / "r_reference_parity.csv", index=False)

    r_inv = pd.read_csv(rr / "inventory" / "requested_participants.csv")
    p_inv = pd.read_csv(pr / "inventory" / "requested_participants.csv")
    inv_m = r_inv.merge(p_inv, on="participant_id", suffixes=("_r", "_py"))
    status_match = int((inv_m.final_participant_status_r == inv_m.final_participant_status_py).sum())

    n_ex = int((cmp.status == "exact_match").sum())
    n_reg = int((cmp.status == "regression").sum())
    (out / "r_reference_parity_report.md").write_text("\n".join([
        "# R-reference parity (internal validation)", "",
        f"R run: `{rr.name}`  |  Python run: `{pr.name}` (R results not modified)", "",
        f"- Overlapping selected windows compared: {len(cmp)}",
        f"- **Exact matches: {n_ex}/{len(cmp)}** | tolerance: {int((cmp.status == 'tolerance_match').sum())} | regressions: {n_reg}",
        f"- Participant-status agreement: {status_match}/{len(inv_m)}"]))
    print(f"R-reference parity: {n_ex}/{len(cmp)} exact windows, {n_reg} regressions; status {status_match}/{len(inv_m)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
