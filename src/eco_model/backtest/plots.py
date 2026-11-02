"""Optional diagnostic plots (needs the ``plots`` extra: ``uv sync --extra plots``)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

LEVELS = (50, 80, 95)
PLOT_METHODS = ("historical_mean", "persistence", "ensemble_equal", "ensemble_perf")


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def write_plots(frame: pd.DataFrame, metrics: pd.DataFrame, out_dir: Path) -> list[str]:
    """Write error-over-time and calibration PNGs; returns file names (empty if no matplotlib)."""
    plt = _pyplot()
    if plt is None:
        return []
    written = [name for name in (_error_plot(plt, frame, out_dir),
                                 _calibration_plot(plt, metrics, out_dir)) if name]
    return written


def _error_plot(plt, frame: pd.DataFrame, out_dir: Path) -> str | None:
    err = "error_first" if (frame["track"] == "real_time").any() else "error_revised"
    data = frame[frame["method"].isin(PLOT_METHODS) & frame[err].notna()]
    if data.empty:
        return None
    targets = sorted(data["target"].unique())
    horizons = sorted(data["horizon"].unique())
    fig, axes = plt.subplots(len(targets), len(horizons), figsize=(4 * len(horizons), 2.6 * len(targets)),
                             squeeze=False, sharex=True)
    for i, target in enumerate(targets):
        for j, horizon in enumerate(horizons):
            ax = axes[i][j]
            cell = data[(data["target"] == target) & (data["horizon"] == horizon)]
            for method, g in cell.groupby("method"):
                g = g.sort_values("target_period")
                ax.plot(g["target_period"].dt.to_timestamp(), g[err], label=method, lw=1)
            ax.axhline(0, color="grey", lw=0.5)
            ax.set_title(f"{target} h={horizon}", fontsize=8)
    axes[0][0].legend(fontsize=6)
    fig.suptitle("Forecast error (outcome - forecast) by target quarter", fontsize=10)
    fig.tight_layout()
    name = "errors_over_time.png"
    fig.savefig(out_dir / name, dpi=110)
    plt.close(fig)
    return name


def _calibration_plot(plt, metrics: pd.DataFrame, out_dir: Path) -> str | None:
    cols = [f"coverage_{lv}" for lv in LEVELS]
    if metrics.empty or not set(cols) <= set(metrics.columns):
        return None
    data = metrics.dropna(subset=cols, how="all")
    data = data[data["method"].isin(PLOT_METHODS)]
    if data.empty:
        return None
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0.4, 1], [0.4, 1], color="grey", lw=0.8, label="perfect")
    for method, g in data.groupby("method"):
        means = [g[c].mean() for c in cols]
        ax.plot([lv / 100 for lv in LEVELS], means, marker="o", label=method)
    ax.set_xlabel("nominal coverage")
    ax.set_ylabel("empirical coverage (mean over cells)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    name = "calibration.png"
    fig.savefig(out_dir / name, dpi=110)
    plt.close(fig)
    return name
