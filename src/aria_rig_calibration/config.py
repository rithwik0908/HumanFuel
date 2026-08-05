"""Configuration loading for the Aria rig-calibration toolkit (Python port).

Loads a study profile merged onto the generic default config and resolves the target /
metadata / status mappings. No study-specific values are hardcoded in code.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        base[k] = _deep_merge(base.get(k, {}), v) if isinstance(base.get(k), dict) and isinstance(v, dict) else v
    return base


def load_study_config(study_config_path: str | Path) -> dict[str, Any]:
    """Load a study config, merge onto its ``extends:`` default, and attach mappings.

    :param study_config_path: path to ``studies/<id>/study_config.yml``.
    :return: merged config dict with ``target``, ``metadata_map``, ``status_map`` attached.
    """
    p = Path(study_config_path).resolve()
    scfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    cfg: dict[str, Any] = {}
    if scfg.get("extends"):
        cfg = yaml.safe_load((p.parent / scfg["extends"]).resolve().read_text(encoding="utf-8"))
    cfg = _deep_merge(cfg, scfg)
    if scfg.get("target_config"):
        cfg["target"] = yaml.safe_load((p.parent / scfg["target_config"]).read_text(encoding="utf-8"))["calibration_targets"]
    if scfg.get("metadata_mapping"):
        cfg["metadata_map"] = yaml.safe_load((p.parent / scfg["metadata_mapping"]).read_text(encoding="utf-8"))["metadata_mapping"]
    if scfg.get("participant_status_mapping"):
        cfg["status_map"] = yaml.safe_load((p.parent / scfg["participant_status_mapping"]).read_text(encoding="utf-8"))["participant_status_mapping"]
    cfg["_study_config_path"] = str(p)
    return cfg


def validate_config(cfg: dict) -> tuple[bool, list[str]]:
    """Validate required config keys (fails on unrecovered nulls)."""
    problems: list[str] = []
    cs = cfg.get("calibration_search", {})
    for k in ("search_start_sec", "search_end_sec", "window_length_sec", "window_step_sec"):
        if cs.get(k) is None:
            problems.append(f"calibration_search.{k} is null (recover from legacy audit)")
    if cfg.get("target_blocks", {}).get("expected_count") is None:
        problems.append("target_blocks.expected_count null")
    for r in cfg.get("input", {}).get("roots", []):
        if not Path(r).is_dir():
            problems.append(f"input root missing: {r}")
    return (len(problems) == 0, problems)


def expand_pid_spec(spec) -> list[int]:
    """Expand a PID spec like ['1-37'] or '35' into a sorted int list."""
    out: set[int] = set()
    items = spec if isinstance(spec, (list, tuple)) else [spec]
    for tok in items:
        tok = str(tok).strip()
        if "-" in tok and all(x.isdigit() for x in tok.split("-")):
            a, b = (int(x) for x in tok.split("-"))
            out.update(range(a, b + 1))
        elif tok.isdigit():
            out.add(int(tok))
    return sorted(out)
