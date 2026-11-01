import itertools

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

from eco_model.contracts import MAX_ERRORS_FOR_WEIGHTS, MIN_ERRORS_FOR_WEIGHTS
from eco_model.models.ensemble import (
    ENSEMBLE_MEMBERS,
    combine,
    equal_weights,
    penalised_simplex_weights,
    performance_weights,
    shrink_to_diagonal,
)


def _errors(n: int, sds=(1.0, 1.0, 1.0), seed: int = 0, corr: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    m = len(sds)
    c = np.full((m, m), corr) + (1 - corr) * np.eye(m)
    cov = c * np.outer(sds, sds)
    draws = rng.multivariate_normal(np.zeros(m), cov, size=n)
    return pd.DataFrame(draws, columns=list(ENSEMBLE_MEMBERS)[:m])


def test_members_and_equal_weights():
    assert ENSEMBLE_MEMBERS == ("persistence", "ar", "var3")
    w = equal_weights(ENSEMBLE_MEMBERS)
    assert list(w) == list(ENSEMBLE_MEMBERS)
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["ar"] == pytest.approx(1 / 3)


def test_equal_weights_rejects_empty_or_duplicates():
    with pytest.raises(ValueError):
        equal_weights([])
    with pytest.raises(ValueError):
        equal_weights(["a", "a"])


def test_performance_weights_unavailable_below_minimum():
    # Arrange: 20 rows, one with a NaN, so only 19 common rows remain.
    errors = _errors(MIN_ERRORS_FOR_WEIGHTS)
    errors.iloc[3, 1] = np.nan
    # Act / Assert
    assert performance_weights(errors) is None


def test_performance_weights_available_at_minimum():
    assert performance_weights(_errors(MIN_ERRORS_FOR_WEIGHTS)) is not None


def test_performance_weights_use_only_last_forty_rows():
    # Arrange: older rows make "persistence" terrible; they must be ignored.
    recent = _errors(MAX_ERRORS_FOR_WEIGHTS, seed=1)
    old = recent.iloc[:10].assign(persistence=1000.0 * np.arange(10))
    stacked = pd.concat([old, recent], ignore_index=True)
    # Act
    got = performance_weights(stacked)
    expected = performance_weights(recent)
    # Assert
    assert got == pytest.approx(expected)


def test_weights_nonnegative_sum_to_one_in_column_order():
    # Arrange
    errors = _errors(30, sds=(3.0, 1.0, 0.5), seed=2, corr=0.6)
    # Act
    w = performance_weights(errors)
    # Assert
    assert list(w) == list(errors.columns)
    assert all(v >= 0 for v in w.values())
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-12)


def test_lower_variance_method_gets_more_weight():
    errors = _errors(40, sds=(2.0, 1.0, 1.0), seed=3)
    w = performance_weights(errors)
    assert w["persistence"] < w["ar"]
    assert w["persistence"] < w["var3"]


def test_iid_identical_variance_gives_near_equal_weights_on_average():
    draws = [performance_weights(_errors(40, seed=s)) for s in range(200)]
    mean = pd.DataFrame(draws).mean()
    np.testing.assert_allclose(mean.to_numpy(), np.full(3, 1 / 3), atol=0.02)


def test_shrinkage_keeps_diagonal_and_scales_off_diagonal():
    # Arrange
    errors = _errors(25, sds=(1.0, 2.0, 3.0), seed=4, corr=0.3).to_numpy()
    sample = np.cov(errors, rowvar=False)
    # Act
    shrunk, intensity = shrink_to_diagonal(errors)
    # Assert
    assert 0.0 <= intensity <= 1.0
    np.testing.assert_allclose(np.diag(shrunk), np.diag(sample))
    off = ~np.eye(3, dtype=bool)
    np.testing.assert_allclose(shrunk[off], (1 - intensity) * sample[off])


def test_shrinkage_is_full_when_a_column_is_constant():
    errors = np.column_stack([np.arange(20.0), np.zeros(20)])
    shrunk, intensity = shrink_to_diagonal(errors)
    assert intensity == 1.0
    assert shrunk[0, 1] == 0.0


def test_shrinkage_is_small_for_strongly_correlated_large_sample():
    errors = _errors(2000, seed=8, corr=0.9).to_numpy()
    _, intensity = shrink_to_diagonal(errors)
    assert intensity < 0.05


def test_qp_solver_matches_scipy():
    rng = np.random.default_rng(9)
    for _ in range(25):
        # Arrange
        a = rng.normal(size=(4, 4))
        sigma = a @ a.T
        lam = np.trace(sigma) / 4 * rng.uniform(0, 1)
        target = np.full(4, 0.25)

        def objective(w, sigma=sigma, lam=lam):
            return w @ sigma @ w + lam * np.sum((w - target) ** 2)

        ref = minimize(
            objective,
            target,
            method="SLSQP",
            bounds=[(0, 1)] * 4,
            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
            options={"ftol": 1e-14, "maxiter": 500},
        )
        # Act
        got = penalised_simplex_weights(sigma, lam)
        # Assert
        assert objective(got) <= ref.fun + 1e-9
        np.testing.assert_allclose(got, ref.x, atol=1e-4)


def test_qp_solver_returns_corner_when_one_method_dominates():
    sigma = np.diag([1e-6, 10.0, 10.0])
    w = penalised_simplex_weights(sigma, 0.0)
    assert w[0] == pytest.approx(1.0, abs=1e-4)
    assert np.all(w >= 0)


def test_qp_solver_rejects_bad_input():
    with pytest.raises(ValueError):
        penalised_simplex_weights(np.ones((2, 3)), 1.0)
    with pytest.raises(ValueError):
        penalised_simplex_weights(np.eye(2), -1.0)


def test_degenerate_zero_covariance_gives_equal_weights():
    errors = pd.DataFrame(np.zeros((25, 3)), columns=list(ENSEMBLE_MEMBERS))
    w = performance_weights(errors)
    assert w == pytest.approx(equal_weights(ENSEMBLE_MEMBERS))


def test_performance_weights_do_not_mutate_input():
    errors = _errors(30, seed=5)
    before = errors.copy()
    performance_weights(errors)
    pd.testing.assert_frame_equal(errors, before)


def test_combine_weighted_sum_and_validation():
    points = {"persistence": 1.0, "ar": 2.0, "var3": 4.0}
    assert combine(points, {"persistence": 0.5, "ar": 0.25, "var3": 0.25}) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        combine(points, {"persistence": 0.5, "ar": 0.5})
    with pytest.raises(ValueError):
        combine(points, {"persistence": 0.5, "ar": 0.25, "var3": 0.2})
    with pytest.raises(ValueError):
        combine({**points, "ar": float("nan")}, equal_weights(ENSEMBLE_MEMBERS))
    with pytest.raises(ValueError):
        combine(points, {"persistence": 1.5, "ar": -0.25, "var3": -0.25})


def test_performance_weights_rejects_bad_columns():
    with pytest.raises(ValueError):
        performance_weights(pd.DataFrame())
    dup = pd.DataFrame(np.zeros((25, 2)), columns=["a", "a"])
    with pytest.raises(ValueError):
        performance_weights(dup)


def test_two_method_weights_sum_to_one():
    for sds in itertools.product([0.5, 2.0], repeat=2):
        w = performance_weights(_errors(30, sds=sds, seed=6))
        assert sum(w.values()) == pytest.approx(1.0)
