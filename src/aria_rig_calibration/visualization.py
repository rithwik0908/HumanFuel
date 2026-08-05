"""Per-session + aggregate plots (matplotlib PNG/SVG/PDF; plotly HTML for aggregate). Emphasises
yaw/pitch angular space with the selected window and the three target blocks marked."""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TARGET_COL = {"triview": "#d95f5f", "dashboard": "#4c78a8", "ipad": "#59a14f"}


def _save(fig, name: str, cfg: dict, paths: dict) -> None:
    o = cfg["outputs"]
    for fmt in ("png", "svg", "pdf"):
        if o.get(fmt):
            fig.savefig(paths[f"plots_{fmt}"] / f"{name}.{fmt}", dpi=o.get("plot_dpi", 110), bbox_inches="tight")
    plt.close(fig)


def session_plots(res: dict, cfg: dict, paths: dict) -> None:
    base = f"PID{res['pid']}_trial_{res['trial_index'] + 1}"; tag = res["title_tag"]
    d = res["work"]; d = d[np.isfinite(d.rel_sec)]
    sel = res["sel"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(d.rel_sec, d.yaw_deg, lw=0.4, label="Yaw (deg)")
    ax.plot(d.rel_sec, d.pitch_deg, lw=0.4, label="Pitch (deg)")
    if sel:
        ax.axvspan(sel["start"], sel["end"], alpha=0.12, color="steelblue")
        for b in (sel["start"] + 5, sel["start"] + 10):
            ax.axvline(b, ls=":", color="grey")
    ax.set_title(f"{tag} yaw/pitch vs time (window shaded; triview|dashboard|iPad)")
    ax.set_xlabel("Session time (s)"); ax.set_ylabel("Angle (deg)"); ax.legend(fontsize=8); ax.grid(alpha=.3)
    _save(fig, f"{base}_yaw_pitch_timeline", cfg, paths)
    if sel:
        fig, ax = plt.subplots(figsize=(8, 6))
        for i, b in enumerate(sel["blocks"]):
            tid = cfg["target"]["targets"][i]["id"]
            if len(b):
                ax.scatter(b.yaw_deg, b.pitch_deg, s=6, alpha=0.5, color=TARGET_COL.get(tid, "grey"), label=tid)
        ax.set_title(f"{tag} selected-window gaze by target"); ax.set_xlabel("Yaw (deg)"); ax.set_ylabel("Pitch (deg)")
        ax.legend(fontsize=8); ax.grid(alpha=.3); ax.set_aspect("equal", adjustable="datalim")
        _save(fig, f"{base}_target_yaw_pitch_scatter", cfg, paths)
    if sel and len(res["all_windows"]):
        aw = res["all_windows"].sort_values("window_start_sec")
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(aw.window_start_sec, aw.score, "-o", ms=3, color="grey")
        ax.axvline(sel["start"], color="red", ls="--")
        ax.set_title(f"{tag} candidate-window scores (red=selected {sel['start']:.1f}s)")
        ax.set_xlabel("Window start (s)"); ax.set_ylabel("Legacy score"); ax.grid(alpha=.3)
        _save(fig, f"{base}_candidate_window_scores", cfg, paths)


def aggregate_plots(selected, blocks, pairwise, cfg: dict, paths: dict) -> None:
    det = selected
    if det is None or len(det) == 0:
        return
    fig, ax = plt.subplots(figsize=(9, 5.5)); ax.hist(det.calibration_start_sec, bins=30, color="steelblue")
    ax.axvline(15, ls="--", color="red"); ax.set_title("Calibration start distribution"); ax.set_xlabel("Start (s)"); ax.set_ylabel("Sessions")
    _save(fig, "agg_calibration_start_distribution", cfg, paths)
    fig, ax = plt.subplots(figsize=(9, 5.5)); det.confidence.value_counts().plot.bar(ax=ax, color="seagreen")
    ax.set_title("Confidence distribution"); ax.set_ylabel("Sessions"); _save(fig, "agg_confidence", cfg, paths)
    fig, ax = plt.subplots(figsize=(9, 5.5)); det.exploratory_result.value_counts().plot.barh(ax=ax, color="slateblue")
    ax.set_title("Exploratory result by session"); ax.set_xlabel("Sessions"); _save(fig, "agg_qc_status", cfg, paths)
    if pairwise is not None and len(pairwise):
        fig, ax = plt.subplots(figsize=(9, 5.5)); ax.hist(pairwise.angular_separation_deg.dropna(), bins=30, color="darkorange")
        ax.set_title("Pairwise target angular separation (deg)"); ax.set_xlabel("deg"); ax.set_ylabel("pairs")
        _save(fig, "agg_pairwise_separation", cfg, paths)
    # one HTML aggregate where plotly is available
    try:
        import plotly.express as px
        fig = px.histogram(det, x="calibration_start_sec", nbins=30, title="Calibration start distribution")
        fig.write_html(paths["plots_html"] / "agg_calibration_start_distribution.html", include_plotlyjs="cdn")
    except Exception:  # noqa: BLE001
        pass
