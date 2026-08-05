"""Source-integrity verification.

Role in the pipeline
--------------------
Compute SHA-256 hashes of the selected source gaze files and the study configuration/mapping files
*before* processing and again *after*, then compare. This lets the run manifest make a **verified**
claim that the toolkit did not modify its inputs, rather than an unchecked assertion.

We only hash files the toolkit actually reads; we make no claims about unrelated files unless their
paths are passed in and hashed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str | None:
    """Return the hex SHA-256 of a file, or None if it cannot be read."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def hash_paths(paths: list[str | Path], role: str) -> pd.DataFrame:
    """Hash a list of files into a DataFrame of ``(role, path, sha256, size_bytes, exists)`` rows."""
    rows = []
    for p in paths:
        pp = Path(p)
        exists = pp.is_file()
        rows.append({"role": role, "path": str(pp).replace("\\", "/"),
                     "sha256": sha256_file(pp) if exists else None,
                     "size_bytes": pp.stat().st_size if exists else None, "exists": exists})
    return pd.DataFrame(rows, columns=["role", "path", "sha256", "size_bytes", "exists"])


def snapshot(source_files: list[str | Path], config_files: list[str | Path]) -> pd.DataFrame:
    """Hash the selected gaze files (role ``source``) and config/mapping files (role ``config``)."""
    return pd.concat([hash_paths(source_files, "source"), hash_paths(config_files, "config")], ignore_index=True)


def compare(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    """Compare two hash snapshots, returning a per-file result frame.

    :return: DataFrame with ``role, path, sha256_before, sha256_after, status`` where status is
        ``unchanged``, ``modified``, ``disappeared``, ``appeared``, or ``not_checked``.
    """
    b = before.set_index("path")["sha256"].to_dict()
    a = after.set_index("path")["sha256"].to_dict()
    roles = pd.concat([before[["path", "role"]], after[["path", "role"]]]).drop_duplicates("path").set_index("path")["role"].to_dict()
    rows = []
    for path in sorted(set(b) | set(a)):
        hb, ha = b.get(path), a.get(path)
        if hb is None and ha is not None:
            status = "appeared"
        elif hb is not None and ha is None:
            status = "disappeared"
        elif hb is None and ha is None:
            status = "not_checked"
        else:
            status = "unchanged" if hb == ha else "modified"
        rows.append({"role": roles.get(path), "path": path, "sha256_before": hb, "sha256_after": ha, "status": status})
    return pd.DataFrame(rows, columns=["role", "path", "sha256_before", "sha256_after", "status"])


def sources_unmodified(comparison: pd.DataFrame) -> str:
    """Reduce a comparison frame to a manifest value: ``true``, ``false``, or ``not_checked``."""
    if comparison.empty:
        return "not_checked"
    statuses = set(comparison.status)
    if statuses <= {"unchanged"}:
        return "true"
    if statuses & {"modified", "disappeared"}:
        return "false"
    return "not_checked"
