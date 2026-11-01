"""Integration: real DuckDB store + real model registry/ensemble/intervals on synthetic vintages."""

from __future__ import annotations

import pandas as pd
import pytest

from eco_model.backtest.availability import StoreAvailability
from eco_model.backtest.origins import origin_schedule
from eco_model.backtest.report import write_report
from eco_model.backtest.runner import run_backtest
from eco_model.contracts import Observation, SourceSnapshot, VintageTrack

from .conftest import make_synthetic_store, ts

store_mod = pytest.importorskip("eco_model.data.store")
registry = pytest.importorskip("eco_model.models.registry")


def _duckdb_from_fake(path, fake):
    db = store_mod.DuckDBObservationStore(path)
    by_release = {}
    for series_id, period, value, published in fake.rows:
        by_release.setdefault((series_id, published), []).append((period, value))
    for (series_id, published), values in by_release.items():
        snap_id = f"{series_id}-{published:%Y%m%d}"
        db.add_snapshot(SourceSnapshot(
            snapshot_id=snap_id, source_id=f"synthetic:{series_id}", url="synthetic://",
            retrieved_at=published.to_pydatetime(), published_at=published.to_pydatetime(),
            file_path="synthetic", sha256=snap_id, media_type="text/csv", licence="test"))
        db.add_observations(Observation(series_id, p, v, published.to_pydatetime(), snap_id)
                            for p, v in values)
    return db


@pytest.mark.parametrize("track", list(VintageTrack))
def test_real_components_end_to_end(tmp_path, track):
    db = _duckdb_from_fake(tmp_path / "obs.duckdb", make_synthetic_store(n=60))
    try:
        schedule = origin_schedule("2003Q1", "2014Q2", StoreAvailability(db))

        result = run_backtest(db, track, schedule, registry.default_forecasters(), (1, 4))
        out = write_report(result, tmp_path / "reports", eval_start=ts("2011-01-01"), n_boot=50)
    finally:
        db.close()

    assert not result.attrs["failures"]
    perf = result[result["method"] == "ensemble_perf"]
    assert (~perf["notes"].str.contains("unavailable")).any()
    assert perf["notes"].str.contains("unavailable").any()
    assert result["quantiles"].map(bool).any()
    assert (out / "report.md").exists()
    metrics = pd.read_csv(out / "metrics.csv")
    assert metrics["coverage_50"].notna().any()
