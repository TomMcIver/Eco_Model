"""Markdown report and CSV/Parquet artifacts for a backtest run.

All numbers are computed from the supplied frames at write time; nothing is
hardcoded. Output goes to ``<root>/<run_id>/``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from eco_model.backtest.metrics import compute_metrics, revision_sensitivity
from eco_model.backtest.origins import label_segments
from eco_model.contracts import VintageTrack

QUANTILE_PROBS = (0.025, 0.10, 0.25, 0.75, 0.90, 0.975)
LEADERBOARD_COLS = ["method", "n_pairs", "n_pairs_excluded", "mae", "mae_ci_low",
                    "mae_ci_high", "rmse", "bias", "median_ae",
                    "rel_mae_vs_persistence", "rel_mae_vs_historical_mean"]
COVERAGE_COLS = ["method", "coverage_50", "width_50", "n_interval_50", "coverage_80",
                 "width_80", "n_interval_80", "coverage_95", "width_95", "n_interval_95"]

LIMITATIONS = """\
## Limitations

- **Track labelling.** The `{pseudo}` track uses today's revised data truncated
  at each origin. It is a pseudo-out-of-sample (revised-data) backtest and is
  **NOT a real-time backtest**; its scores must not be pooled with or presented
  as `{real}` scores. Reference quarters whose release time was not verified
  used an assumed publication lag and are labelled in record notes.
- **Forecast accuracy is not causal validation.** These scores measure how well
  methods predicted published outcomes. They do not validate the causal effect
  of any policy and must not be used as evidence of policy-effect accuracy.
- **Development / evaluation split.** {split}
- **Revised outcome** is the latest vintage held in the store at run time, not
  a "final" value. Interval coverage is an empirical diagnostic: quarterly
  errors are dependent, samples are short and multi-step errors overlap.
- Ensemble weights and intervals use only errors whose outcomes were published
  by each origin; on the `{pseudo}` track those outcomes are revised values.
