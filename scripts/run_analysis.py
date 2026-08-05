#!/usr/bin/env python
"""Main entry point for the Aria rig-calibration toolkit (Python), legacy_reproduction mode."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aria_rig_calibration.config import load_study_config, validate_config, expand_pid_spec
from aria_rig_calibration.logging_utils import CollectingLogger
from aria_rig_calibration.discovery import discover_files, apply_scope
from aria_rig_calibration.gaze import load_gaze, validate_schema
from aria_rig_calibration.legacy_sliding_window import scan_windows
from aria_rig_calibration.target_blocks import analyze_targets
from aria_rig_calibration.metadata import resolve_metadata, normalize_metadata
from aria_rig_calibration.output_writer import make_run_dir, pid_folder_status_factory, build_participant_inventory, build_summaries
from aria_rig_calibration import visualization, excel_writer


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--study-config", required=True); p.add_argument("--pids"); p.add_argument("--trials")
    p.add_argument("--mode", default="legacy_reproduction"); p.add_argument("--discover-all", action="store_true")
    p.add_argument("--refresh-metadata", action="store_true"); p.add_argument("--offline-metadata", action="store_true")
    p.add_argument("--validate-only", action="store_true"); p.add_argument("--run-id"); p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def main():
    a = parse_args()
    cfg = load_study_config(a.study_config)
    if a.pids: cfg["participants"]["include"] = a.pids.split(",")
    if a.trials: cfg["trials"]["expected_indices"] = expand_pid_spec(a.trials.split(","))
    if a.pids and not a.discover_all: cfg["participants"]["discovery_mode"] = "requested_only"
    ok, probs = validate_config(cfg)
    if not ok: raise SystemExit("config invalid: " + "; ".join(probs))
    requested = expand_pid_spec(cfg["participants"]["include"]); trials = list(cfg["trials"]["expected_indices"])
    paths = make_run_dir(cfg, run_label=cfg["outputs"].get("run_label", cfg["study"]["id"]), run_id=a.run_id, overwrite=a.overwrite)
    lg = CollectingLogger(paths["logs"] / "run.log")
    from datetime import datetime; run_start = datetime.now().isoformat()
    lg.info("run %s (mode=%s study=%s)", paths["run_id"], a.mode, cfg["study"]["id"])

    msrc = resolve_metadata(cfg, paths["metadata_snapshot"], lg, force_offline=(a.offline_metadata and not a.refresh_metadata))
    meta = normalize_metadata(msrc["workbook"], cfg["metadata_map"], msrc["source"], lg)
    meta.to_csv(paths["metadata"] / "participant_trial_metadata.csv", index=False)
    json.dump({"source": msrc["source"], "online": msrc["online"], "fallback_used": msrc["fallback_used"], "rows": len(meta)},
              open(paths["metadata"] / "metadata_source_report.json", "w"), indent=2, default=str)

    inv = discover_files(cfg, lg)
    inv = apply_scope(inv, cfg, requested, trials, discover_all=a.discover_all)
    inv.to_csv(paths["inventory"] / "discovered_files.csv", index=False)
    inv[inv.parse_status.isin(["pid_mismatch", "trial_mismatch", "no_pid", "no_trial"])].to_csv(paths["inventory"] / "ambiguous_files.csv", index=False)
    inv[inv.duplicate_group.notna()].to_csv(paths["inventory"] / "duplicate_files.csv", index=False)
    process = inv[inv.in_scope == True]  # noqa: E712
    lg.info("discovery: %d files, %d in-scope", len(inv), len(process))

    schema = pd.DataFrame([validate_schema(r.absolute_path, r._asdict(), cfg) for r in process.itertuples()]) if len(process) else pd.DataFrame()
    if len(schema): schema.to_csv(paths["validation"] / "schema_validation.csv", index=False)

    aw_all, top_all, selected, blocks, pairwise, diag, status_rows, processed_pids = [], [], [], [], [], [], [], []
    do_plots = cfg["outputs"].get("png", True) and not a.validate_only
    if not a.validate_only:
        for r in process.itertuples():
            pid, ti = int(r.participant_id), int(r.trial_index)
            sv = schema[(schema.participant_id == pid) & (schema.trial_index == ti)] if len(schema) else None
            if sv is not None and len(sv) and sv.validation_status.iloc[0] != "ok":
                status_rows.append({"participant_id": pid, "trial_index": ti, "status": "invalid_data", "reason": sv.exclusion_reason.iloc[0]}); continue
            try:
                g = load_gaze(r.absolute_path, cfg); sw = scan_windows(g["work"], cfg)
                mr = meta[(meta.participant_id == pid) & (meta.trial_index == ti)]
                seqn = mr.sequence_number.iloc[0] if len(mr) else None; lod = mr.lod.iloc[0] if len(mr) else None
                tag = f"PID{pid} T{ti+1} seq{seqn} {lod} |"
                if len(sw["all_windows"]):
                    aw = sw["all_windows"].copy(); aw["participant_id"] = pid; aw["trial_number"] = ti + 1; aw_all.append(aw)
                    top_all.append(aw.head(cfg["outputs"].get("save_top_n_windows", 5)))
                if sw["selected"] is not None:
                    s, rv = sw["selected"], sw["review"]; margin = float(sw["all_windows"].score.iloc[0] - sw["all_windows"].score.iloc[1]) if len(sw["all_windows"]) >= 2 else np.nan
                    notes = rv["notes"]
                    res_cat = ("multiple_similar_windows" if (np.isfinite(margin) and margin < 5 and margin < 0.02 * abs(sw["all_windows"].score.iloc[0]))
                               else "weak_target_separation" if any("not clearly distinct" in n for n in notes)
                               else "insufficient_samples" if any("samples" in n for n in notes)
                               else "selected_with_qc_warning" if notes else "selected_clear")
                    ta = analyze_targets(s, cfg, pid, ti); ta["blocks"]["sequence_number"] = seqn; ta["blocks"]["lod"] = lod
                    blocks.append(ta["blocks"]); pairwise.append(ta["pairwise"])
                    selected.append({"participant_id": pid, "trial_index": ti, "trial_number": ti + 1,
                        "calibration_start_sec": round(s["start"], 4), "calibration_end_sec": round(s["end"], 4),
                        "score": round(s["score"], 4), "min_centroid_distance": round(s["min_dist"], 6), "avg_dispersion": round(s["avg_disp"], 6),
                        "total_samples": s["total_samples"], "block_1_samples": s["summaries"][0]["n"], "block_2_samples": s["summaries"][1]["n"],
                        "block_3_samples": s["summaries"][2]["n"], "confidence": rv["confidence"], "needs_review": "Yes" if rv["needs_review"] else "No",
                        "exploratory_result": res_cat, "best_vs_second_margin": round(margin, 4) if np.isfinite(margin) else None,
                        "window_selected": True, "sequence_number": seqn, "lod": lod, "notes": "; ".join(notes)})
                    diag.append({"participant_id": pid, "trial_number": ti + 1, "n_scanned_windows": len(sw["all_windows"]),
                        "best_score": round(float(sw["all_windows"].score.iloc[0]), 3), "margin": round(margin, 3) if np.isfinite(margin) else None,
                        "exploratory_result": res_cat, "confidence": rv["confidence"], "review_reasons": "; ".join(notes)})
                    if do_plots:
                        try: visualization.session_plots({"pid": pid, "trial_index": ti, "work": g["work"], "sel": s, "all_windows": sw["all_windows"], "title_tag": tag}, cfg, paths)
                        except Exception as e: lg.warning("plot PID%d T%d: %s", pid, ti + 1, e)  # noqa: BLE001
                processed_pids.append(pid)
                status_rows.append({"participant_id": pid, "trial_index": ti, "status": "processed", "reason": None})
            except Exception as e:  # noqa: BLE001
                lg.error("session PID%d T%d: %s", pid, ti + 1, e)
                status_rows.append({"participant_id": pid, "trial_index": ti, "status": "processing_failed", "reason": str(e)})

    cat = lambda l: pd.concat(l, ignore_index=True) if l else None
    sel_df = pd.DataFrame(selected) if selected else None
    blk_df, pw_df = cat(blocks), cat(pairwise)
    if aw_all: cat(aw_all).to_csv(paths["windows"] / "all_scanned_windows.csv", index=False)
    if top_all: cat(top_all).to_csv(paths["windows"] / "top_candidate_windows.csv", index=False)
    if sel_df is not None:
        sel_df.to_csv(paths["windows"] / "selected_windows.csv", index=False)
    if blk_df is not None:
        blk_df.to_csv(paths["targets"] / "target_block_samples.csv", index=False)
        blk_df[["participant_id", "trial_number", "target_id", "median_yaw_deg", "median_pitch_deg", "median_depth_m",
                "centroid_x", "centroid_y", "centroid_z", "within_target_dispersion_deg"]].to_csv(paths["targets"] / "target_centres.csv", index=False)
        blk_df.groupby("target_id").agg(n=("target_id", "size"), median_within_dispersion_deg=("within_target_dispersion_deg", "median"),
            median_yaw_deg=("median_yaw_deg", "median"), median_pitch_deg=("median_pitch_deg", "median")).round(4).reset_index().to_csv(paths["targets"] / "target_quality_summary.csv", index=False)
    if pw_df is not None: pw_df.to_csv(paths["targets"] / "target_pairwise_separation.csv", index=False)
    if diag:
        dd = pd.DataFrame(diag); dd.to_csv(paths["diagnostics"] / "window_ranking_diagnostics.csv", index=False)
        dd[["participant_id", "trial_number", "best_score", "margin"]].to_csv(paths["diagnostics"] / "alternative_window_comparison.csv", index=False)
        dd[["participant_id", "trial_number", "exploratory_result", "confidence"]].to_csv(paths["diagnostics"] / "session_qc_summary.csv", index=False)
        dd[dd.review_reasons != ""][["participant_id", "trial_number", "review_reasons"]].to_csv(paths["diagnostics"] / "review_reasons.csv", index=False)

    pfs = pid_folder_status_factory(cfg, inv)
    part_inv = build_participant_inventory(cfg, inv, requested, processed_pids, meta, cfg["status_map"], pfs)
    part_inv.to_csv(paths["inventory"] / "requested_participants.csv", index=False)
    admin = part_inv[part_inv.final_participant_status.str.startswith("administrative_no_data")]
    admin.to_csv(paths["inventory"] / "administrative_no_data.csv", index=False)
    admin[["participant_id", "tracker_status", "normalized_admin_status"]].to_csv(paths["metadata"] / "administrative_status.csv", index=False)
    part_inv[(part_inv.gaze_files_found) & (part_inv.missing_trial_indices != "")][["participant_id", "missing_trial_indices", "discovered_trial_indices"]].to_csv(paths["inventory"] / "missing_trials.csv", index=False)

    if sel_df is not None:
        su = build_summaries(sel_df, blk_df, pw_df, part_inv, cfg)
        su["overall"].to_csv(paths["summaries"] / "overall_summary.csv", index=False)
        for nm in ("participant", "trial", "lod", "williams"):
            if su[nm] is not None: su[nm].to_csv(paths["summaries"] / f"{nm}_summary.csv", index=False)
        su["timing"].to_csv(paths["summaries"] / "calibration_timing_summary.csv", index=False)
        su["qc"].to_csv(paths["summaries"] / "qc_status_summary.csv", index=False)
        sel_df.to_csv(paths["summaries"] / "session_summary.csv", index=False)
        if pw_df is not None:
            pw_df.groupby(["target_a", "target_b"]).angular_separation_deg.median().round(3).reset_index().to_csv(paths["summaries"] / "target_separation_summary.csv", index=False)
        rev = sel_df[(sel_df.needs_review == "Yes") | sel_df.exploratory_result.isin(["multiple_similar_windows", "weak_target_separation", "no_valid_window"]) | (sel_df.participant_id == 35)]
        rev.to_csv(paths["review"] / "manual_review_manifest.csv", index=False)
        (paths["review"] / "manual_review_report.html").write_text(
            f"<html><body><h2>Manual review manifest</h2><p>{len(rev)} sessions flagged; independent video/log review required.</p></body></html>")
        sm = {"Run Information": pd.DataFrame({"field": ["run_id", "mode", "study", "metadata_source"], "value": [paths["run_id"], a.mode, cfg["study"]["id"], msrc["source"]]}),
            "Participant Inventory": part_inv, "Input Validation": schema, "Selected Windows": sel_df,
            "Top Candidate Windows": cat(top_all), "Target Centres": (blk_df[["participant_id", "trial_number", "target_id", "median_yaw_deg", "median_pitch_deg", "centroid_x", "centroid_y", "centroid_z"]] if blk_df is not None else None),
            "Target Separation": pw_df, "Target Quality": blk_df, "Session QC": pd.DataFrame(diag), "Review Manifest": rev,
            "Participant Summary": su["participant"], "Trial Summary": su["trial"], "LOD Summary": su["lod"], "Williams Sequence": su["williams"],
            "Administrative No Data": admin, "Data Dictionary": pd.DataFrame({"field": ["calibration_start_sec", "score", "min_centroid_distance", "confidence", "exploratory_result"], "meaning": ["selected window start (s)", "legacy score", "min pairwise centroid distance (3D)", "High/Medium/Low", "exploratory category"]})}
        dest = excel_writer.write_workbook(sm, paths["excel"] / "aria_rig_calibration_analysis.xlsx", lg)
        if dest: excel_writer.validate_workbook(dest, sm, paths["validation"] / "excel_validation.csv", lg)
        if do_plots:
            try: visualization.aggregate_plots(sel_df, blk_df, pw_df, cfg, paths)
            except Exception as e: lg.error("aggregate plots: %s", e)  # noqa: BLE001

    pd.DataFrame(status_rows).to_csv(paths["logs"] / "session_status.csv", index=False)
    pd.DataFrame(lg.warnings).to_csv(paths["logs"] / "warnings.csv", index=False)
    pd.DataFrame(lg.errors).to_csv(paths["logs"] / "errors.csv", index=False)
    man = {"run_id": paths["run_id"], "run_start": run_start, "run_end": datetime.now().isoformat(), "mode": a.mode,
        "study": cfg["study"]["id"], "python_version": sys.version.split()[0], "requested_pids": requested,
        "calibration_search": cfg["calibration_search"], "score_weights": cfg["window_quality"]["scoring"],
        "metadata_source": msrc["source"], "recorded_sessions": len(process), "processed_sessions": (len(sel_df) if sel_df is not None else 0),
        "target_order": [t["id"] for t in cfg["target"]["targets"]], "source_files_modified": False, "r_toolkit_modified": False,
        "classification_pipeline_modified": False, "full_session_classification_performed": False,
        "coordinate_frame": "CPF-relative gaze-ray points (yaw/pitch primary; depth-scaled)"}
    json.dump(man, open(paths["manifest"] / "run_manifest.json", "w"), indent=2, default=str)
    lg.info("run complete: %d processed sessions", (len(sel_df) if sel_df is not None else 0))
    print("RUN_ROOT:", paths["run_root"])


if __name__ == "__main__":
    main()
