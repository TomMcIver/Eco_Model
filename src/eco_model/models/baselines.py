"""Simple benchmark forecasters (VALIDATION_PLAN "Baselines").

Representation: the targets are already rates (q/q GDP growth, y/y CPI
inflation, unemployment rate), so persistence carries the latest *rate*
forward unchanged. Columns with no observations produce no forecasts.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from eco_model.models._common import (
    constant_forecasts,
    observed_columns,
    validate_history,
    validate_horizons,
)


class Persistence:
    """No-change forecast: each target's own last observed value for every h."""

    name = "persistence"

    def forecast(
        self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0
    ) -> Mapping[tuple[str, int], float]:
        validate_history(history)
        hs = validate_horizons(horizons)
        out: dict[tuple[str, int], float] = {}
        for col in observed_columns(history):
            out |= constant_forecasts(col, history[col].dropna().iloc[-1], hs)
        return out


class HistoricalMean:
    """Mean of all of the target's observations available at the origin."""

    name = "historical_mean"

    def forecast(
        self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0
    ) -> Mapping[tuple[str, int], float]:
        validate_history(history)
        hs = validate_horizons(horizons)
        out: dict[tuple[str, int], float] = {}
        for col in observed_columns(history):
            out |= constant_forecasts(col, history[col].dropna().mean(), hs)
        return out
