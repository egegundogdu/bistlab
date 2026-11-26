import pandas as pd

from bistlab.credit.scores import operating_profit


def test_operating_profit_prefers_operating_income() -> None:
    items = pd.DataFrame({"Operating Income": [11.49, None], "EBIT": [1.12, 5.0]})
    assert operating_profit(items).tolist() == [11.49, 5.0]


def test_operating_profit_falls_back_to_ebit() -> None:
    items = pd.DataFrame({"EBIT": [1.12]})
    assert operating_profit(items).tolist() == [1.12]
