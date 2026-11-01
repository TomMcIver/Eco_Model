import numpy as np
import pandas as pd
import pytest

from eco_model.contracts import CPI_INFLATION, GDP_GROWTH, UNEMPLOYMENT
from eco_model.models.baselines import HistoricalMean, Persistence
from tests.models.helpers import make_history


def _toy() -> pd.DataFrame:
    return make_history(
        {
            GDP_GROWTH: [np.nan, 1.0, 2.0, 3.0, 4.0],
            CPI_INFLATION: [2.0, 4.0, 6.0, np.nan, np.nan],
            UNEMPLOYMENT: [5.0, 5.5, 6.0, 6.5, 7.0],
        }
    )


def test_persistence_uses_each_targets_own_last_observation():
    # Arrange
    history = _toy()
    # Act
    result = Persistence().forecast(history, (1, 4, 8))
    # Assert
    assert Persistence.name == "persistence"
    assert result[(GDP_GROWTH, 1)] == 4.0
    assert result[(CPI_INFLATION, 8)] == 6.0
    assert result[(UNEMPLOYMENT, 4)] == 7.0
    assert len(result) == 9


def test_historical_mean_averages_available_history():
    # Arrange
    history = _toy()
    # Act
    result = HistoricalMean().forecast(history, (1, 4))
    # Assert
    assert HistoricalMean.name == "historical_mean"
    assert result[(GDP_GROWTH, 1)] == pytest.approx(2.5)
    assert result[(CPI_INFLATION, 4)] == pytest.approx(4.0)
    assert result[(UNEMPLOYMENT, 1)] == pytest.approx(6.0)


def test_all_nan_column_is_omitted():
    # Arrange
    history = _toy().assign(**{CPI_INFLATION: np.nan})
    # Act
    result = Persistence().forecast(history, (1,))
    # Assert
    assert (CPI_INFLATION, 1) not in result
    assert (GDP_GROWTH, 1) in result


def test_inputs_are_not_mutated():
    # Arrange
    history = _toy()
    before = history.copy()
    # Act
    HistoricalMean().forecast(history, (1,))
    # Assert
    pd.testing.assert_frame_equal(history, before)


@pytest.mark.parametrize("horizons", [(0,), (-1,), (1.5,), (), (True,)])
def test_invalid_horizons_raise(horizons):
    with pytest.raises(ValueError):
        Persistence().forecast(_toy(), horizons)


def test_non_period_index_raises():
    history = _toy().reset_index(drop=True)
    with pytest.raises(TypeError):
        Persistence().forecast(history, (1,))


def test_monthly_index_raises():
    history = _toy()
    history.index = pd.period_range("2000-01", periods=5, freq="M")
    with pytest.raises(TypeError):
        Persistence().forecast(history, (1,))


def test_unknown_column_raises():
    history = _toy().rename(columns={GDP_GROWTH: "mystery"})
    with pytest.raises(ValueError):
        Persistence().forecast(history, (1,))


def test_unsorted_index_raises():
    history = _toy().iloc[::-1]
    with pytest.raises(ValueError):
        Persistence().forecast(history, (1,))
