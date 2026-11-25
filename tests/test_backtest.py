import numpy as np
import pandas as pd
import pytest

from bistlab.portfolio.backtest import equal_weight, run_backtest


def _returns(rows: list[list[float]]) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(rows))
    return pd.DataFrame(rows, index=index, columns=["A", "B"])


def test_constant_returns_without_cost() -> None:
    result = run_backtest(_returns([[0.01, 0.01]] * 10), equal_weight, lookback=3, cost=0.0)
    assert list(result.returns) == pytest.approx([0.01] * 7)


def test_initial_purchase_pays_cost() -> None:
    result = run_backtest(_returns([[0.0, 0.0]] * 6), equal_weight, lookback=2, cost=0.01)
    assert result.returns.iloc[0] == pytest.approx(-0.01)  # ilk alım: devir 1
    assert result.returns.iloc[1:].abs().max() == pytest.approx(0.0)


def test_weights_drift_between_rebalances() -> None:
    returns = _returns([[0.0, 0.0], [0.10, 0.0], [0.0, 0.10]])
    result = run_backtest(returns, equal_weight, lookback=1, rebalance_every=100, cost=0.0)
    # 1. gün %5; ağırlıklar 0,55 / 0,50 → B'nin payı 0,5 / 1,05; 2. gün getiri = 0,1 × 0,5 / 1,05
    assert list(result.returns) == pytest.approx([0.05, 0.1 * 0.5 / 1.05])


def test_strategy_never_sees_the_future() -> None:
    returns = _returns([[0.001 * i, 0.0] for i in range(30)])
    seen: list[pd.Timestamp] = []

    def spy(window: pd.DataFrame) -> np.ndarray:
        seen.append(window.index[-1])
        return equal_weight(window)

    run_backtest(returns, spy, lookback=10, rebalance_every=5)
    expected = [returns.index[t - 1] for t in range(10, 30, 5)]
    assert seen == expected


def test_too_short_history_raises() -> None:
    with pytest.raises(ValueError):
        run_backtest(_returns([[0.0, 0.0]] * 5), equal_weight, lookback=5)
