"""End-to-end synthetic backtest: runner -> outcomes -> ensembles -> metrics -> report."""

import json

import pandas as pd
import pytest

from eco_model.backtest.availability import StoreAvailability
from eco_model.backtest.origins import origin_schedule
from eco_model.backtest.outcomes import build_outcome_tables, first_release_target
from eco_model.backtest.report import flatten_forecasts, markdown_table, write_report
from eco_model.backtest.runner import run_backtest
from eco_model.contracts import GDP_GROWTH, TARGETS, UNEMPLOYMENT, VintageTrack

from .conftest import fake_quantiles, ts

HORIZONS = (1, 4)


@pytest.fixture
def schedule(store):
    return origin_schedule("2001Q2", "2010Q4", StoreAvailability(store))


def _run(store, schedule, forecasters, ensemble_fns, track=VintageTrack.PSEUDO_OOS, seed=0):
    return run_backtest(store, track, schedule, forecasters, HORIZONS, seed=seed,
                        ensemble_fns=ensemble_fns, quantile_fn=fake_quantiles)


def test_run_produces_one_row_per_origin_method_target_horizon(store, schedule, forecasters,
                                                               ensemble_fns):
    result = _run(store, schedule, forecasters, ensemble_fns)

    n_methods = len(forecasters) + 2
    assert len(result) == len(schedule) * n_methods * len(TARGETS) * len(HORIZONS)
    assert (result["target_period"] == result["last_observed"] + result["horizon"]).all()
    assert (result["last_observed"] == result["origin"].map(
        dict(zip(schedule["origin"], schedule["ref_quarter"])))).all()
    assert result.attrs["seed"] == 0 and result.attrs["code_version"]
    assert result.attrs["interval_error_pool"] == "error_revised"


def test_run_is_reproducible(store, schedule, forecasters, ensemble_fns):
    a = _run(store, schedule, forecasters, ensemble_fns)
    b = _run(store, schedule, forecasters, ensemble_fns)

    pd.testing.assert_frame_equal(flatten_forecasts(a), flatten_forecasts(b))
    assert a.attrs["run_id"] == b.attrs["run_id"]
    assert _run(store, schedule, forecasters, ensemble_fns, seed=1).attrs["run_id"] != a.attrs["run_id"]


def test_issued_intervals_only_use_published_outcomes(store, schedule, forecasters, ensemble_fns):
    result = _run(store, schedule, forecasters, ensemble_fns, track=VintageTrack.REAL_TIME)

    for _, row in result[result["interval_n_errors"] > 0].head(50).iterrows():
        same = result[(result["method"] == row["method"]) & (result["target"] == row["target"])
                      & (result["horizon"] == row["horizon"])]
        known = same[(same["origin"] < row["origin"])
                     & (same["outcome_available_at"] <= row["origin"])
                     & same["error_first"].notna()]
        assert row["interval_n_errors"] == len(known)


def test_first_release_outcome_differs_from_revised(store):
    tables = build_outcome_tables(store)

    q = pd.Period("2005Q1", "Q")
    assert tables.first.at[q, UNEMPLOYMENT] == pytest.approx(
        tables.revised.at[q, UNEMPLOYMENT] - 0.4)
    assert first_release_target(store, GDP_GROWTH).notna().all()
    assert tables.revised_as_of


def test_skips_origin_without_data_and_records_failures(store, forecasters, ensemble_fns):
    class Broken:
        name = "broken"

        def forecast(self, history, horizons, seed=0):
            raise ValueError("boom")

    result = run_backtest(store, VintageTrack.REAL_TIME, [ts("1999-01-01"), ts("2004-01-01")],
                          [*forecasters, Broken()], HORIZONS, ensemble_fns=ensemble_fns,
                          quantile_fn=fake_quantiles)

    assert len(result.attrs["skipped_origins"]) == 1
    assert result.attrs["failures"][0]["method"] == "broken"
    assert "broken" not in set(result["method"])


def test_write_report_end_to_end(tmp_path, store, schedule, forecasters, ensemble_fns):
    real = _run(store, schedule, forecasters, ensemble_fns, track=VintageTrack.REAL_TIME)

    out = write_report(real, tmp_path, eval_start=ts("2007-01-01"), n_boot=50)

    text = (out / "report.md").read_text(encoding="utf-8")
    assert out.name == real.attrs["run_id"]
    for name in ("forecasts", "metrics", "revision_sensitivity", "ensemble_weights"):
        assert (out / f"{name}.csv").exists() and (out / f"{name}.parquet").exists()
    assert "NOT a real-time backtest" in text
    assert "does not validate the causal effect" in text.replace("\n  ", " ") or \
        "do not validate the causal effect" in text.replace("\n  ", " ")
    assert "was not used for model" in text
    assert "## Interval coverage" in text and "coverage_50" in text
    metrics = pd.read_csv(out / "metrics.csv")
    assert {"development", "evaluation"} <= set(metrics["segment"])
    assert {"ensemble_equal", "ensemble_perf"} <= set(metrics["method"])
    assert json.loads((out / "run_meta.json").read_text())["seed"] == 0


def test_markdown_table_handles_empty_and_nan():
    assert markdown_table(pd.DataFrame()) == "_no rows_\n"
    assert "n/a" in markdown_table(pd.DataFrame({"a": [float("nan")]}))


def test_report_lists_failures_and_skipped_origins():
    from eco_model.backtest.report import _run_issues

    meta = {"skipped_origins": ["2017-03-31"], "dropped_origins": [],
            "failures": [{"origin": "2020-06-30", "method": "var", "error": "boom"}]}
    text = "\n".join(_run_issues(meta))
    assert "2017-03-31" in text and "boom" in text and "failures: 1" in text
    assert "None:" in "\n".join(_run_issues({}))


def test_run_id_changes_with_data_state():
    from eco_model.backtest.runner import run_id_for
    from eco_model.contracts import VintageTrack

    sched = [(__import__("datetime").datetime(2020, 1, 1), None)]
    a = run_id_for(VintageTrack.REAL_TIME, sched, ["m"], [1], 0, "v", {"gdp": "2026-06-01"})
    b = run_id_for(VintageTrack.REAL_TIME, sched, ["m"], [1], 0, "v", {"gdp": "2026-09-01"})
    assert a != b
