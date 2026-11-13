import pandas as pd
import pytest

from retail_report.pipeline import clean_transactions, validate
from retail_report import kpis as K


@pytest.fixture
def raw():
    return pd.DataFrame({
        "InvoiceNo":   ["1", "1", "2", "C3", "4", "5", "6"],
        "StockCode":   ["85123A", "85123A", "22423", "85123A", "POST", "22423", "85123A"],
        "Description": ["a", "a", "b", "a", "post", "b", "a"],
        "Quantity":    [2, 2, 1, -1, 1, 3, 5],
        "InvoiceDate": pd.to_datetime(["2011-01-05", "2011-01-05", "2011-01-20", "2011-02-02",
                                       "2011-02-03", "2011-02-10", "2011-02-11"]),
        "UnitPrice":   [10.0, 10.0, 5.0, 10.0, 15.0, 0.0, 10.0],
        "CustomerID":  [1, 1, 2, 1, 1, 3, None],
        "Country":     ["UK", "UK", "FR", "UK", "UK", "FR", "UK"],
    })


def test_cleaning_removes_and_logs(raw):
    sales, returns, qr = clean_transactions(raw)
    assert qr.removed["exact duplicate rows"] == 1
    assert qr.removed["fees / postage / manual adjustments"] == 1
    assert qr.removed["zero or negative unit price"] == 1
    assert len(returns) == 1 and returns["Revenue"].iloc[0] == 10
    assert len(sales) == 3
    assert validate(sales) == []


def test_month_summary(raw):
    sales, returns, _ = clean_transactions(raw)
    s = K.month_summary(sales, returns, pd.Period("2011-02", "M"))
    assert s["Revenue"]["value"] == 50          # guest order only
    assert s["Revenue"]["prev"] == 25           # 20 + 5 in January
    assert s["Revenue"]["change"] == pytest.approx(1.0)
    assert s["Share of revenue from guest checkouts"]["value"] == 1.0


def test_customer_mix_new_vs_returning(raw):
    sales, _, _ = clean_transactions(raw)
    mix = K.customer_mix(sales, pd.Period("2011-01", "M"))
    assert mix.loc["New", "Customers"] == 2
