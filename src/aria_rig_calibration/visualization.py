"""Plotting.

Role in the pipeline
--------------------
Render per-session and aggregate figures. Static formats (PNG/SVG/PDF) are written with matplotlib and
each format is emitted only when enabled in ``outputs``. One interactive HTML aggregate is written with
plotly when ``outputs.html`` is enabled. Target colours and block boundaries derive from the study's
target configuration, so the module is not specialised to any one study.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_FALLBACK_COLORS = ["#4c78a8", "#59a14f", "#d95f5f", "#b279a2", "#e49444", "#86bcb6"]


def target_colors(cfg: dict) -> list[str]:
    """Return one colour per target, taken from the target config with a fallback palette."""
    targets = cfg["target"]["targets"]
    return [t.get("color") or _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)] for i, t in enumerate(targets)]


def _save_static(fig, name: str, cfg: dict, paths: dict) -> None:
    """Save ``fig`` in each enabled static format (png/svg/pdf), then close it."""
    o = cfg["outputs"]
    for fmt in ("png", "svg", "pdf"):
        if o.get(fmt):
            fig.savefig(paths[f"plots_{fmt}"] / f"{name}.{fmt}", dpi=o.get("plot_dpi", 110), bbox_inches="tight")
    plt.close(fig)


def session_plots(res: dict, cfg: dict, paths: dict) -> None:
    """Write per-session figures: yaw/pitch timeline, per-target scatter, and candidate-score curve.

    :param res: dict with ``pid``, ``trial_index``, ``work`` frame, selected window ``sel``,
        ``all_windows`` DataFrame, and a ``title_tag`` string.
    :param cfg: merged config (for target ids/colours/display names and output formats).
    :param paths: run path map from the output writer.
    """
    base = f"PID{res['pid']}_trial_{res['trial_index'] + 1}"
    tag = res["title_tag"]
    targets = cfg["target"]["targets"]
    colors = target_colors(cfg)
    d = res["work"]
    d = d[np.isfinite(d.rel_sec)]
    sel = res["sel"]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(d.rel_sec, d.yaw_deg, lw=0.4, label="Yaw (deg)")
    ax.plot(d.rel_sec, d.pitch_deg, lw=0.4, label="Pitch (deg)")
    if sel:
        n = len(sel["blocks"])
        blk_len = cfg["calibration_search"]["window_length_sec"] / n
        ax.axvspan(sel["start"], sel["end"], alpha=0.12, color="steelblue")
        for i in range(1, n):  # interior block boundaries derived from the target count
            ax.axvline(sel["start"] + i * blk_len, ls=":", color="grey")
    order = " | ".join(t["display_name"] for t in targets)
    ax.set_title(f"{tag} yaw/pitch vs time (window shaded; {order})")
    ax.set_xlabel("Session time (s)")
    ax.set_ylabel("Angle (deg)")
    ax.legend(fontsize=8)
    ax.grid(alpha=.3)
    _save_static(fig, f"{base}_yaw_pitch_timeline", cfg, paths)

    if sel:
        fig, ax = plt.subplots(figsize=(8, 6))
        for i, block in enumerate(sel["blocks"]):
            if len(block):
                ax.scatter(block.yaw_deg, block.pitch_deg, s=6, alpha=0.5, color=colors[i], label=targets[i]["id"])
        ax.set_title(f"{tag} selected-window gaze by target")
        ax.set_xlabel("Yaw (deg)")
        ax.set_ylabel("Pitch (deg)")
        ax.legend(fontsize=8)
        ax.grid(alpha=.3)
        ax.set_aspect("equal", adjustable="datalim")
        _save_static(fig, f"{base}_target_yaw_pitch_scatter", cfg, paths)

    if sel and len(res["all_windows"]):
        aw = res["all_windows"].sort_values("window_start_sec")
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(aw.window_start_sec, aw.score, "-o", ms=3, color="grey")
        ax.axvline(sel["start"], color="red", ls="--")
        ax.set_title(f"{tag} candidate-window scores (red = selected {sel['start']:.1f}s)")
        ax.set_xlabel("Window start (s)")
        ax.set_ylabel("Window score")
        ax.grid(alpha=.3)
        _save_static(fig, f"{base}_candidate_window_scores", cfg, paths)


def aggregate_plots(selected, blocks, pairwise, cfg: dict, paths: dict) -> None:
    """Write cohort-level figures (start distribution, confidence, exploratory result, separation).

    Static formats honour the ``outputs`` flags; the interactive HTML is written only when
    ``outputs.html`` is enabled.
    """
    det = selected
    if det is None or len(det) == 0:
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.hist(det.calibration_start_sec, bins=30, color="steelblue")
    ax.axvline(15, ls="--", color="red")
    ax.set_title("Calibration start distribution")
    ax.set_xlabel("Start (s)")
    ax.set_ylabel("Sessions")
    _save_static(fig, "agg_calibration_start_distribution", cfg, paths)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    det.confidence.value_counts().plot.bar(ax=ax, color="seagreen")
    ax.set_title("Confidence distribution")
    ax.set_ylabel("Sessions")
    _save_static(fig, "agg_confidence", cfg, paths)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    det.exploratory_result.value_counts().plot.barh(ax=ax, color="slateblue")
    ax.set_title("Exploratory result by session")
    ax.set_xlabel("Sessions")
    _save_static(fig, "agg_qc_status", cfg, paths)

    if pairwise is not None and len(pairwise):
        fig, ax = plt.subplots(figsize=(9, 5.5))
        ax.hist(pairwise.angular_separation_deg.dropna(), bins=30, color="darkorange")
        ax.set_title("Pairwise target angular separation (deg)")
        ax.set_xlabel("deg")
        ax.set_ylabel("pairs")
        _save_static(fig, "agg_pairwise_separation", cfg, paths)

    if cfg["outputs"].get("html"):
        try:
            import plotly.express as px
            fig = px.histogram(det, x="calibration_start_sec", nbins=30, title="Calibration start distribution")
            fig.write_html(paths["plots_html"] / "agg_calibration_start_distribution.html", include_plotlyjs="cdn")
        except Exception:  # noqa: BLE001 - plotly is optional; never fail the run on an HTML plot
            pass
