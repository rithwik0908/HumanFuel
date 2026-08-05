"""Recursive PID/trial gaze-file discovery across heterogeneous Aria layouts (Python port).
Prunes heavy directories (venvs, libs, prior results). Flags filename/folder disagreements and
duplicates; never guesses. Independent of the gaze-screen classification pipeline.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

# Heavy or generated directories skipped during discovery so a broad data root is not fully walked.
PRUNE = re.compile(r"(^\.venv$|^venv$|^env$|site-packages$|__pycache__$|node_modules$|\.git$|"
                   r"\.tox$|\.eggs$|build$|dist$|_results$|_results_python$|_outputs$|_output$)", re.I)


def _find_pruned(root: Path, pattern: re.Pattern) -> list[Path]:
    out: list[Path] = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if not PRUNE.search(e.name):
                    stack.append(e)
            elif pattern.search(e.name):
                out.append(e)
    return out


def parse_pid_trial(path: str) -> dict:
    """Parse PID/trial from filename + parent folders (tolerates a '-vrs' separator typo)."""
    parts = str(path).replace("\\", "/").split("/")
    fname = parts[-1]
    mf = re.search(r"mps_(\d+)-(\d+)[_-]vrs", fname)
    pid_file, trial_file = (int(mf.group(1)), int(mf.group(2))) if mf else (None, None)
    pid_folder = trial_folder = None
    for c in parts:
        mc = re.match(r"^mps_(\d+)-(\d+)[_-]vrs$", c)
        if mc:
            pid_folder, trial_folder = int(mc.group(1)), int(mc.group(2)); break
    pid_dir = None
    for c in parts:
        md = re.match(r"^[Pp][Ii][Dd][_]?0*(\d+)$", c)
        if md:
            pid_dir = int(md.group(1)); break
    trial_dir = None
    for c in parts:
        mt = re.match(r"^trial[_]?0*(\d+)$", c, re.I)
        if mt:
            trial_dir = int(mt.group(1)); break
    if re.search(r"mps_\d+-\d+[_-]vrs_general_eye_gaze", fname):
        layout = "flat_file"
    elif fname.lower() == "general_eye_gaze.csv" and any(p.endswith("eye_gaze") for p in parts[:-1]):
        layout = "nested_vrs_eye_gaze"
    elif fname.lower() == "general_eye_gaze.csv" and pid_folder is not None:
        layout = "nested_vrs"
    elif fname.lower() == "general_eye_gaze.csv" and trial_dir is not None:
        layout = "trial_folder"
    else:
        layout = "unknown"
    return dict(pid_file=pid_file, trial_file=trial_file, pid_folder=pid_folder, trial_folder=trial_folder,
                pid_dir=pid_dir, trial_dir=trial_dir, layout=layout, filename=fname)


def reconcile(p: dict) -> dict:
    pids = sorted({x for x in (p["pid_file"], p["pid_folder"], p["pid_dir"]) if x is not None})
    trials = sorted({x for x in (p["trial_file"], p["trial_folder"], p["trial_dir"]) if x is not None})
    status, excl, pid, trial, conf = "ok", None, None, None, "high"
    if not pids:
        status, excl, conf = "no_pid", "no PID parseable", "none"
    elif len(pids) > 1:
        status, excl, conf = "pid_mismatch", f"PID disagreement: {'/'.join(map(str, pids))}", "none"
    else:
        pid = pids[0]
    if not trials:
        if status == "ok":
            status, excl, conf = "no_trial", "no trial parseable", "none"
    elif len(trials) > 1:
        status, excl, conf = "trial_mismatch", f"trial disagreement: {'/'.join(map(str, trials))}", "none"
    else:
        trial = trials[0]
    return dict(pid=pid, trial_index=trial, parse_status=status, exclusion_reason=excl, parse_confidence=conf,
                filename_parse=(f"pid={p['pid_file']},trial={p['trial_file']}" if p["pid_file"] is not None else "no-match"))


def discover_files(cfg: dict, log) -> pd.DataFrame:
    """Discover gaze files under configured roots, reconcile PID/trial, and flag duplicates."""
    pattern = re.compile(r"general_eye_gaze\.csv$", re.I)
    files: list[Path] = []
    for r in cfg["input"]["roots"]:
        rp = Path(r)
        if rp.is_dir():
            files += _find_pruned(rp, pattern)
    files = sorted({f.resolve() for f in files})
    log.info("discovery: %d candidate gaze files", len(files))
    recs = []
    for f in files:
        p = parse_pid_trial(str(f)); rc = reconcile(p); st = f.stat()
        recs.append(dict(participant_id=rc["pid"], trial_index=rc["trial_index"],
                         trial_number=None if rc["trial_index"] is None else rc["trial_index"] + 1,
                         absolute_path=str(f).replace("\\", "/"), filename=p["filename"], layout=p["layout"],
                         file_size_bytes=st.st_size, modified_time=pd.Timestamp(st.st_mtime, unit="s").isoformat(),
                         parser_rule=p["layout"], parse_confidence=rc["parse_confidence"],
                         filename_parse=rc["filename_parse"], parse_status=rc["parse_status"],
                         exclusion_reason=rc["exclusion_reason"]))
    inv = pd.DataFrame(recs)
    if inv.empty:
        return inv
    inv["duplicate_group"] = None; inv["selected"] = False
    ok = (inv.parse_status == "ok") & inv.participant_id.notna() & inv.trial_index.notna()
    key = inv.apply(lambda r: f"PID{int(r.participant_id)}_T{int(r.trial_index)}" if ok[r.name] else None, axis=1)
    for k in key.dropna().unique():
        idx = key[key == k].index
        if len(idx) == 1:
            inv.loc[idx, "selected"] = True
        else:
            inv.loc[idx, "duplicate_group"] = k
            inv.loc[idx, "exclusion_reason"] = f"duplicate PID/trial ({len(idx)} files); none auto-selected"
            log.warning("discovery: duplicate %s: %d files", k, len(idx))
    return inv


def apply_scope(inv: pd.DataFrame, cfg: dict, requested_pids, requested_trials, discover_all=False) -> pd.DataFrame:
    inv = inv.copy(); inv["in_scope"] = inv["selected"]
    mode = "discovered_only" if discover_all else cfg["participants"].get("discovery_mode", "requested_plus_discovered")
    if mode == "requested_only" and requested_pids:
        inv["in_scope"] &= inv.participant_id.isin(requested_pids)
    if requested_trials:
        inv["in_scope"] &= inv.trial_index.isin(requested_trials)
    return inv
