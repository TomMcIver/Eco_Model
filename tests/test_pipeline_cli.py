from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from eco_model.cli import main
from eco_model.contracts import RAW_SERIES, Observation, SourceSnapshot, VintageTrack
from eco_model.data.store import DuckDBObservationStore, ReleaseEntry
from eco_model.pipeline import BacktestConfig, CalendarAvailability, run_track

UTC = timezone.utc
LAG_DAYS = 40


def _release_time(period: pd.Period) -> datetime:
    return period.end_time.to_pydatetime().replace(tzinfo=UTC) + timedelta(days=LAG_DAYS)


def _synthetic_store(path, quarters: pd.PeriodIndex, calendar_from: pd.Period):
    """One vintage per quarter; calendar entries only from `calendar_from` on."""
    rng = np.random.default_rng(0)
    levels = {
        RAW_SERIES[0]: 1000 * np.cumprod(1 + rng.normal(0.005, 0.005, len(quarters))),
        RAW_SERIES[1]: 100 * np.cumprod(1 + rng.normal(0.006, 0.003, len(quarters))),
        RAW_SERIES[2]: 5 + np.cumsum(rng.normal(0, 0.1, len(quarters))),
    }
    store = DuckDBObservationStore(path)
    for i, period in enumerate(quarters):
        published = _release_time(period)
        snap = SourceSnapshot(f"snap{i}", "test", "http://example", published, published,
                              f"f{i}", f"snap{i}", "text/csv", "test")
        store.add_snapshot(snap)
        for series_id, values in levels.items():
            store.add_observations(
                [Observation(series_id, q, float(values[j]), published, snap.snapshot_id)
                 for j, q in enumerate(quarters[: i + 1])])
            if period >= calendar_from:
                store.add_release_entries([ReleaseEntry(series_id, period, f"r{i}", published,
                                                        "http://example", "test")])
    return store


@pytest.fixture
def store(tmp_path):
    quarters = pd.period_range("2000Q1", "2014Q4", freq="Q")
    s = _synthetic_store(tmp_path / "t.duckdb", quarters, pd.Period("2008Q1", "Q"))
    yield s
    s.close() if hasattr(s, "close") else None


def test_calendar_availability_uses_first_dated_release_and_none_before_archive(store):
    calendar = CalendarAvailability(store)

    known = calendar(RAW_SERIES[0], pd.Period("2010Q1", "Q"))
    unknown = calendar(RAW_SERIES[0], pd.Period("2005Q1", "Q"))

    assert known == pd.Timestamp(_release_time(pd.Period("2010Q1", "Q")))
    assert unknown is None


def test_real_time_track_runs_only_on_verified_release_origins(store, tmp_path):
    config = BacktestConfig(track=VintageTrack.REAL_TIME, start="2005Q1", end="2013Q4",
                            eval_start=pd.Timestamp("2012-01-01", tz="UTC"), n_boot=20)

    out = run_track(store, config, tmp_path / "reports")

    forecasts = pd.read_csv(out / "forecasts.csv")
    first_origin = pd.to_datetime(forecasts["origin"]).min()
    assert first_origin >= pd.Timestamp(_release_time(pd.Period("2008Q1", "Q")))
    assert (out / "report.md").read_text(encoding="utf-8")


def test_cli_dispatches_tax_and_requires_assumed_opt_in(capsys):
    args = ["tax", "--dob", "2004-06-15", "--salary", "52000",
            "--pay-frequency", "fortnightly", "--tax-year", "2028"]

    refused = main(args)
    accepted = main([*args, "--allow-assumed"])

    assert refused != 0
    assert accepted == 0
    assert "8008.00" in capsys.readouterr().out


def test_pseudo_oos_never_assumes_a_lag_inside_the_calendar_window(store, tmp_path):
    config = BacktestConfig(track=VintageTrack.PSEUDO_OOS, start="2005Q1", end="2015Q2",
                            eval_start=None, n_boot=20)

    out = run_track(store, config, tmp_path / "reports")

    forecasts = pd.read_csv(out / "forecasts.csv")
    origins = pd.to_datetime(forecasts["origin"])
    assert origins.max() <= pd.Timestamp(_release_time(pd.Period("2014Q4", "Q")) + timedelta(minutes=1))
    assert origins.min() < pd.Timestamp(_release_time(pd.Period("2008Q1", "Q")))