"""


def flatten_forecasts(frame: pd.DataFrame) -> pd.DataFrame:
    """Serialisable copy: quantile columns, JSON weights, string periods."""
    qcols = {f"q_{p:g}": [(q or {}).get(p, np.nan) if isinstance(q, Mapping) else np.nan
                          for q in frame.get("quantiles", [None] * len(frame))]
             for p in QUANTILE_PROBS}
    flat = frame.drop(columns=[c for c in ("quantiles", "weights") if c in frame])
    weights = frame["weights"] if "weights" in frame else [None] * len(frame)
    return flat.assign(
        last_observed=frame["last_observed"].astype(str),
        target_period=frame["target_period"].astype(str),
        weights_json=[json.dumps(w, sort_keys=True) if isinstance(w, Mapping) else ""
                      for w in weights],
        **{k: pd.Series(v, index=frame.index, dtype=float) for k, v in qcols.items()},
    )


def weights_summary(frame: pd.DataFrame) -> pd.DataFrame:
    perf = frame[frame["method"] == "ensemble_perf"]
    rows = []
    for (track, target, horizon), g in perf.groupby(["track", "target", "horizon"], sort=True):
        available = g[~g["notes"].str.contains("unavailable", na=False)]
        weights = pd.DataFrame([w for w in available["weights"] if isinstance(w, Mapping)])
        row = {"track": track, "target": target, "horizon": horizon, "n_origins": len(g),
               "n_perf_weights_available": len(available)}
        row.update({f"mean_w_{m}": float(weights[m].mean()) for m in weights.columns})
        rows.append(row)
    return pd.DataFrame(rows)


def _fmt(value) -> str:
    if isinstance(value, (float, np.floating)):
        return "n/a" if np.isnan(value) else f"{value:.3f}"
    return str(value)


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_no rows_\n"
    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    rule = "|" + "---|" * len(frame.columns)
    body = ["| " + " | ".join(_fmt(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body]) + "\n"


def _sections(metrics: pd.DataFrame, cols: list[str], title: str) -> list[str]:
    out = [f"## {title}\n"]
    if metrics.empty:
        return out + ["_no scored pairs_\n"]
    keys = ["track", "segment", "outcome", "target", "horizon"]
    for values, cell in metrics.groupby(keys, sort=True):
        present = [c for c in cols if c in cell]
        if title.startswith("Interval") and (
            "n_interval_50" not in cell or cell["n_interval_50"].isna().all()
        ):
            continue
        out.append("### " + " / ".join(f"{k}={v}" for k, v in zip(keys, values)) + "\n")
        out.append(markdown_table(cell[present].sort_values("method")))
    return out


def _split_text(eval_start) -> str:
    if eval_start is None:
        return ("No evaluation cut date was supplied: all origins are labelled `all`; "
                "treat these results as development-interval diagnostics only.")
    return (f"Origins before {pd.Timestamp(eval_start).isoformat()} form the development "
            "interval; later origins form the frozen evaluation interval. Methods, "
            "ensemble rules, interval rules and scoring are fixed rules in code; the "
            "evaluation interval was not used for model, weight or protocol selection "
            "by this pipeline (rolling ensemble weights and intervals use only errors "
            "published before each origin). Any manual selection must also have used "
            "development-interval results only.")


def _run_issues(meta) -> list[str]:
    """Skipped origins and forecaster failures, so they are visible in the report itself."""
    skipped, failures = meta.get("skipped_origins") or [], meta.get("failures") or []
    dropped = meta.get("dropped_origins") or []
    lines = ["## Skipped origins and failures\n"]
    if not (skipped or failures or dropped):
        return lines + ["None: every scheduled origin was issued by every method.\n"]
    lines.append(f"Skipped origins: {len(skipped)}; dropped origins: {len(dropped)}; "
                 f"forecaster failures: {len(failures)}. Scores exclude these cases.\n")
    for item in (skipped + dropped)[:20]:
        lines.append(f"- skipped/dropped: `{item}`")
    for item in failures[:20]:
        lines.append(f"- failure: `{item}`")
    return lines + [""]


def render_markdown(frame, metrics, revision, weights, meta, eval_start) -> str:
    lines = [f"# Backtest report `{meta.get('run_id', 'unknown')}`\n",
             "## Run metadata\n",
             "```json\n" + json.dumps(meta, indent=2, sort_keys=True, default=str) + "\n```\n",
             "## Sample counts\n",
             markdown_table(frame.groupby(["track", "segment", "method"]).size()
                            .rename("n_forecasts").reset_index()),
             "Error sign convention: error = outcome - forecast. `rel_mae_vs_X` = "
             "MAE(method)/MAE(X) on identical pairs; below 1 beats the baseline.\n"]
    lines += _sections(metrics, LEADERBOARD_COLS, "Leaderboards")
    lines += _run_issues(meta)
    lines += ["## Ensemble weights summary\n", markdown_table(weights)]
    lines += _sections(metrics, COVERAGE_COLS, "Interval coverage")
    lines += ["## Revision sensitivity\n", markdown_table(revision)]
    lines.append(LIMITATIONS.format(pseudo=VintageTrack.PSEUDO_OOS.value,
                                    real=VintageTrack.REAL_TIME.value, split=_split_text(eval_start)))
    return "\n".join(lines)


def _write_table(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path.with_suffix(".csv"), index=False)
    frame.to_parquet(path.with_suffix(".parquet"), index=False)


def write_report(
    frame: pd.DataFrame,
    root: Path | str,
    *,
    eval_start: datetime | pd.Timestamp | None = None,
    meta: Mapping | None = None,
    n_boot: int = 1000,
    seed: int = 0,
) -> Path:
    """Compute metrics and write report.md + artifacts to ``<root>/<run_id>/``."""
    run_meta = {**dict(frame.attrs), **dict(meta or {}), "eval_start":
                None if eval_start is None else pd.Timestamp(eval_start).isoformat(),
                "bootstrap": {"n_boot": n_boot, "seed": seed,
                              "block_rule": "max(h, round(n ** (1/3)))"}}
    labelled = label_segments(frame, eval_start)
    metrics = compute_metrics(labelled, n_boot=n_boot, seed=seed)
    revision = revision_sensitivity(labelled)
    weights = weights_summary(labelled)
    out_dir = Path(root) / str(run_meta.get("run_id", "run"))
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_table(flatten_forecasts(labelled), out_dir / "forecasts")
    _write_table(metrics, out_dir / "metrics")
    _write_table(revision, out_dir / "revision_sensitivity")
    _write_table(weights, out_dir / "ensemble_weights")
    (out_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, default=str), "utf-8")
    text = render_markdown(labelled, metrics, revision, weights, run_meta, eval_start)
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    return out_dir
