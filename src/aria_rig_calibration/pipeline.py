"""Analysis orchestration.

Role in the pipeline
--------------------
``run_pipeline(options)`` is the single public entry point used by both the installed console command
and ``python scripts/run_analysis.py``. It is split into small, individually testable stages:
configuration, run directory, metadata, discovery, schema validation, per-session analysis, and output
writing (windows, targets, inventory, summaries, Excel, plots, integrity, manifest).

The scientific method is unchanged from the validated implementation; this module only reorganises the
control flow and adds portability, integrity, and privacy handling.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import excel_writer, integrity, visualization
from .calibration import scan_windows
from .config import apply_path_overrides, expand_pid_spec, load_study_config, require_valid_config
from .discovery import apply_scope, discover_files
from .gaze import load_gaze, validate_schema
from .logging_utils import CollectingLogger
from .metadata import check_forbidden_columns, normalize_metadata, resolve_metadata
from .models import RunOptions, RunResult
from .output_writer import (build_participant_inventory, build_summaries, make_run_dir,
                            pid_folder_status_factory, scope_run_label)
from .target_blocks import analyze_targets


# --------------------------------------------------------------------------------------------------
# Configuration & run setup
# --------------------------------------------------------------------------------------------------
def load_and_validate_config(opts: RunOptions) -> dict:
    """Load the study config, apply CLI overrides and scope, and validate (raises on error)."""
    cfg = load_study_config(opts.study_config)
    apply_path_overrides(cfg, opts.data_root, opts.metadata_file, opts.output_root)
    if opts.metadata_mode == "none":
        cfg.setdefault("metadata", {})["enabled"] = False  # mode 'none' disables metadata & its file requirement
    if opts.pids:
        cfg["participants"]["include"] = opts.pids.split(",")
    if opts.trials:
        cfg["trials"]["expected_indices"] = expand_pid_spec(opts.trials.split(","))
    if opts.pids and not opts.discover_all:
        cfg["participants"]["discovery_mode"] = "requested_only"
    require_valid_config(cfg, opts.metadata_mode)
    return cfg


def _config_files(cfg: dict) -> list[str]:
    """Return the study config and sibling mapping/target YAMLs plus the default config, for hashing."""
    study = Path(cfg["_study_config_path"])
    files = [study] + sorted(study.parent.glob("*.yml"))
    default = study.parent / cfg.get("extends", "") if cfg.get("extends") else None
    if default and default.exists():
        files.append(default.resolve())
    seen, out = set(), []
    for f in files:
        s = str(Path(f).resolve())
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _git_info() -> dict:
    """Best-effort git commit/branch/dirty for the package repo (nulls if git is unavailable)."""
    repo = Path(__file__).resolve().parents[2]
    def run(args):
        try:
            return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=5).stdout.strip() or None
        except Exception:  # noqa: BLE001
            return None
    sha = run(["rev-parse", "HEAD"])
    branch = run(["rev-parse", "--abbrev-ref", "HEAD"])
    status = run(["status", "--porcelain"])
    return {"commit": sha, "branch": branch, "dirty": None if status is None else bool(status)}


# --------------------------------------------------------------------------------------------------
# Metadata / discovery / validation
# --------------------------------------------------------------------------------------------------
def resolve_run_metadata(cfg: dict, paths: dict, log, opts: RunOptions) -> tuple[dict, pd.DataFrame]:
    """Resolve and normalise metadata, delete any temporary workbook, and write the metadata report."""
    msrc = resolve_metadata(cfg, paths["metadata_snapshot"], log, mode=opts.metadata_mode,
                            retain_snapshot=opts.retain_metadata_snapshot)
    meta = normalize_metadata(msrc["workbook"], cfg.get("metadata_map", {}), msrc["source"], log)
    if msrc.get("temp_path"):
        Path(msrc["temp_path"]).unlink(missing_ok=True)  # never retain the full workbook by default
    meta.to_csv(paths["metadata"] / "participant_trial_metadata.csv", index=False)
    json.dump({"source": msrc["source"], "online": msrc["online"], "rows": len(meta),
               "retained_snapshot": bool(opts.retain_metadata_snapshot and msrc["source"] == "online")},
              open(paths["metadata"] / "metadata_source_report.json", "w"), indent=2, default=str)
    return msrc, meta


def discover_sessions(cfg: dict, log, requested: list[int], trials: list[int], discover_all: bool, paths: dict):
    """Discover gaze files, apply scope, and write discovery inventory CSVs. Returns (inv, process)."""
    inv = discover_files(cfg, log)
    inv = apply_scope(inv, cfg, requested, trials, discover_all=discover_all)
    inv.to_csv(paths["inventory"] / "discovered_files.csv", index=False)
    if not inv.empty:
        inv[inv.parse_status.isin(["pid_mismatch", "trial_mismatch", "no_pid", "no_trial"])].to_csv(paths["inventory"] / "ambiguous_files.csv", index=False)
        inv[inv.duplicate_group.notna()].to_csv(paths["inventory"] / "duplicate_files.csv", index=False)
    process = inv[inv.in_scope == True] if not inv.empty else inv  # noqa: E712
    log.info("discovery: %d files, %d in-scope", len(inv), len(process))
    return inv, process


def validate_sessions(process: pd.DataFrame, cfg: dict, paths: dict) -> pd.DataFrame:
    """Run schema validation for each in-scope file and write the schema report."""
    schema = pd.DataFrame([validate_schema(r.absolute_path, r._asdict(), cfg) for r in process.itertuples()]) if len(process) else pd.DataFrame()
    if len(schema):
        schema.to_csv(paths["validation"] / "schema_validation.csv", index=False)
    return schema


# --------------------------------------------------------------------------------------------------
# Per-session analysis
# --------------------------------------------------------------------------------------------------
def _exploratory_result(margin: float, best_score: float, notes: list[str]) -> str:
    """Classify a selected window's interpretability from its score margin and QC notes."""
    if np.isfinite(margin) and margin < 5 and margin < 0.02 * abs(best_score):
        return "multiple_similar_windows"
    if any("not clearly distinct" in n for n in notes):
        return "weak_target_separation"
    if any("samples" in n for n in notes):
        return "insufficient_samples"
    return "selected_with_qc_warning" if notes else "selected_clear"


