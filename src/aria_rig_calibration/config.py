"""Configuration loading for the Project Aria rig-calibration toolkit.

Responsibilities
----------------
* Load a study profile and deep-merge it onto the generic default config named by ``extends:``.
* Attach the resolved target / metadata / status mappings referenced by the study profile.
* Expand ``${ENV_VAR}`` placeholders in every string value so no machine-specific path is committed.
* Apply command-line path overrides (highest precedence) and validate the merged configuration.

No study-specific values are hardcoded in code; portability comes from environment variables and
optional CLI overrides. See ``docs/configuration.md``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

#: Matches ``${NAME}`` environment-variable placeholders inside YAML string values.
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: Config fields whose unresolved placeholder should raise a targeted, user-friendly error, mapped to
#: the CLI override that can satisfy them without an environment variable.
_REQUIRED_PATH_FIELDS = {
    "ARIA_DATA_ROOT": ("input.roots", "--data-root"),
    "ARIA_OUTPUT_ROOT": ("outputs.root", "--output-root"),
    "ARIA_METADATA_FILE": ("metadata.local", "--metadata-file"),
}


class ConfigError(Exception):
    """Raised when a configuration is missing required values or references unset environment variables."""


def _deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge ``over`` onto ``base`` in place and return ``base`` (dicts merge, others replace)."""
    for k, v in over.items():
        base[k] = _deep_merge(base.get(k, {}), v) if isinstance(base.get(k), dict) and isinstance(v, dict) else v
    return base


def expand_env(obj: Any, missing: set[str] | None = None) -> Any:
    """Recursively expand ``${VAR}`` placeholders in strings within dicts/lists/scalars.

    :param obj: any nested structure of dicts, lists, and scalars loaded from YAML.
    :param missing: mutable set collecting names of placeholders that are unset/empty (left literal).
    :return: a new structure with resolved placeholders; unresolved ones are kept verbatim so that
             :func:`validate_config` can report them precisely.
    """
    if missing is None:
        missing = set()
    if isinstance(obj, dict):
        return {k: expand_env(v, missing) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env(v, missing) for v in obj]
    if isinstance(obj, str):
        def sub(m: re.Match) -> str:
            name = m.group(1)
            val = os.environ.get(name)
            if val is None or val == "":
                missing.add(name)
                return m.group(0)  # keep ${NAME} literal for later validation
            return val
        return _ENV_RE.sub(sub, obj)
    return obj


