import warnings

import numpy as np
import pytest

from eco_model.contracts import CPI_INFLATION, GDP_GROWTH, UNEMPLOYMENT
from eco_model.models.univariate import MIN_AR_OBS, AutoRegressive, fit_ar
from tests.models.helpers import make_history, simulate_ar1


def test_fit_ar_recovers_known_ar1_coefficient():
    # Arrange
    y = simulate_ar1(n=600, intercept=1.0, phi=0.6, seed=42)
    # Act
    fit = fit_ar(y)
    restricted = fit_ar(y, max_lag=1)
    # Assert: AIC may add small extra lags, but total persistence is recovered.
    assert 1 <= fit.lags <= 4
    assert sum(fit.coefs) == pytest.approx(0.6, abs=0.08)
    assert restricted.lags == 1
    assert restricted.coefs[0] == pytest.approx(0.6, abs=0.08)
    assert fit.is_stationary
    assert fit.mean == pytest.approx(2.5, abs=0.3)


def test_ar_forecast_converges_to_mean_at_long_horizon():
    # Arrange
    y = simulate_ar1(n=400, intercept=1.0, phi=0.6, seed=7)
    history = make_history({GDP_GROWTH: y})
    model = AutoRegressive()
    # Act
    result = model.forecast(history, (1, 4, 8, 200))
    # Assert
    fit = fit_ar(y)
    assert model.name == "ar"
    assert result[(GDP_GROWTH, 200)] == pytest.approx(fit.mean, abs=1e-6)
    assert abs(result[(GDP_GROWTH, 8)] - fit.mean) <= abs(result[(GDP_GROWTH, 1)] - fit.mean) + 1e-9
    assert model.last_diagnostics[GDP_GROWTH].startswith("ar(p=")


def test_ar_falls_back_to_persistence_on_short_history():
    # Arrange
    y = simulate_ar1(n=MIN_AR_OBS - 1, intercept=1.0, phi=0.5, seed=3)
    history = make_history({CPI_INFLATION: y})
    model = AutoRegressive()
    # Act
    result = model.forecast(history, (1, 8))
    # Assert
    assert result[(CPI_INFLATION, 1)] == y[-1]
    assert result[(CPI_INFLATION, 8)] == y[-1]
    assert "fallback:persistence" in model.last_diagnostics[CPI_INFLATION]


def test_ar_falls_back_on_explosive_series():
    # Arrange
    rng = np.random.default_rng(0)
    y = 1.08 ** np.arange(80) + rng.normal(scale=0.01, size=80)
    history = make_history({UNEMPLOYMENT: y})
    model = AutoRegressive()
    # Act
    result = model.forecast(history, (1,))
    # Assert
    assert result[(UNEMPLOYMENT, 1)] == y[-1]
    assert "non-stationary" in model.last_diagnostics[UNEMPLOYMENT]


def test_ar_ragged_edge_uses_each_series_own_end():
    # Arrange
    a = simulate_ar1(n=120, intercept=1.0, phi=0.5, seed=11)
    b = simulate_ar1(n=120, intercept=0.5, phi=0.7, seed=12)
    b[-3:] = np.nan
    history = make_history({GDP_GROWTH: a, CPI_INFLATION: b})
    # Act
    result = AutoRegressive().forecast(history, (1, 4))
    alone = AutoRegressive().forecast(history[[CPI_INFLATION]].iloc[:-3], (1, 4))
    # Assert
    assert result[(CPI_INFLATION, 1)] == pytest.approx(alone[(CPI_INFLATION, 1)])
    assert result[(CPI_INFLATION, 4)] == pytest.approx(alone[(CPI_INFLATION, 4)])


def test_ar_uses_trailing_contiguous_block_after_interior_gap():
    # Arrange
    a = simulate_ar1(n=120, intercept=1.0, phi=0.5, seed=13)
    a[50] = np.nan
    history = make_history({GDP_GROWTH: a})
    model = AutoRegressive()
    # Act
    result = model.forecast(history, (1,))
    expected = fit_ar(a[51:]).forecast_path(a[51:], 1)[0]
    # Assert
    assert result[(GDP_GROWTH, 1)] == pytest.approx(expected)
    assert "n=69" in model.last_diagnostics[GDP_GROWTH]


def test_ar_is_deterministic_and_quiet():
    # Arrange
    y = simulate_ar1(n=100, intercept=1.0, phi=0.9, seed=21)
    history = make_history({GDP_GROWTH: y})
    # Act
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        first = AutoRegressive().forecast(history, (1, 4, 8), seed=1)
        second = AutoRegressive().forecast(history, (1, 4, 8), seed=99)
    # Assert
    assert first == second


def test_fit_ar_rejects_too_short_input():
    with pytest.raises(ValueError):
        fit_ar(np.arange(5.0))