def analyze_one_session(row, cfg: dict, meta: pd.DataFrame, schema: pd.DataFrame, paths: dict,
                        gen_static: bool, gen_html: bool, log) -> dict:
    """Analyse a single (pid, trial) file; returns a dict of result frames/records or a status.

    On any failure the ``status`` key carries ``invalid_data`` or ``processing_failed`` with the pid,
    trial, and source path recorded for batch continuation.
    """
    pid, ti = int(row.participant_id), int(row.trial_index)
    sv = schema[(schema.participant_id == pid) & (schema.trial_index == ti)] if len(schema) else None
    if sv is not None and len(sv) and sv.validation_status.iloc[0] != "ok":
        return {"status": {"participant_id": pid, "trial_index": ti, "status": "invalid_data", "reason": sv.exclusion_reason.iloc[0]}}
    try:
        g = load_gaze(row.absolute_path, cfg)
        sw = scan_windows(g["work"], cfg)
        mr = meta[(meta.participant_id == pid) & (meta.trial_index == ti)] if len(meta) else meta
        seqn = mr.sequence_number.iloc[0] if len(mr) else None
        lod = mr.lod.iloc[0] if len(mr) else None
        out: dict = {"pid": pid, "trial_index": ti, "processed": True,
                     "status": {"participant_id": pid, "trial_index": ti, "status": "processed", "reason": None}}
        if len(sw["all_windows"]):
            aw = sw["all_windows"].copy()
            aw["participant_id"] = pid
            aw["trial_number"] = ti + 1
            out["all_windows"] = aw
            out["top_windows"] = aw.head(cfg["outputs"].get("save_top_n_windows", 5))
        if sw["selected"] is not None:
            s, rv = sw["selected"], sw["review"]
            margin = float(sw["all_windows"].score.iloc[0] - sw["all_windows"].score.iloc[1]) if len(sw["all_windows"]) >= 2 else np.nan
            notes = rv["notes"]
            res_cat = _exploratory_result(margin, float(sw["all_windows"].score.iloc[0]), notes)
            ta = analyze_targets(s, cfg, pid, ti)
            ta["blocks"]["sequence_number"] = seqn
            ta["blocks"]["lod"] = lod
            out["blocks"] = ta["blocks"]
            out["pairwise"] = ta["pairwise"]
            sel_rec = {"participant_id": pid, "trial_index": ti, "trial_number": ti + 1,
                       "calibration_start_sec": round(s["start"], 4), "calibration_end_sec": round(s["end"], 4),
                       "score": round(s["score"], 4), "min_centroid_distance": round(s["min_dist"], 6),
                       "avg_dispersion": round(s["avg_disp"], 6), "total_samples": s["total_samples"]}
            for i, sm in enumerate(s["summaries"], start=1):  # block_1..N (block_1/2/3 for three targets)
                sel_rec[f"block_{i}_samples"] = sm["n"]
            sel_rec.update({"confidence": rv["confidence"], "needs_review": "Yes" if rv["needs_review"] else "No",
                            "exploratory_result": res_cat, "best_vs_second_margin": round(margin, 4) if np.isfinite(margin) else None,
                            "window_selected": True, "sequence_number": seqn, "lod": lod, "notes": "; ".join(notes)})
            out["selected"] = sel_rec
            out["diag"] = {"participant_id": pid, "trial_number": ti + 1, "n_scanned_windows": len(sw["all_windows"]),
                           "best_score": round(float(sw["all_windows"].score.iloc[0]), 3),
                           "margin": round(margin, 3) if np.isfinite(margin) else None, "exploratory_result": res_cat,
                           "confidence": rv["confidence"], "review_reasons": "; ".join(notes)}
            if gen_static or gen_html:
                tag = f"PID{pid} T{ti + 1} seq{seqn} {lod} |"
                try:
                    visualization.session_plots({"pid": pid, "trial_index": ti, "work": g["work"], "sel": s,
                                                  "all_windows": sw["all_windows"], "title_tag": tag}, cfg, paths)
                except Exception as e:  # noqa: BLE001
                    log.warning("plot PID%d T%d: %s", pid, ti + 1, e)
        return out
    except Exception as e:  # noqa: BLE001
        log.error("session PID%d T%d (%s): %s: %s", pid, ti + 1, row.absolute_path, type(e).__name__, e)
        return {"status": {"participant_id": pid, "trial_index": ti, "status": "processing_failed",
                           "reason": f"{type(e).__name__}: {e}"}}