def load_study_config(study_config_path: str | Path) -> dict[str, Any]:
    """Load a study config, merge it onto its ``extends:`` default, attach mappings, and expand env vars.

    Loading never raises on unset environment variables; unresolved ``${VAR}`` placeholders are left
    literal and recorded under ``cfg["_unresolved_env"]``. Call :func:`validate_config` (or
    :func:`require_valid_config`) to fail clearly on required-but-missing values.

    :param study_config_path: path to ``studies/<id>/study_config(.local|.example).yml``.
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
    missing: set[str] = set()
    cfg = expand_env(cfg, missing)
    cfg["_study_config_path"] = str(p)
    cfg["_unresolved_env"] = sorted(missing)
    return cfg


def apply_path_overrides(cfg: dict, data_root: str | None = None, metadata_file: str | None = None,
                         output_root: str | None = None) -> dict:
    """Apply CLI path overrides in place (highest precedence over env vars and YAML).

    :param cfg: merged config to mutate.
    :param data_root: overrides ``input.roots`` with a single root when provided.
    :param metadata_file: overrides ``metadata.local`` when provided.
    :param output_root: overrides ``outputs.root`` when provided.
    :return: the same ``cfg`` for chaining. Overrides also clear the corresponding unresolved-env entry.
    """
    unresolved = set(cfg.get("_unresolved_env", []))
    if data_root:
        cfg.setdefault("input", {})["roots"] = [data_root]
        unresolved.discard("ARIA_DATA_ROOT")
    if metadata_file:
        cfg.setdefault("metadata", {})["local"] = metadata_file
        unresolved.discard("ARIA_METADATA_FILE")
    if output_root:
        cfg.setdefault("outputs", {})["root"] = output_root
        unresolved.discard("ARIA_OUTPUT_ROOT")
    cfg["_unresolved_env"] = sorted(unresolved)
    return cfg


def _has_unresolved(value: Any) -> bool:
    """Return True if a scalar or any nested string still contains a ``${VAR}`` placeholder."""
    if isinstance(value, str):
        return bool(_ENV_RE.search(value))
    if isinstance(value, (list, tuple)):
        return any(_has_unresolved(v) for v in value)
    return False


def validate_config(cfg: dict, metadata_mode: str = "auto") -> tuple[bool, list[str]]:
    """Validate scientific parameters, target definitions, and required paths.

    Checks (non-exhaustive): positive window length/step, ``search_end >= search_start``, target count
    >= 2 matching the target list with unique orders, block duration consistent with the target count,
    a non-empty resolved output root, and resolved input roots (env vars supplied). Metadata
    requirements depend on ``metadata_mode`` (see :func:`_metadata_problems`).

    :param cfg: merged config from :func:`load_study_config` (after any :func:`apply_path_overrides`).
    :param metadata_mode: ``auto``/``online``/``local``/``none`` — controls which metadata sources are
        required.
    :return: ``(ok, problems)`` where ``problems`` is a list of human-readable messages.
    """
    problems: list[str] = []
    cs = cfg.get("calibration_search", {})
    for k in ("search_start_sec", "search_end_sec", "window_length_sec", "window_step_sec"):
        if cs.get(k) is None:
            problems.append(f"calibration_search.{k} is null")
    if all(cs.get(k) is not None for k in ("window_length_sec", "window_step_sec", "search_start_sec", "search_end_sec")):
        if cs["window_length_sec"] <= 0:
            problems.append("calibration_search.window_length_sec must be > 0")
        if cs["window_step_sec"] <= 0:
            problems.append("calibration_search.window_step_sec must be > 0")
        if cs["search_end_sec"] < cs["search_start_sec"]:
            problems.append("calibration_search.search_end_sec must be >= search_start_sec")

    # Target definitions: count >= 2, matches list length, unique 1..N orders.
    tb = cfg.get("target_blocks", {})
    count = tb.get("expected_count")
    if count is None or count < 2:
        problems.append("target_blocks.expected_count must be an integer >= 2")
    targets = (cfg.get("target") or {}).get("targets")
    if targets is not None:
        if count is not None and len(targets) != count:
            problems.append(f"target list length ({len(targets)}) != target_blocks.expected_count ({count})")
        orders = [t.get("order") for t in targets]
        if len(set(orders)) != len(orders):
            problems.append("duplicate target order values in target config")
        ids = [t.get("id") for t in targets]
        if any(i is None for i in ids) or len(set(ids)) != len(ids):
            problems.append("target ids must be present and unique")
    if count and cs.get("window_length_sec") and tb.get("expected_duration_sec"):
        if abs(cs["window_length_sec"] / count - tb["expected_duration_sec"]) > 1e-9:
            problems.append("window_length_sec / expected_count != target_blocks.expected_duration_sec")

    # Required resolved paths (env vars / CLI overrides).
    roots = cfg.get("input", {}).get("roots") or []
    if not roots or any(_has_unresolved(r) for r in roots):
        var, (field, flag) = "ARIA_DATA_ROOT", _REQUIRED_PATH_FIELDS["ARIA_DATA_ROOT"]
        problems.append(f"{var} is not set. Set the environment variable, pass {flag}, or provide "
                        f"{field} in a local study configuration file.")
    else:
        for r in roots:
            if not Path(r).is_dir():
                problems.append(f"input root does not exist: {r}")
    out_root = cfg.get("outputs", {}).get("root")
    if not out_root or _has_unresolved(out_root):
        problems.append("ARIA_OUTPUT_ROOT is not set. Set the environment variable, pass --output-root, "
                        "or provide outputs.root in a local study configuration file.")

    problems += _metadata_problems(cfg.get("metadata", {}), metadata_mode)
    return (len(problems) == 0, problems)


def _metadata_problems(md: dict, mode: str) -> list[str]:
    """Return metadata configuration problems for the selected ``metadata_mode``.

    * ``none``  - no metadata source is required.
    * ``online``- a resolved online document id is required; the local file is irrelevant.
    * ``local`` - an existing local workbook is required; the online id is irrelevant.
    * ``auto``  - neither source is required (the run proceeds with a warning if neither is available).
    """
    doc = (md.get("online") or {}).get("document_id")
    loc = md.get("local")
    if mode == "online":
        if not doc or _has_unresolved(doc):
            return ["metadata-mode online requires a resolved online document id "
                    "(set ARIA_TRACKER_DOCUMENT_ID or metadata.online.document_id)."]
    elif mode == "local":
        if not loc or _has_unresolved(loc):
            return ["metadata-mode local requires a local workbook (set ARIA_METADATA_FILE, pass "
                    "--metadata-file, or provide metadata.local)."]
        if not Path(loc).is_file():
            return [f"metadata-mode local: workbook not found: {loc}"]
    # 'none' and 'auto' impose no hard requirement here; 'auto' warns at run time if nothing resolves.
    return []


def require_valid_config(cfg: dict, metadata_mode: str = "auto") -> None:
    """Raise :class:`ConfigError` with all problems if the config is invalid; otherwise return None."""
    ok, problems = validate_config(cfg, metadata_mode)
    if not ok:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))


def expand_pid_spec(spec: Any) -> list[int]:
    """Expand a PID/trial spec such as ``['1-37']`` or ``'35'`` or ``[0,1,2]`` into a sorted int list.

    :param spec: a scalar, or a list of tokens, each an integer or an inclusive ``A-B`` range.
    :return: sorted list of unique integers.
    """
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
