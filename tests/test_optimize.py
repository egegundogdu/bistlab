import numpy as np
import pytest

from bistlab.portfolio.optimize import efficient_frontier, max_sharpe, min_variance, performance

MU = np.array([0.10, 0.10])
COV = np.array([[0.04, 0.0], [0.0, 0.01]])


def test_min_variance_uses_inverse_variance_weights() -> None:
    # İlişkisiz iki hisse: ağırlık ∝ 1 / varyans → 25 : 100 → %20 / %80
    assert min_variance(MU, COV).weights == pytest.approx([0.2, 0.8], abs=1e-3)


def test_max_weight_cap_is_respected() -> None:
    p = min_variance(MU, COV, max_weight=0.6)
    assert p.weights == pytest.approx([0.4, 0.6], abs=1e-3)
    assert p.weights.sum() == pytest.approx(1.0)


def test_max_sharpe_matches_tangency_portfolio() -> None:
    # Teğet portföy ∝ Σ⁻¹ μ = [0,20 / 0,04, 0,10 / 0,01] = [5, 10] → 1/3, 2/3
    p = max_sharpe(np.array([0.20, 0.10]), COV)
    assert p.weights == pytest.approx([1 / 3, 2 / 3], abs=1e-3)


def test_efficient_frontier_is_monotonic() -> None:
    mu = np.array([0.05, 0.10, 0.20])
    cov = np.diag([0.01, 0.04, 0.09])
    frontier = efficient_frontier(mu, cov, points=6)
    returns = [p.expected_return for p in frontier]
    vols = [p.volatility for p in frontier]
    assert returns == sorted(returns)
    assert all(b >= a - 1e-6 for a, b in zip(vols, vols[1:], strict=False))


def test_infeasible_cap_raises() -> None:
    with pytest.raises(ValueError):
        min_variance(MU, COV, max_weight=0.4)


def test_performance() -> None:
    p = performance(np.array([0.5, 0.5]), MU, COV)
    assert p.expected_return == pytest.approx(0.10)
    assert p.volatility == pytest.approx(np.sqrt(0.25 * 0.04 + 0.25 * 0.01))
