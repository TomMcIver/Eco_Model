import numpy as np
import pandas as pd
import pytest

from eco_model.backtest.metrics import (
    align_pairs,
    block_length,
    bootstrap_ci,
    compute_metrics,
    effective_sample_size,
    interval_metrics,
    moving_block_bootstrap,
    point_metrics,
    revision_sensitivity,
)

from .conftest import ts

Q = pd.Period


def _rows(method, errors, start=0, track="pseudo_oos_revised"):
    return [{"track": track, "target": "t", "horizon": 1, "method": method,
             "origin": ts("2001-01-01") + pd.Timedelta(days=91 * (start + k)),
             "target_period": Q("2001Q1", "Q") + start + k, "point": 0.0,
             "error_first": e, "error_revised": e, "outcome_first": e, "outcome_revised": e,
             "quantiles": {}}
            for k, e in enumerate(errors)]


def test_align_pairs_drops_pairs_missing_for_any_method():
    frame = pd.DataFrame(_rows("persistence", [1.0, 2.0, 3.0])
                         + _rows("historical_mean", [1.0, np.nan, 3.0, 4.0]))

    aligned, info = align_pairs(frame, "error_first")

    assert info["n_pairs"] == 2
    assert info["n_pairs_excluded"] == 2
    assert info["n_valid_by_method"] == {"historical_mean": 3, "persistence": 3}
    assert aligned.groupby("method").size().to_dict() == {"historical_mean": 2, "persistence": 2}


def test_compute_metrics_on_identical_pairs_with_relative_mae():
    frame = pd.DataFrame(_rows("persistence", [1.0, -1.0, 9.0])
                         + _rows("historical_mean", [2.0, -2.0]))

    metrics = compute_metrics(frame, n_boot=50)

    first = metrics[metrics["outcome"] == "first_release"].set_index("method")
    assert first.loc["persistence", "mae"] == pytest.approx(1.0)  # 9.0 pair excluded
    assert first.loc["historical_mean", "rel_mae_vs_persistence"] == pytest.approx(2.0)
    assert first.loc["persistence", "rel_mae_vs_historical_mean"] == pytest.approx(0.5)
    assert first.loc["persistence", "n_pairs_excluded"] == 1
    assert first.loc["persistence", "bias"] == pytest.approx(0.0)


def test_point_metrics_values():
    result = point_metrics(pd.Series([1.0, -3.0, 2.0]))

    assert result == pytest.approx({"mae": 2.0, "rmse": np.sqrt(14 / 3), "bias": 0.0,
                                    "median_ae": 2.0})


def test_interval_coverage_on_hand_made_example():
    quantiles = {0.025: -3, 0.10: -2, 0.25: -1, 0.75: 1, 0.90: 2, 0.975: 3}
    rows = pd.DataFrame({"quantiles": [quantiles, quantiles, quantiles, {}],
                         "outcome": [0.5, 1.5, 2.5, 0.0]})

    result = interval_metrics(rows, "outcome")

    assert result["coverage_50"] == pytest.approx(1 / 3)
    assert result["coverage_80"] == pytest.approx(2 / 3)
    assert result["coverage_95"] == pytest.approx(1.0)
    assert result["width_50"] == pytest.approx(2.0)
    assert result["n_interval_95"] == 3


def test_block_bootstrap_reproducible_with_seed():
    values = np.arange(30, dtype=float)

    a = moving_block_bootstrap(values, 4, n_boot=200, seed=7)
    b = moving_block_bootstrap(values, 4, n_boot=200, seed=7)
    c = moving_block_bootstrap(values, 4, n_boot=200, seed=8)

    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)
    lo, hi = bootstrap_ci(values, 4, n_boot=200, seed=7)
    assert lo < values.mean() < hi
    assert np.isnan(bootstrap_ci([1.0], 1)[0])
    assert moving_block_bootstrap([], 3).size == 0


def test_block_length_rule():
    assert block_length(27, 1) == 3
    assert block_length(27, 8) == 8
    assert block_length(5, 8) == 5


def test_effective_sample_size_shrinks_with_autocorrelation():
    trending = np.linspace(0, 1, 50) + np.sin(np.arange(50))
    assert effective_sample_size(np.ones(5)) == 5
    assert effective_sample_size(np.cumsum(np.ones(50)) + 0.01 * np.arange(50) ** 2) < 50
    assert 1 <= effective_sample_size(trending) <= 50


def test_revision_sensitivity_reports_difference():
    frame = pd.DataFrame(_rows("persistence", [1.0, 2.0])).assign(
        error_revised=[2.0, 4.0], outcome_revised=[2.0, 4.0])

    result = revision_sensitivity(frame).iloc[0]

    assert result["mae_first_minus_revised"] == pytest.approx(1.5 - 3.0)
    assert result["mean_target_revision"] == pytest.approx(1.5)
    assert result["n"] == 2
