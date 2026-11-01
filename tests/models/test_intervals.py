import numpy as np
import pytest

from eco_model.models.intervals import empirical_quantiles, interval_levels_available


def test_no_quantiles_below_twenty_errors():
    assert empirical_quantiles(1.0, [0.1] * 19) == {}


def test_fifty_and_eighty_intervals_from_twenty_errors():
    # Arrange
    base = np.linspace(-1.0, 1.0, 20)
    errors = list(base) + [np.nan, np.nan]
    # Act
    result = empirical_quantiles(2.0, errors)
    # Assert
    assert set(result) == {0.10, 0.25, 0.75, 0.90}
    assert result[0.25] == pytest.approx(2.0 + np.quantile(base, 0.25))
    assert result[0.10] < result[0.25] < result[0.75] < result[0.90]


def test_ninety_five_interval_needs_forty_errors():
    # Arrange
    errors = np.arange(40, dtype=float)
    # Act
    result = empirical_quantiles(0.0, errors)
    # Assert
    assert set(result) == {0.025, 0.10, 0.25, 0.75, 0.90, 0.975}
    assert result[0.975] == pytest.approx(np.quantile(errors, 0.975))


def test_nans_do_not_count_toward_thresholds():
    errors = [0.0] * 39 + [np.nan]
    assert 0.975 not in empirical_quantiles(0.0, errors)


@pytest.mark.parametrize(
    ("n", "expected"),
    [(0, ()), (19, ()), (20, (0.5, 0.8)), (39, (0.5, 0.8)), (40, (0.5, 0.8, 0.95))],
)
def test_interval_levels_available(n, expected):
    assert interval_levels_available(n) == expected


def test_interval_levels_rejects_negative():
    with pytest.raises(ValueError):
        interval_levels_available(-1)


def test_non_finite_point_raises():
    with pytest.raises(ValueError):
        empirical_quantiles(float("nan"), [0.0] * 25)