def analyze_sessions(process: pd.DataFrame, cfg: dict, meta: pd.DataFrame, schema: pd.DataFrame,
                     paths: dict, gen_static: bool, gen_html: bool, log) -> dict:
    """Analyse every in-scope session and collect aggregate frames and status rows."""
    agg = {k: [] for k in ("all_windows", "top_windows", "selected", "blocks", "pairwise", "diag", "status", "processed_pids")}
    for row in process.itertuples():
        r = analyze_one_session(row, cfg, meta, schema, paths, gen_static, gen_html, log)
        agg["status"].append(r["status"])
        if r.get("processed"):
            agg["processed_pids"].append(r["pid"])
        for k in ("all_windows", "top_windows", "selected", "blocks", "pairwise", "diag"):
            if k in r:
                agg[k].append(r[k])
    return agg


# --------------------------------------------------------------------------------------------------
# Output writing
# --------------------------------------------------------------------------------------------------
def _cat(frames):
    return pd.concat(frames, ignore_index=True) if frames else None


def write_window_and_target_outputs(agg: dict, paths: dict) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    """Write scanned/selected windows and target block/centre/separation CSVs. Returns (sel, blk, pw)."""
    sel_df = pd.DataFrame(agg["selected"]) if agg["selected"] else None
    blk_df, pw_df = _cat(agg["blocks"]), _cat(agg["pairwise"])
    if agg["all_windows"]:
        _cat(agg["all_windows"]).to_csv(paths["windows"] / "all_scanned_windows.csv", index=False)
    if agg["top_windows"]:
        _cat(agg["top_windows"]).to_csv(paths["windows"] / "top_candidate_windows.csv", index=False)
    if sel_df is not None:
        sel_df.to_csv(paths["windows"] / "selected_windows.csv", index=False)
    if blk_df is not None:
        blk_df.to_csv(paths["targets"] / "target_block_samples.csv", index=False)
        # Generic long-format per-target metrics (works for any target count).
        blk_df.to_csv(paths["targets"] / "window_target_block_metrics.csv", index=False)
        blk_df[["participant_id", "trial_number", "target_id", "median_yaw_deg", "median_pitch_deg", "median_depth_m",
                "centroid_x", "centroid_y", "centroid_z", "within_target_dispersion_deg"]].to_csv(paths["targets"] / "target_centres.csv", index=False)
        blk_df.groupby("target_id").agg(n=("target_id", "size"), median_within_dispersion_deg=("within_target_dispersion_deg", "median"),
            median_yaw_deg=("median_yaw_deg", "median"), median_pitch_deg=("median_pitch_deg", "median")).round(4).reset_index().to_csv(paths["targets"] / "target_quality_summary.csv", index=False)
    if pw_df is not None:
        pw_df.to_csv(paths["targets"] / "target_pairwise_separation.csv", index=False)
    return sel_df, blk_df, pw_df


