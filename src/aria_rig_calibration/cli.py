"""Command-line interface.

Parses arguments into a :class:`aria_rig_calibration.models.RunOptions` and invokes
:func:`aria_rig_calibration.pipeline.run_pipeline` directly. This is the target of the installed
``aria-rig-calibration`` console command and of ``python -m aria_rig_calibration.cli``; it does not
depend on the repository-level ``scripts/`` directory.
"""
from __future__ import annotations

import argparse
import sys

from .config import ConfigError
from .models import RunOptions
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser (also used to document the CLI)."""
    p = argparse.ArgumentParser(
        prog="aria-rig-calibration",
        description="Locate the rig-calibration interval in Project Aria gaze recordings and "
                    "characterise where each configured calibration target appears in gaze space.")
    p.add_argument("--study-config", required=True,
                   help="Path to a study config, e.g. studies/so_pedestrian/study_config.local.yml")
    p.add_argument("--pids", help="PID scope, e.g. '35' or '1-37' or '1-6,35' (default: config include)")
    p.add_argument("--trials", help="Trial-index scope, e.g. '0-4' (default: config expected_indices)")
    p.add_argument("--discover-all", action="store_true",
                   help="Process and report every discovered PID (including new PIDs beyond the config range)")
    p.add_argument("--metadata-mode", choices=["auto", "online", "local", "none"], default="auto",
                   help="auto: online then local; online: require online; local: require local file; none: disable metadata")
    p.add_argument("--retain-metadata-snapshot", action="store_true",
                   help="Keep the full downloaded tracker workbook in the run outputs (PRIVACY WARNING; off by default)")
    p.add_argument("--validate-only", action="store_true", help="Run discovery + schema validation only; no analysis")
    p.add_argument("--data-root", help="Override input.roots with this data root (highest precedence)")
    p.add_argument("--metadata-file", help="Override metadata.local with this tracker .xlsx path")
    p.add_argument("--output-root", help="Override outputs.root with this directory")
    p.add_argument("--run-id", help="Explicit run id (default: timestamped)")
    p.add_argument("--overwrite", action="store_true", help="Allow reusing an existing run folder")
    return p


def parse_options(argv: list[str] | None = None) -> RunOptions:
    """Parse ``argv`` (or ``sys.argv``) into a :class:`RunOptions`."""
    a = build_parser().parse_args(argv)
    return RunOptions(
        study_config=a.study_config, pids=a.pids, trials=a.trials, discover_all=a.discover_all,
        metadata_mode=a.metadata_mode, retain_metadata_snapshot=a.retain_metadata_snapshot,
        validate_only=a.validate_only, run_id=a.run_id, overwrite=a.overwrite,
        data_root=a.data_root, metadata_file=a.metadata_file, output_root=a.output_root)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 on success, 2 on configuration error)."""
    opts = parse_options(argv)
    try:
        result = run_pipeline(opts)
    except ConfigError as e:
        print(f"Configuration error:\n{e}", file=sys.stderr)
        return 2
    print(f"RUN_ID={result.run_id}")
    print(f"RUN_ROOT={result.run_root}")
    print(f"Processed {result.processed_sessions}/{result.recorded_sessions} sessions; "
          f"sources_unmodified={result.sources_unmodified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
