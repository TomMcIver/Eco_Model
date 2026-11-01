"""In-memory fakes for backtest tests (never used in src)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pytest

from eco_model.backtest.ensembles import EnsembleFns
from eco_model.contracts import RAW_CPI_INDEX, RAW_GDP_LEVEL, RAW_UNEMPLOYMENT

UTC = "UTC"
LAG_DAYS = {RAW_GDP_LEVEL: 70, RAW_CPI_INDEX: 20, RAW_UNEMPLOYMENT: 35}


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz=UTC)


@dataclass
class FakeStore:
    """rows: (series_id, ref_period, value, published_at)."""

    rows: list[tuple[str, pd.Period, float, pd.Timestamp]] = field(default_factory=list)

    def _frame(self, series_id: str) -> pd.DataFrame:
        data = [r for r in self.rows if r[0] == series_id]
        return pd.DataFrame(data, columns=["series", "period", "value", "published"])

    def as_of(self, series_id, as_of) -> pd.Series:
        df = self._frame(series_id)
        df = df[df["published"] <= pd.Timestamp(as_of)]
        return self._pick(df, last=True)

    def first_release(self, series_id) -> pd.Series:
        return self._pick(self._frame(series_id), last=False)

    def latest(self, series_id) -> pd.Series:
        return self._pick(self._frame(series_id), last=True)

    def release_times(self, series_id) -> list:
        return sorted(set(self._frame(series_id)["published"]))

    @staticmethod
    def _pick(df: pd.DataFrame, last: bool) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float, index=pd.PeriodIndex([], freq="Q"))
        df = df.sort_values("published")
        picked = df.groupby("period").last() if last else df.groupby("period").first()
        out = picked["value"].astype(float)
        out.index = pd.PeriodIndex(out.index, freq="Q")
        return out.sort_index()


def _true_values(n: int) -> dict[str, np.ndarray]:
    i = np.arange(n)
    rng = np.random.default_rng(42)
    return {
        RAW_GDP_LEVEL: 100 * 1.006 ** i + rng.normal(0, 0.3, n),
        RAW_CPI_INDEX: 100 * 1.007 ** i + rng.normal(0, 0.1, n),
        RAW_UNEMPLOYMENT: 5 + np.sin(i / 3) + rng.normal(0, 0.1, n),
    }


def make_synthetic_store(start: str = "2000Q1", n: int = 48, revision: float = 0.4) -> FakeStore:
    """Each quarter q is published at q-end + lag; that release revises q-1 by ``revision``."""
    periods = pd.period_range(start, periods=n, freq="Q")
    values = _true_values(n)
    rows = []
    for series_id, vals in values.items():
        for k, period in enumerate(periods):
            released = pd.Timestamp(period.end_time, tz=UTC) + pd.Timedelta(days=LAG_DAYS[series_id])
            rows.append((series_id, period, float(vals[k]), released))
            if k > 0:
                rows.append((series_id, periods[k - 1], float(vals[k - 1] + revision), released))
    return FakeStore(rows)


@dataclass(frozen=True)
class LastValue:
    name: str = "persistence"
    shift: float = 0.0

    def forecast(self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0):
        return {(t, h): float(history[t].dropna().iloc[-1]) + self.shift
                for t in history.columns for h in horizons}


@dataclass(frozen=True)
class MeanValue:
    name: str = "historical_mean"

    def forecast(self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0):
        return {(t, h): float(history[t].mean()) for t in history.columns for h in horizons}


def fake_equal(methods: Sequence[str]) -> dict[str, float]:
    return {m: 1.0 / len(methods) for m in methods}


def fake_combine(points: Mapping[str, float], weights: Mapping[str, float]) -> float:
    return float(sum(points[m] * w for m, w in weights.items()))


def make_fake_perf(min_rows: int = 3):
    def perf(errors: pd.DataFrame):
        if len(errors) < min_rows:
            return None
        inv = 1.0 / errors.abs().mean().clip(lower=1e-9)
        return (inv / inv.sum()).to_dict()

    return perf


def fake_quantiles(point: float, errors: pd.Series) -> dict[float, float]:
    if len(errors) < 3:
        return {}
    probs = (0.025, 0.10, 0.25, 0.75, 0.90, 0.975)
    return {p: point + float(np.quantile(errors, p)) for p in probs}


@pytest.fixture
def store() -> FakeStore:
    return make_synthetic_store()


@pytest.fixture
def forecasters():
    return [LastValue(), MeanValue(), LastValue(name="ar", shift=0.1),
            LastValue(name="var3", shift=-0.2)]


@pytest.fixture
def ensemble_fns() -> EnsembleFns:
    return EnsembleFns(members=("persistence", "ar", "var3"), equal_weights=fake_equal,
                       performance_weights=make_fake_perf(3), combine=fake_combine)
