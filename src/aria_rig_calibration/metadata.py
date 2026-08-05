"""Participant-tracker metadata: online refresh (read-only) with local fallback, privacy-safe
extraction (only PID/sequence/trial-LOD/status), and administrative status. Metadata is attached
after analysis and never affects window search, scoring, or QC.
"""
from __future__ import annotations
import re
import urllib.request
from pathlib import Path
import pandas as pd


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).strip().lower())


def resolve_metadata(cfg: dict, snapshot_dir: Path, log, force_offline: bool = False) -> dict:
    """Try the online export (xlsx magic-byte check); else the local workbook."""
    online = {"attempted": False, "success": False, "reason": "offline", "path": None}
    md = cfg.get("metadata", {})
    if not force_offline and md.get("enabled") and md.get("online", {}).get("document_id"):
        online["attempted"] = True
        url = f"https://docs.google.com/spreadsheets/d/{md['online']['document_id']}/export?format=xlsx"
        dest = snapshot_dir / "online_tracker_snapshot.xlsx"; snapshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, dest)
            if dest.read_bytes()[:2] == b"PK":
                online.update(success=True, path=str(dest), reason="ok")
            else:
                online["reason"] = "endpoint returned non-xlsx (auth required)"; dest.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            online["reason"] = str(e)
    if online["success"]:
        return {"source": "online", "workbook": online["path"], "online": online, "fallback_used": False}
    loc = md.get("local")
    if loc and Path(loc).exists():
        log.warning("metadata: online unavailable (%s); using local fallback", online["reason"])
        return {"source": "local", "workbook": loc, "online": online, "fallback_used": True}
    return {"source": "none", "workbook": None, "online": online, "fallback_used": False}


def normalize_metadata(workbook: str | None, mapping: dict, source_label: str, log) -> pd.DataFrame:
    """Normalize the tracker to long metadata (pid, trial_index, sequence, lod, status)."""
    cols = ["participant_id", "trial_index", "trial_number", "sequence_number", "lod", "participant_status", "metadata_source"]
    if not workbook or not Path(workbook).exists():
        return pd.DataFrame(columns=cols)
    xl = pd.ExcelFile(workbook)
    pid_k, seq_k, st_k = _norm(mapping["participant_id_column"]), _norm(mapping.get("sequence_column") or ""), _norm(mapping.get("status_column") or "")
    trial_k = {int(k): _norm(v) for k, v in (mapping.get("trial_lod_columns") or {}).items()}
    rows = []
    for sh in xl.sheet_names:
        df = xl.parse(sh)
        hdr = {_norm(c): c for c in df.columns}
        if pid_k not in hdr or not all(v in hdr for v in trial_k.values()):
            continue
        for _, r in df.iterrows():
            try:
                pid = int(r[hdr[pid_k]])
            except (ValueError, TypeError):
                continue
            seqn = r[hdr[seq_k]] if seq_k in hdr else None
            st = r[hdr[st_k]] if st_k in hdr else None
            for ti, k in trial_k.items():
                rows.append(dict(participant_id=pid, trial_index=ti, trial_number=ti + 1,
                                 sequence_number=seqn, lod=r[hdr[k]] if k in hdr else None,
                                 participant_status=st, metadata_source=source_label))
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows)
    # dedupe by pid+trial, preferring a completed row
    def pick(g):
        comp = g[g.participant_status.astype(str).str.contains("complet", case=False, na=False)]
        return (comp.iloc[0] if len(comp) else g.iloc[0])
    return out.groupby(["participant_id", "trial_index"], as_index=False, group_keys=False).apply(pick)[cols].reset_index(drop=True)


def admin_status_for(tracker_status, has_data: bool, status_map: dict) -> str | None:
    """Map a tracker Status -> administrative status (explicit-only; never guessed)."""
    if has_data:
        return None
    s = str(tracker_status).strip().lower()
    default = status_map.get("default_when_no_data", "administrative_no_data_status_unknown")
    if s in ("", "na", "nan", "none"):
        return default
    for k, v in status_map.items():
        if k != "default_when_no_data" and k in s:
            return default if v == "completed" else v
    return default
