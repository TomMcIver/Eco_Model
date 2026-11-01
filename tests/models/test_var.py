import warnings

import numpy as np
import pytest

from eco_model.contracts import CPI_INFLATION, GDP_GROWTH, UNEMPLOYMENT
from eco_model.models.var import CompactVAR, fit_var, max_estimable_lag
from tests.models.helpers import (
    STABLE_A,
    TARGET_COLS,
    make_history,
    simulate_ar1,
    stable_var_history,
)


def test_fit_var_recovers_stable_var1():
    # Arrange
    data = stable_var_history(n=600).to_numpy()
    # Act
    fit = fit_var(data, lags=1)
    # Assert
    assert fit.is_stable
    np.testing.assert_allclose(fit.coefs[0], STABLE_A, atol=0.1)


def test_compact_var_is_stable_and_converges_to_mean():
    # Arrange
    history = stable_var_history()
    model = CompactVAR()
    # Act
    result = model.forecast(history, (1, 4, 8, 300))
    # Assert
    assert model.name == "var3"
    assert model.last_diagnostics["model"].startswith("var(p=")
    mean = history.mean()
    for col in TARGET_COLS:
        assert result[(col, 300)] == pytest.approx(mean[col], abs=0.5)
    assert len(result) == 12


def test_compact_var_falls_back_on_short_sample():
    # Arrange
    history = stable_var_history(n=15)
    model = CompactVAR()
    # Act
    result = model.forecast(history, (1, 4))
    # Assert
    assert model.last_diagnostics["model"].startswith("fallback:ar")
    assert result[(GDP_GROWTH, 1)] == history[GDP_GROWTH].iloc[-1]


def test_compact_var_falls_back_on_unstable_data():
    # Arrange
    t = np.arange(120)
    rng = np.random.default_rng(4)
    history = make_history(
        {c: 1.06**t * (j + 1) + rng.normal(scale=0.01, size=120) for j, c in enumerate(TARGET_COLS)}
    )
    model = CompactVAR()
    # Act
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = model.forecast(history, (1,))
    # Assert
    assert model.last_diagnostics["model"].startswith("fallback:ar")
    assert "unstable" in model.last_diagnostics["model"]
    assert set(result) == {(c, 1) for c in TARGET_COLS}


def test_compact_var_falls_back_with_single_series():
    # Arrange
    history = make_history({GDP_GROWTH: simulate_ar1(80, 1.0, 0.5, seed=2)})
    model = CompactVAR()
    # Act
    result = model.forecast(history, (1,))
    # Assert
    assert model.last_diagnostics["model"].startswith("fallback:ar")
    assert (GDP_GROWTH, 1) in result


def test_compact_var_ragged_edge_indexes_from_each_targets_own_end():
    # Arrange: GDP ends two quarters before CPI and unemployment.
    full = stable_var_history(n=200)
    ragged = full.copy()
    ragged.loc[ragged.index[-2:], GDP_GROWTH] = np.nan
    trimmed = full.iloc[:-2]
    model = CompactVAR()
    # Act
    got = model.forecast(ragged, (1, 3))
    ref = CompactVAR().forecast(trimmed, (1, 3))
    # Assert: the common sample is identical, so the fit and path are identical.
    assert got[(GDP_GROWTH, 1)] == pytest.approx(ref[(GDP_GROWTH, 1)])
    assert got[(CPI_INFLATION, 1)] == pytest.approx(ref[(CPI_INFLATION, 3)])
    assert got[(UNEMPLOYMENT, 1)] == pytest.approx(ref[(UNEMPLOYMENT, 3)])
    assert "offset=2" in model.last_diagnostics[CPI_INFLATION]


def test_compact_var_is_deterministic():
    history = stable_var_history(n=120)
    assert CompactVAR().forecast(history, (1, 8)) == CompactVAR().forecast(history, (1, 8), seed=5)


@pytest.mark.parametrize(("n_obs", "expected"), [(200, 4), (30, 2), (20, 1), (12, 0)])
def test_max_estimable_lag_caps_parameter_count(n_obs, expected):
    assert max_estimable_lag(n_obs, k=3) == expected


def test_fit_var_rejects_bad_lags():
    with pytest.raises(ValueError):
        fit_var(np.ones((10, 3)), lags=0)
