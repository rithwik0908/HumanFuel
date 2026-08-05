"""Participant-tracker metadata.

Role in the pipeline
--------------------
Optionally attach de-identified participant metadata (Williams Sequence, per-trial LOD, administrative
status) to the analysis. Metadata is joined *after* the calibration search and never influences window
selection, scoring, or QC.

Privacy
-------
To read the configured fields the tracker workbook must be opened, so we do not claim the forbidden
fields are "never read". Instead: only the configured de-identified fields are *retained* in toolkit
outputs; an online workbook is downloaded to a secure temporary file and deleted after normalisation
(unless the caller explicitly opts to retain a snapshot); and :func:`check_forbidden_columns` guards
every exported frame so no name/email/phone/payment/scheduling column can leak.
"""
from __future__ import annotations

import os
import re
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

#: Fixed, de-identified output schema for normalised metadata.
METADATA_COLUMNS = ["participant_id", "trial_index", "trial_number", "sequence_number", "lod",
                    "participant_status", "metadata_source"]

_UNRESOLVED = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")


class MetadataError(Exception):
    """Raised when a required metadata source (online or local) is requested but unavailable."""


def _norm(s: str) -> str:
    """Normalise a header for matching: lowercase and strip non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", str(s).strip().lower())


#: The toolkit's own analytic columns that legitimately contain a forbidden substring (e.g. QC
#: "notes", or a target label ending in "...name"). These are toolkit-controlled, not personal data,
#: and are exempt from the forbidden-token export guard.
SAFE_ANALYTIC_COLUMNS = {"notes", "target_display_name", "display_name", "review_reasons"}


def check_forbidden_columns(df: pd.DataFrame | None, forbidden_tokens: list[str],
                            allow: set[str] | None = None) -> list[str]:
    """Return names of columns whose header contains a forbidden token (case-insensitive).

    Used as a privacy guard before writing any output frame. Columns in ``allow`` (defaulting to the
    toolkit's own analytic columns such as ``notes``) are exempt. An empty result means the frame is
    clean of personal-data columns.
    """
    if df is None or not forbidden_tokens:
        return []
    allow = SAFE_ANALYTIC_COLUMNS if allow is None else (SAFE_ANALYTIC_COLUMNS | allow)
    toks = [t.lower() for t in forbidden_tokens]
    return [c for c in df.columns if str(c).lower() not in allow and any(t in str(c).lower() for t in toks)]


def _download_workbook(url: str, log) -> str | None:
    """Download an xlsx export to a secure temp file; return its path, or None if not a valid xlsx."""
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", prefix="aria_tracker_")
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, tmp)
        if Path(tmp).read_bytes()[:2] == b"PK":  # real xlsx begins with the ZIP magic 'PK'
            return tmp
        Path(tmp).unlink(missing_ok=True)
        return None
    except Exception as e:  # noqa: BLE001
        log.warning("metadata: online download failed (%s)", e)
        Path(tmp).unlink(missing_ok=True)
        return None


def resolve_metadata(cfg: dict, snapshot_dir: Path, log, mode: str = "auto", retain_snapshot: bool = False) -> dict:
    """Resolve the metadata workbook according to ``mode``.

    :param cfg: merged config (``metadata`` section).
    :param snapshot_dir: run directory where a snapshot is kept only if ``retain_snapshot`` is True.
    :param log: collecting logger.
    :param mode: ``auto`` (online then local), ``online`` (require online), ``local`` (require local
        file), or ``none`` (disable metadata).
    :param retain_snapshot: when True, keep the downloaded workbook under ``snapshot_dir`` (with a
        privacy warning); when False, the temporary download is deleted after normalisation.
    :return: dict with ``source`` (online/local/none), ``workbook`` (path or None), ``temp_path``
        (a temp file to delete after normalisation, or None), and ``online`` diagnostics.
    """
    md = cfg.get("metadata", {})
    online = {"attempted": False, "success": False, "reason": "disabled"}
    enabled = bool(md.get("enabled"))
    # Explicit online/local modes force resolution even if the profile has metadata.enabled = false.
    # 'none' always disables; 'auto' respects metadata.enabled.
    if mode == "none" or (mode == "auto" and not enabled):
        return {"source": "none", "workbook": None, "temp_path": None, "online": online}

    doc_id = (md.get("online") or {}).get("document_id")
    can_online = bool(doc_id) and not _UNRESOLVED.search(str(doc_id)) and mode in ("auto", "online")
    temp_path = None
    if can_online:
        online["attempted"] = True
        url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
        temp_path = _download_workbook(url, log)
        if temp_path:
            online.update(success=True, reason="ok")
            workbook = temp_path
            if retain_snapshot:
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                dest = snapshot_dir / "online_tracker_snapshot.xlsx"
                dest.write_bytes(Path(temp_path).read_bytes())
                log.warning("metadata: PRIVACY: retaining full tracker snapshot at %s (contains all tracker columns)", dest)
                workbook, temp_path = str(dest), temp_path  # temp still deleted after normalisation
            return {"source": "online", "workbook": workbook, "temp_path": temp_path, "online": online}
        online["reason"] = "online export unavailable or not an xlsx"
        if mode == "online":
            raise MetadataError("metadata-mode 'online' requested but the online export was unavailable")
    elif mode == "online":
        raise MetadataError("metadata-mode 'online' requested but no resolved online document id was configured")

    loc = md.get("local")
    if loc and not _UNRESOLVED.search(str(loc)) and Path(loc).exists():
        if mode == "auto" and online["attempted"]:
            log.warning("metadata: online unavailable (%s); using local file", online["reason"])
        return {"source": "local", "workbook": loc, "temp_path": None, "online": online}
    if mode == "local":
        raise MetadataError(f"metadata-mode 'local' requested but no local workbook was found: {loc!r}")
    log.warning("metadata: no workbook available; proceeding without metadata")
    return {"source": "none", "workbook": None, "temp_path": None, "online": online}


def normalize_metadata(workbook: str | None, mapping: dict, source_label: str, log) -> pd.DataFrame:
    """Extract only the de-identified fields into a long (pid, trial) table.

    :param workbook: path to the tracker workbook, or None.
    :param mapping: the ``metadata_mapping`` block (participant/sequence/status/trial-LOD columns and
        ``forbidden_tokens``).
    :param source_label: value written into the ``metadata_source`` column.
    :param log: collecting logger.
    :return: DataFrame with exactly :data:`METADATA_COLUMNS`; empty if no workbook or no matching sheet.
    """
    if not workbook or not Path(workbook).exists():
        return pd.DataFrame(columns=METADATA_COLUMNS)
    pid_k = _norm(mapping["participant_id_column"])
    seq_k = _norm(mapping.get("sequence_column") or "")
    st_k = _norm(mapping.get("status_column") or "")
    trial_k = {int(k): _norm(v) for k, v in (mapping.get("trial_lod_columns") or {}).items()}
    rows = []
    try:
        # Context manager closes the file handle before any caller deletes it (important on Windows).
        with pd.ExcelFile(workbook) as xl:
            sheets = {sh: xl.parse(sh) for sh in xl.sheet_names}
    except Exception as e:  # noqa: BLE001
        raise MetadataError(f"could not read metadata workbook: {type(e).__name__}") from None
    for df in sheets.values():
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
        return pd.DataFrame(columns=METADATA_COLUMNS)
    out = pd.DataFrame(rows)

    def pick(g):
        """Prefer a completed row when duplicate (pid, trial) rows exist."""
        comp = g[g.participant_status.astype(str).str.contains("complet", case=False, na=False)]
        return comp.iloc[0] if len(comp) else g.iloc[0]

    out = out.groupby(["participant_id", "trial_index"], as_index=False, group_keys=False).apply(pick)[METADATA_COLUMNS].reset_index(drop=True)
    leaked = check_forbidden_columns(out, mapping.get("forbidden_tokens", []))
    if leaked:  # defensive: the fixed schema should never contain these
        raise RuntimeError(f"normalized metadata contains forbidden columns: {leaked}")
    return out


def admin_status_for(tracker_status, has_data: bool, status_map: dict) -> str | None:
    """Map a tracker Status to an administrative no-data status (explicit only; never guessed).

    :param tracker_status: the raw Status string from the tracker (may be None/blank).
    :param has_data: whether any gaze data was found for the participant.
    :param status_map: the ``participant_status_mapping`` block.
    :return: None when data exists; otherwise the mapped ``administrative_no_data_*`` status, or the
        configured default when the status is blank or unmapped.
    """
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
