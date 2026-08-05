"""Run-folder scaffolding, participant inventory, and cohort summaries.

Role in the pipeline
--------------------
Create the timestamped run directory tree, build the per-participant inventory (including
administrative no-data accounting that never guesses status), and derive the cohort summary tables.
The *reporting scope* is the union of explicitly requested PIDs and, when ``--discover-all`` is used,
every discovered PID — so newly added participants (e.g. PID38+) appear in the inventory, summaries,
and denominators without any code change.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .metadata import admin_status_for

SUBDIRS = ["manifest", "manifest/config_snapshot", "metadata_snapshot", "inventory", "validation",
           "windows", "targets", "diagnostics", "metadata", "summaries", "review", "excel",
           "plots/png", "plots/svg", "plots/pdf", "plots/html", "reports", "logs"]

#: Fallback administrative-status mapping for studies that deliberately omit metadata/status mapping.
DEFAULT_STATUS_MAP = {"cancelled": "administrative_no_data_cancelled",
                      "rescheduled": "administrative_no_data_rescheduled",
                      "not collected": "administrative_no_data_not_collected",
                      "pending": "administrative_no_data_pending_upload",
                      "completed": "completed",
                      "default_when_no_data": "administrative_no_data_status_unknown"}


def scope_run_label(base_label: str | None, reporting_pids: list[int], discover_all: bool) -> str:
    """Build a run label that reflects the actual reporting scope.

    :param base_label: the study's configured ``run_label`` (or None).
    :param reporting_pids: the sorted list of PIDs being reported on.
    :param discover_all: whether discovery scope was used.
    :return: e.g. ``so_pedestrian_PID1_to_PID38`` or ``so_pedestrian_discovered_37PIDs``.
    """
    base = base_label or "run"
    if not reporting_pids:
        return base
    lo, hi = reporting_pids[0], reporting_pids[-1]
    contiguous = reporting_pids == list(range(lo, hi + 1))
    if discover_all:
        return f"{base}_discovered_{len(reporting_pids)}PIDs"
    return f"{base}_PID{lo}_to_PID{hi}" if contiguous else f"{base}_{len(reporting_pids)}PIDs"


def _safe_delete_run_dir(root: Path, out_root: Path) -> None:
    """Delete exactly one resolved run directory, refusing anything that isn't a child of out_root.

    Guards against deleting the output root itself, a parent directory, a filesystem root, or an
    unresolved/empty path.
    """
    root_r, out_r = root.resolve(), out_root.resolve()
    if not root_r.name or root_r == out_r or root_r == Path(root_r.anchor) or len(root_r.parts) <= 1:
        raise ValueError(f"refusing to delete unsafe run directory: {root_r}")
    if root_r.parent != out_r:
        raise ValueError(f"refusing to delete a run directory outside the output root: {root_r}")
    shutil.rmtree(root_r)


def make_run_dir(cfg: dict, run_label: str | None = None, run_id: str | None = None, overwrite: bool = False) -> dict:
    """Create the run directory tree under ``outputs.root`` and return a path map.

    Without ``overwrite`` an existing run directory raises ``FileExistsError``. With ``overwrite`` the
    exact existing run directory is deleted completely and recreated clean, so no stale windows, plots,
    Excel files, logs, or summaries survive (see :func:`_safe_delete_run_dir` for the safety guards).

    :param cfg: merged config (``outputs.root`` must be resolved).
    :param run_label: label appended to the auto-generated run id.
    :param run_id: explicit run id (skips timestamp generation) when provided.
    :param overwrite: replace an existing run folder.
    :return: dict mapping each subdir key to its Path, plus ``run_root`` and ``run_id``.
    """
    if run_id is None:
        run_id = "run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + (f"_{run_label}" if run_label else "")
    out_root = Path(cfg["outputs"]["root"])
    root = out_root / run_id
    if root.exists():
        if not overwrite:
            raise FileExistsError(f"run folder exists (use --overwrite): {root}")
        _safe_delete_run_dir(root, out_root)
    for s in SUBDIRS:
        (root / s).mkdir(parents=True, exist_ok=True)
    paths = {s.replace("/", "_"): root / s for s in SUBDIRS}
    paths["run_root"] = root
    paths["run_id"] = run_id
    return paths


def pid_folder_status_factory(cfg: dict, inv: pd.DataFrame):
    """Return a function ``pid -> {folder_found, gaze_data_found, empty_folder}``.

    Folder presence is read from the top two directory levels under each input root; data presence
    comes from the discovery inventory (a folder with no discoverable gaze file is an admin case).
    """
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
    folder_pids = {int(m.group(1)) for n in cand if (m := re.match(r"^[Pp][Ii][Dd][_]?0*(\d+)$", n))}
    data_pids = set(inv.loc[inv.selected, "participant_id"].dropna().astype(int)) if not inv.empty else set()

    def fn(pid: int) -> dict:
        return {"folder_found": pid in folder_pids, "gaze_data_found": pid in data_pids,
                "empty_folder": pid in folder_pids and pid not in data_pids}
    return fn


def build_participant_inventory(cfg, inv, reporting_pids, session_status, meta_tbl, status_map, folder_fn,
                                validation_only: bool = False, valid_pids: set | None = None) -> pd.DataFrame:
    """Build one inventory row per reporting PID from explicit per-session outcomes.

    Participant status distinguishes schema-invalid data from processing failures using the
    per-session status rows (``processed`` / ``invalid_data`` / ``processing_failed`` / ``no_window``),
    not merely the count of processed sessions.

    :param session_status: list of dicts with ``participant_id``, ``trial_index``, ``status``.
    :param validation_only: when True, analysis was skipped; valid data -> ``validation_only``,
        schema-invalid data -> ``invalid_data``, no data -> administrative status.
    :param valid_pids: PIDs with >= 1 schema-valid file (validation-only mode only).
    :return: DataFrame with ``final_participant_status`` and per-session counts per participant.
    """
    exp = list(cfg["trials"]["expected_indices"])
    n_exp = len(exp)
    valid_pids = valid_pids or set()
    status_by_pid: dict[int, list[str]] = {}
    for r in (session_status or []):
        status_by_pid.setdefault(int(r["participant_id"]), []).append(r["status"])
    rows = []
    for pid in reporting_pids:
        fs = folder_fn(pid)
        sel = inv[(inv.participant_id == pid) & (inv.in_scope == True)] if not inv.empty else inv  # noqa: E712
        dt = sorted(set(sel.trial_index.dropna().astype(int))) if len(sel) else []
        miss = [t for t in exp if t not in dt]
        sts = status_by_pid.get(pid, [])
        n_processed = sts.count("processed")
        n_invalid = sts.count("invalid_data")
        n_exc = sts.count("processing_failed")
        n_no_window = sts.count("no_window")
        n_schema_valid = n_processed + n_exc + n_no_window
        trk, seqn = None, None
        if meta_tbl is not None and len(meta_tbl) and pid in set(meta_tbl.participant_id):
            mr = meta_tbl[meta_tbl.participant_id == pid].iloc[0]
            trk, seqn = mr.participant_status, mr.sequence_number
        has = fs["gaze_data_found"]
        adm = admin_status_for(trk, has, status_map)
        if not has:
            final = adm
        elif validation_only:
            final = "validation_only" if pid in valid_pids else "invalid_data"
        elif len(sts) == 0 or n_schema_valid == 0:
            final = "invalid_data"                       # data present but nothing schema-valid ran
        elif n_exc > 0:
            final = "processing_failed"                  # a schema-valid session raised
        elif n_processed == 0:
            final = "no_valid_window"                    # schema-valid but no complete window (e.g. short)
        else:
            final = "processed" if n_processed >= n_exp else "partial_data"
        rows.append(dict(participant_id=pid, pid_label=f"PID{pid}", folder_found=fs["folder_found"],
                         folder_empty=fs["empty_folder"], gaze_files_found=has, expected_trials=n_exp,
                         discovered_sessions=len(dt), discovered_trial_indices=",".join(map(str, dt)),
                         missing_trial_indices=",".join(map(str, miss)),
                         schema_valid_sessions=n_schema_valid, schema_invalid_sessions=n_invalid,
                         processing_failed_sessions=n_exc, no_window_sessions=n_no_window,
                         processed_trials=n_processed, tracker_status=trk, normalized_admin_status=adm,
                         sequence_number=seqn, final_participant_status=final))
    return pd.DataFrame(rows)


def build_summaries(selected: pd.DataFrame, blocks, pairwise, part_inv, cfg) -> dict:
    """Derive cohort summary tables from the selected-window and inventory frames.

    Denominators use the reporting scope (``len(part_inv)``), so discover-all runs count discovered
    participants correctly.
    """
    det = selected
    admin = part_inv[part_inv.final_participant_status.str.startswith("administrative_no_data")]
    n_exp = len(cfg["trials"]["expected_indices"])
    overall = pd.DataFrame({"metric": ["reporting_pids", "recorded_pids", "administrative_no_data_pids",
        "partial_data_pids", "recorded_sessions", "selected_windows", "needs_review_sessions",
        "theoretical_sessions", "administrative_unrecorded_sessions"],
        "value": [len(part_inv), int(part_inv.gaze_files_found.sum()), len(admin),
                  int((part_inv.final_participant_status == "partial_data").sum()),
                  len(det), int((det.window_selected == True).sum()), int((det.needs_review == "Yes").sum()),  # noqa: E712
                  len(part_inv) * n_exp, len(admin) * n_exp]})

    def grp(by):
        if by not in det.columns or det[by].dropna().empty:
            return None  # nothing to group by (e.g. metadata disabled -> lod/sequence all null)
        g = det.groupby(by)
        return pd.DataFrame({by: list(g.groups.keys()), "n_sessions": g.size().values,
            "median_start_sec": g.calibration_start_sec.median().round(2).values,
            "pct_needs_review": (g.apply(lambda x: (x.needs_review == "Yes").mean() * 100, include_groups=False)).round(1).values})

    return {"overall": overall, "participant": grp("participant_id"), "trial": grp("trial_number"),
            "lod": grp("lod"), "williams": grp("sequence_number"),
            "timing": det[["participant_id", "trial_number", "calibration_start_sec", "calibration_end_sec", "confidence", "needs_review"]],
            "qc": det.exploratory_result.value_counts().rename_axis("exploratory_result").reset_index(name="count")}