def write_diagnostics(agg: dict, paths: dict) -> pd.DataFrame | None:
    """Write per-session diagnostic CSVs; returns the diagnostics DataFrame (or None)."""
    if not agg["diag"]:
        return None
    dd = pd.DataFrame(agg["diag"])
    dd.to_csv(paths["diagnostics"] / "window_ranking_diagnostics.csv", index=False)
    dd[["participant_id", "trial_number", "best_score", "margin"]].to_csv(paths["diagnostics"] / "alternative_window_comparison.csv", index=False)
    dd[["participant_id", "trial_number", "exploratory_result", "confidence"]].to_csv(paths["diagnostics"] / "session_qc_summary.csv", index=False)
    dd[dd.review_reasons != ""][["participant_id", "trial_number", "review_reasons"]].to_csv(paths["diagnostics"] / "review_reasons.csv", index=False)
    return dd


def build_inventory(cfg: dict, inv: pd.DataFrame, reporting_pids: list[int], processed_pids: list[int],
                    meta: pd.DataFrame, paths: dict, validation_only: bool = False,
                    schema: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build and write the participant inventory / administrative accounting."""
    pfs = pid_folder_status_factory(cfg, inv)
    valid_pids = set()
    if validation_only and schema is not None and len(schema):
        valid_pids = set(schema.loc[schema.validation_status == "ok", "participant_id"].dropna().astype(int))
    part_inv = build_participant_inventory(cfg, inv, reporting_pids, processed_pids, meta, cfg["status_map"], pfs,
                                           validation_only=validation_only, valid_pids=valid_pids)
    part_inv.to_csv(paths["inventory"] / "requested_participants.csv", index=False)
    admin = part_inv[part_inv.final_participant_status.str.startswith("administrative_no_data")]
    admin.to_csv(paths["inventory"] / "administrative_no_data.csv", index=False)
    admin[["participant_id", "tracker_status", "normalized_admin_status"]].to_csv(paths["metadata"] / "administrative_status.csv", index=False)
    part_inv[(part_inv.gaze_files_found) & (part_inv.missing_trial_indices != "")][["participant_id", "missing_trial_indices", "discovered_trial_indices"]].to_csv(paths["inventory"] / "missing_trials.csv", index=False)
    return part_inv


def write_summaries_and_review(sel_df, blk_df, pw_df, part_inv, cfg, paths):
    """Write cohort summaries and the manual-review manifest; returns the review DataFrame."""
    su = build_summaries(sel_df, blk_df, pw_df, part_inv, cfg)
    su["overall"].to_csv(paths["summaries"] / "overall_summary.csv", index=False)
    for nm in ("participant", "trial", "lod", "williams"):
        if su[nm] is not None:
            su[nm].to_csv(paths["summaries"] / f"{nm}_summary.csv", index=False)
    su["timing"].to_csv(paths["summaries"] / "calibration_timing_summary.csv", index=False)
    su["qc"].to_csv(paths["summaries"] / "qc_status_summary.csv", index=False)
    sel_df.to_csv(paths["summaries"] / "session_summary.csv", index=False)
    if pw_df is not None:
        pw_df.groupby(["target_a", "target_b"]).angular_separation_deg.median().round(3).reset_index().to_csv(paths["summaries"] / "target_separation_summary.csv", index=False)
    rev = sel_df[(sel_df.needs_review == "Yes") | sel_df.exploratory_result.isin(["multiple_similar_windows", "weak_target_separation", "no_valid_window"])]
    rev.to_csv(paths["review"] / "manual_review_manifest.csv", index=False)
    (paths["review"] / "manual_review_report.html").write_text(
        f"<html><body><h2>Manual review manifest</h2><p>{len(rev)} sessions flagged; "
        f"independent video/log review recommended.</p></body></html>")
    return su, rev


def write_excel(sel_df, blk_df, pw_df, part_inv, schema, diag, su, rev, cfg, paths, run_id, msrc, log):
    """Assemble and write the Excel workbook, then validate it (structure + privacy)."""
    forbidden = cfg.get("metadata_map", {}).get("forbidden_tokens", [])
    sheet_map = {
        "Run Information": pd.DataFrame({"field": ["run_id", "study", "metadata_source"],
                                         "value": [run_id, cfg["study"]["id"], msrc["source"]]}),
        "Participant Inventory": part_inv, "Input Validation": schema, "Selected Windows": sel_df,
        "Target Centres": (blk_df[["participant_id", "trial_number", "target_id", "median_yaw_deg", "median_pitch_deg", "centroid_x", "centroid_y", "centroid_z"]] if blk_df is not None else None),
        "Target Separation": pw_df, "Target Quality": blk_df, "Session QC": pd.DataFrame(diag) if diag is not None else None,
        "Review Manifest": rev, "Participant Summary": su["participant"], "Trial Summary": su["trial"],
        "LOD Summary": su["lod"], "Williams Sequence": su["williams"],
        "Administrative No Data": part_inv[part_inv.final_participant_status.str.startswith("administrative_no_data")],
        "Data Dictionary": pd.DataFrame({"field": ["calibration_start_sec", "score", "min_centroid_distance", "confidence", "exploratory_result"],
                                         "meaning": ["selected window start (s)", "window score", "min pairwise centroid distance (3-D gaze-ray)", "High/Medium/Low", "exploratory category"]})}
    # Privacy guard: refuse to export any frame containing a forbidden personal column.
    for nm, df in sheet_map.items():
        leaked = check_forbidden_columns(df, forbidden)
        if leaked:
            raise RuntimeError(f"refusing to write Excel: sheet {nm!r} contains forbidden columns {leaked}")
    dest = excel_writer.write_workbook(sheet_map, paths["excel"] / "aria_rig_calibration_analysis.xlsx", log)
    if dest:
        excel_writer.validate_workbook(dest, sheet_map, paths["validation"] / "excel_validation.csv", log,
                                       forbidden_tokens=forbidden, report_md=paths["validation"] / "excel_validation_report.md")


def write_integrity(before: pd.DataFrame, source_files, config_files, paths) -> str:
    """Re-hash sources after processing, compare, write the three integrity CSVs, and return the verdict."""
    after = integrity.snapshot(source_files, config_files)
    comparison = integrity.compare(before, after)
    before.to_csv(paths["manifest"] / "source_file_hashes_before.csv", index=False)
    after.to_csv(paths["manifest"] / "source_file_hashes_after.csv", index=False)
    comparison.to_csv(paths["manifest"] / "source_integrity_check.csv", index=False)
    return integrity.sources_unmodified(comparison)


def write_config_snapshot(cfg: dict, paths: dict) -> None:
    """Save the merged config (sans internal keys) so a run is reproducible."""
    snap = {k: v for k, v in cfg.items() if not k.startswith("_")}
    (paths["manifest_config_snapshot"] / "merged_config.yml").write_text(
        yaml.safe_dump(snap, sort_keys=False, default_flow_style=False), encoding="utf-8")


# --------------------------------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------------------------------
def run_pipeline(opts: RunOptions) -> RunResult:
    """Execute a full analysis run and return a :class:`RunResult`.

    :param opts: fully-populated run options (see :class:`aria_rig_calibration.models.RunOptions`).
    :return: a summary of the run; all artefacts are written under ``outputs.root/<run_id>``.
    """
    cfg = load_and_validate_config(opts)
    requested = expand_pid_spec(cfg["participants"]["include"])
    trials = list(cfg["trials"]["expected_indices"])

    # Discover first so the run label can reflect the actual (possibly discovered) scope.
    tmp_log = CollectingLogger(None)
    inv_preview = apply_scope(discover_files(cfg, tmp_log), cfg, requested, trials, discover_all=opts.discover_all)
    discovered = sorted(set(inv_preview.loc[inv_preview.in_scope, "participant_id"].dropna().astype(int))) if not inv_preview.empty else []
    reporting_pids = sorted(set(requested) | set(discovered)) if opts.discover_all else requested

    label = scope_run_label(cfg["outputs"].get("run_label", cfg["study"]["id"]), reporting_pids, opts.discover_all)
    paths = make_run_dir(cfg, run_label=label, run_id=opts.run_id, overwrite=opts.overwrite)
    log = CollectingLogger(paths["logs"] / "run.log")
    run_start = datetime.now().isoformat()
    log.info("run %s (study=%s, reporting %d PIDs)", paths["run_id"], cfg["study"]["id"], len(reporting_pids))
    write_config_snapshot(cfg, paths)

    msrc, meta = resolve_run_metadata(cfg, paths, log, opts)
    inv, process = discover_sessions(cfg, log, requested, trials, opts.discover_all, paths)
    schema = validate_sessions(process, cfg, paths)

    # Integrity: hash the exact source files we will read + the config, before processing.
    source_files = list(process.absolute_path) if len(process) else []
    config_files = _config_files(cfg)
    before_hashes = integrity.snapshot(source_files, config_files)

    gen_static = (not opts.validate_only) and any(cfg["outputs"].get(f) for f in ("png", "svg", "pdf"))
    gen_html = (not opts.validate_only) and bool(cfg["outputs"].get("html"))

    if opts.validate_only:
        agg = {k: [] for k in ("all_windows", "top_windows", "selected", "blocks", "pairwise", "diag", "status", "processed_pids")}
    else:
        agg = analyze_sessions(process, cfg, meta, schema, paths, gen_static, gen_html, log)

    sel_df, blk_df, pw_df = write_window_and_target_outputs(agg, paths)
    diag = write_diagnostics(agg, paths)
    part_inv = build_inventory(cfg, inv, reporting_pids, agg["processed_pids"], meta, paths,
                               validation_only=opts.validate_only, schema=schema)

    if sel_df is not None:
        su, rev = write_summaries_and_review(sel_df, blk_df, pw_df, part_inv, cfg, paths)
        write_excel(sel_df, blk_df, pw_df, part_inv, schema, diag, su, rev, cfg, paths, paths["run_id"], msrc, log)
        if gen_static or gen_html:
            try:
                visualization.aggregate_plots(sel_df, blk_df, pw_df, cfg, paths)
            except Exception as e:  # noqa: BLE001
                log.error("aggregate plots: %s", e)

    pd.DataFrame(agg["status"]).to_csv(paths["logs"] / "session_status.csv", index=False)
    pd.DataFrame(log.warnings).to_csv(paths["logs"] / "warnings.csv", index=False)
    pd.DataFrame(log.errors).to_csv(paths["logs"] / "errors.csv", index=False)

    sources_unmodified = write_integrity(before_hashes, source_files, config_files, paths)
    processed = len(sel_df) if sel_df is not None else 0
    manifest = {"run_id": paths["run_id"], "run_start": run_start, "run_end": datetime.now().isoformat(),
                "study": cfg["study"]["id"], "python_version": sys.version.split()[0], "git": _git_info(),
                "reporting_pids": reporting_pids, "requested_pids": requested, "discover_all": opts.discover_all,
                "calibration_search": cfg["calibration_search"], "score_weights": cfg["window_quality"]["scoring"],
                "metadata_source": msrc["source"], "recorded_sessions": len(process), "processed_sessions": processed,
                "target_order": [t["id"] for t in cfg["target"]["targets"]],
                "source_files_unmodified": sources_unmodified,
                "coordinate_frame": "CPF-relative gaze-ray points (yaw/pitch primary; depth-scaled x/y/z)"}
    json.dump(manifest, open(paths["manifest"] / "run_manifest.json", "w"), indent=2, default=str)
    log.info("run complete: %d processed sessions (sources_unmodified=%s)", processed, sources_unmodified)

    return RunResult(run_id=paths["run_id"], run_root=str(paths["run_root"]), recorded_sessions=len(process),
                     processed_sessions=processed, reporting_pids=reporting_pids,
                     metadata_source=msrc["source"], sources_unmodified=sources_unmodified)
