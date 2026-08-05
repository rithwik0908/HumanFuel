"""Typed value objects shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunOptions:
    """All inputs that control a single analysis run (populated by the CLI or a caller).

    Path overrides (``data_root``/``metadata_file``/``output_root``) take precedence over environment
    variables and YAML. ``metadata_mode`` is one of ``auto``/``online``/``local``/``none``.
    """
    study_config: str
    pids: str | None = None
    trials: str | None = None
    discover_all: bool = False
    metadata_mode: str = "auto"
    retain_metadata_snapshot: bool = False
    validate_only: bool = False
    run_id: str | None = None
    overwrite: bool = False
    data_root: str | None = None
    metadata_file: str | None = None
    output_root: str | None = None


@dataclass
class RunResult:
    """Summary of a completed run, returned by :func:`aria_rig_calibration.pipeline.run_pipeline`."""
    run_id: str
    run_root: str
    recorded_sessions: int
    processed_sessions: int
    reporting_pids: list[int] = field(default_factory=list)
    metadata_source: str = "none"
    sources_unmodified: str = "not_checked"
