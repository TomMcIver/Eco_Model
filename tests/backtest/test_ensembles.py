"""Ensemble weights and intervals must be frozen at issuance (no look-ahead)."""

import pandas as pd
import pytest

from eco_model.backtest.ensembles import (
    ENSEMBLE_EQUAL,
    ENSEMBLE_PERF,
    EnsembleFns,
    add_intervals,
    eligible_past_errors,
    ensemble_rows,
    error_column,
)
from eco_model.contracts import GDP_GROWTH, VintageTrack

from .conftest import fake_combine, fake_equal, fake_quantiles, make_fake_perf, ts

MEMBERS = ("persistence", "ar", "var3")


def _frame(errors_by_origin, published_by_origin, points=None):
    """One target/horizon; one row per origin x member."""
    rows = []
    for k, (origin, errs) in enumerate(errors_by_origin.items()):
        for method, err in zip(MEMBERS, errs):
            rows.append({
                "track": "pseudo_oos_revised", "origin": origin, "method": method,
                "target": GDP_GROWTH, "horizon": 1,
                "last_observed": pd.Period("2000Q1", "Q") + k,
                "target_period": pd.Period("2000Q2", "Q") + k,
                "point": (points or {}).get(method, 1.0), "weights": None, "notes": "",
                "error_revised": err, "outcome_revised": 1.0 + err,
                "outcome_available_at": published_by_origin[origin],
            })
    return pd.DataFrame(rows)


def _fns():
    return EnsembleFns(MEMBERS, fake_equal, make_fake_perf(min_rows=2), fake_combine)


def test_perf_weights_ignore_outcomes_published_after_origin():
    o1, o2, o3, o4 = ts("2001-01-01"), ts("2001-04-01"), ts("2001-07-01"), ts("2001-10-01")
    # o1, o2 outcomes known by o4; o3 outcome published long after o4. Its error
    # pattern (var3 perfect, persistence awful) would flip the weights if used.
    errors = {o1: (0.1, 1.0, 1.0), o2: (0.1, 1.0, 1.0), o3: (5.0, 1.0, 0.0), o4: (0, 0, 0)}
    published = {o1: ts("2001-02-01"), o2: ts("2001-05-01"), o3: ts("2003-01-01"),
                 o4: ts("2003-06-01")}
    frame = _frame(errors, published, points={"persistence": 1.0, "ar": 2.0, "var3": 3.0})

    out = ensemble_rows(frame, _fns(), "error_revised")

    perf = out[(out["method"] == ENSEMBLE_PERF) & (out["origin"] == o4)].iloc[0]
    expected = make_fake_perf(2)(pd.DataFrame([errors[o1], errors[o2]], columns=list(MEMBERS)))
    assert perf["weights"] == pytest.approx(expected)
    assert perf["weights"]["persistence"] > perf["weights"]["var3"]
    leaky = make_fake_perf(2)(pd.DataFrame([errors[o] for o in (o1, o2, o3)], columns=list(MEMBERS)))
    assert leaky["persistence"] < leaky["var3"]  # proves the guard changes the answer


def test_perf_unavailable_falls_back_to_equal_and_is_marked():
    o1, o2 = ts("2001-01-01"), ts("2001-04-01")
    frame = _frame({o1: (1, 1, 1), o2: (1, 1, 1)}, {o1: ts("2002-01-01"), o2: ts("2002-04-01")},
                   points={"persistence": 1.0, "ar": 2.0, "var3": 3.0})

    out = ensemble_rows(frame, _fns(), "error_revised")

    perf = out[(out["method"] == ENSEMBLE_PERF) & (out["origin"] == o2)].iloc[0]
    equal = out[(out["method"] == ENSEMBLE_EQUAL) & (out["origin"] == o2)].iloc[0]
    assert "performance weighting unavailable" in perf["notes"]
    assert perf["point"] == pytest.approx(2.0) == equal["point"]
    assert perf["weights"] == pytest.approx(fake_equal(MEMBERS))


def test_ensemble_skipped_when_member_missing():
    o1 = ts("2001-01-01")
    frame = _frame({o1: (1, 1, 1)}, {o1: ts("2002-01-01")})
    frame = frame[frame["method"] != "var3"]

    assert ensemble_rows(frame, _fns(), "error_revised").empty


def test_eligible_past_errors_requires_all_members_and_published_outcomes():
    o1, o2, o3 = ts("2001-01-01"), ts("2001-04-01"), ts("2001-07-01")
    frame = _frame({o1: (1, 2, float("nan")), o2: (3, 4, 5), o3: (0, 0, 0)},
                   {o1: ts("2001-02-01"), o2: ts("2001-05-01"), o3: ts("2001-08-01")})

    past = eligible_past_errors(frame, o3, "error_revised", MEMBERS)

    assert list(past.index) == [o2]
    assert list(past.columns) == list(MEMBERS)
    assert eligible_past_errors(frame, o1, "error_revised", MEMBERS).empty


def test_intervals_use_only_errors_known_at_issuance():
    origins = [ts(f"200{i}-01-01") for i in range(1, 7)]
    errors = {o: (float(i), 0.0, 0.0) for i, o in enumerate(origins)}
    published = {o: o + pd.Timedelta(days=30) for o in origins}
    published[origins[3]] = ts("2030-01-01")  # never known within sample
    frame = _frame(errors, published)

    out = add_intervals(frame, fake_quantiles, "error_revised")

    last = out[(out["method"] == "persistence") & (out["origin"] == origins[5])].iloc[0]
    assert last["interval_n_errors"] == 4  # origins 0,1,2,4
    assert last["quantiles"][0.975] == pytest.approx(1.0 + pd.Series([0, 1, 2, 4.0]).quantile(0.975))
    first = out[(out["method"] == "persistence") & (out["origin"] == origins[0])].iloc[0]
    assert first["quantiles"] == {} and "interval unavailable" in first["notes"]
    assert "quantiles" not in frame.columns


def test_error_column_by_track():
    assert error_column(VintageTrack.REAL_TIME) == "error_first"
    assert error_column("pseudo_oos_revised") == "error_revised"
