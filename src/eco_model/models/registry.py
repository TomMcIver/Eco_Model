"""The default set of first-slice forecasters, freshly constructed per call."""

from __future__ import annotations

from eco_model.contracts import Forecaster
from eco_model.models.baselines import HistoricalMean, Persistence
from eco_model.models.univariate import AutoRegressive
from eco_model.models.var import CompactVAR


def default_forecasters() -> list[Forecaster]:
    return [Persistence(), HistoricalMean(), AutoRegressive(), CompactVAR()]
