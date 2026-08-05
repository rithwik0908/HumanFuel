"""Run-folder scaffolding, participant inventory (administrative status), and summaries."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from .config import expand_pid_spec
from .metadata import admin_status_for

SUBDIRS = ["manifest", "manifest/config_snapshot", "metadata_snapshot", "inventory", "validation",
           "windows", "targets", "diagnostics", "metadata", "summaries", "review", "excel",
           "plots/png", "plots/svg", "plots/pdf", "plots/html", "reports", "logs"]


def make_run_dir(cfg: dict, run_label: str | None = None, run_id: str | None = None, overwrite: bool = False) -> dict:
    if run_id is None:
        run_id = "run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + (f"_{run_label}" if run_label else "")
    root = Path(cfg["outputs"]["root"]) / run_id
    if root.exists() and not overwrite:
        raise FileExistsError(f"run folder exists (use --overwrite): {root}")
    for s in SUBDIRS:
        (root / s).mkdir(parents=True, exist_ok=True)
    paths = {s.replace("/", "_"): root / s for s in SUBDIRS}
    paths["run_root"] = root; paths["run_id"] = run_id
    return paths


def pid_folder_status_factory(cfg: dict, inv: pd.DataFrame):
    """Fast PID-folder presence from top-level dirs; data presence from the discovery inventory."""
    from .discovery import PRUNE
    cand: list[str] = []
    for r in cfg["input"]["roots"]:
        rp = Path(r)
        if not rp.is_dir():
            continue
        for l1 in [d for d in rp.iterdir() if d.is_dir() and not PRUNE.search(d.name)]:
            cand.append(l1.name)
            try:
                cand += [d.name for d in l1.iterdir() if d.is_dir() and not PRUNE.search(d.name)]
            except OSError:
                pass
    import re
    folder_pids = {int(m.group(1)) for n in cand if (m := re.match(r"^[Pp][Ii][Dd][_]?0*(\d+)$", n))}
    data_pids = set(inv.loc[inv.selected, "participant_id"].dropna().astype(int)) if not inv.empty else set()

    def fn(pid: int) -> dict:
        return {"folder_found": pid in folder_pids, "gaze_data_found": pid in data_pids,
                "empty_folder": pid in folder_pids and pid not in data_pids}
    return fn


def build_participant_inventory(cfg, inv, requested_pids, processed_pids, meta_tbl, status_map, folder_fn) -> pd.DataFrame:
    exp = list(cfg["trials"]["expected_indices"]); n_exp = len(exp)
    rows = []
    for pid in requested_pids:
        fs = folder_fn(pid)
        sel = inv[(inv.participant_id == pid) & (inv.in_scope == True)] if not inv.empty else inv  # noqa: E712
        dt = sorted(set(sel.trial_index.dropna().astype(int))) if len(sel) else []
        miss = [t for t in exp if t not in dt]
        succ = int(np.sum(np.array(processed_pids) == pid))
        trk, seqn = None, None
        if meta_tbl is not None and len(meta_tbl) and pid in set(meta_tbl.participant_id):
            mr = meta_tbl[meta_tbl.participant_id == pid].iloc[0]; trk, seqn = mr.participant_status, mr.sequence_number
        has = fs["gaze_data_found"]
        adm = admin_status_for(trk, has, status_map)
        final = adm if not has else ("invalid_data" if len(dt) == 0 else "processing_failed" if succ < len(dt)
                                     else "processed" if succ >= n_exp else "partial_data")
        rows.append(dict(participant_id=pid, pid_label=f"PID{pid}", folder_found=fs["folder_found"],
            folder_empty=fs["empty_folder"], gaze_files_found=has, expected_trials=n_exp, discovered_trials=len(dt),
            discovered_trial_indices=",".join(map(str, dt)), missing_trial_indices=",".join(map(str, miss)),
            processed_trials=succ, tracker_status=trk, normalized_admin_status=adm, sequence_number=seqn,
            final_participant_status=final))
    return pd.DataFrame(rows)


def build_summaries(selected: pd.DataFrame, blocks, pairwise, part_inv, cfg) -> dict:
    det = selected
    admin = part_inv[part_inv.final_participant_status.str.startswith("administrative_no_data")]
    n_exp = len(cfg["trials"]["expected_indices"])
    overall = pd.DataFrame({"metric": ["recorded_pids", "administrative_no_data_pids", "partial_data_pids",
        "recorded_sessions", "selected_windows", "needs_review_sessions", "theoretical_sessions", "administrative_unrecorded_sessions"],
        "value": [int(part_inv.gaze_files_found.sum()), len(admin), int((part_inv.final_participant_status == "partial_data").sum()),
                  len(det), int((det.window_selected == True).sum()), int((det.needs_review == "Yes").sum()),  # noqa: E712
                  len(expand_pid_spec(cfg["participants"]["include"])) * n_exp, len(admin) * n_exp]})

    def grp(by):
        if by not in det.columns:
            return None
        g = det.groupby(by)
        return pd.DataFrame({by: list(g.groups.keys()), "n_sessions": g.size().values,
            "median_start_sec": g.calibration_start_sec.median().round(2).values,
            "pct_needs_review": (g.apply(lambda x: (x.needs_review == "Yes").mean() * 100, include_groups=False)).round(1).values})
    return {"overall": overall, "participant": grp("participant_id"), "trial": grp("trial_number"),
            "lod": grp("lod"), "williams": grp("sequence_number"),
            "timing": det[["participant_id", "trial_number", "calibration_start_sec", "calibration_end_sec", "confidence", "needs_review"]],
            "qc": det.exploratory_result.value_counts().rename_axis("exploratory_result").reset_index(name="count")}
