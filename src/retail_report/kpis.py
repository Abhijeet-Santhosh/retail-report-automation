"""KPI and breakdown calculations for a single reporting month."""
from __future__ import annotations

import pandas as pd


def _pct(curr: float, prev: float) -> float | None:
    if prev in (0, None) or pd.isna(prev):
        return None
    return (curr - prev) / prev


def month_summary(sales: pd.DataFrame, returns: pd.DataFrame, month: pd.Period) -> dict:
    """Headline KPIs for `month`, with change vs the previous month."""
    def kpis(m: pd.Period) -> dict:
        s = sales[sales["Month"] == m]
        r = returns[returns["Month"] == m]
        rev = s["Revenue"].sum()
        orders = s["InvoiceNo"].nunique()
        known = s.dropna(subset=["CustomerID"])
        return {
            "Revenue": rev,
            "Orders": orders,
            "Average order value": rev / orders if orders else 0.0,
            "Active customers": known["CustomerID"].nunique(),
            "Units sold": s["Quantity"].sum(),
            "Return rate (value)": r["Revenue"].sum() / rev if rev else 0.0,
            "Share of revenue from guest checkouts": s.loc[s["CustomerID"].isna(), "Revenue"].sum() / rev if rev else 0.0,
        }

    curr, prev = kpis(month), kpis(month - 1)
    return {k: {"value": v, "prev": prev[k], "change": _pct(v, prev[k])} for k, v in curr.items()}


def monthly_trend(sales: pd.DataFrame, upto: pd.Period, months: int = 13) -> pd.DataFrame:
    s = sales[sales["Month"] <= upto]
    t = (s.groupby("Month")
          .agg(Revenue=("Revenue", "sum"), Orders=("InvoiceNo", "nunique"),
               Customers=("CustomerID", "nunique"))
          .tail(months))
    t["AOV"] = t["Revenue"] / t["Orders"]
    return t


def by_country(sales: pd.DataFrame, month: pd.Period, top: int = 10) -> pd.DataFrame:
    def agg(m):
        return sales[sales["Month"] == m].groupby("Country")["Revenue"].sum()
    curr, prev = agg(month), agg(month - 1)
    out = pd.DataFrame({"Revenue": curr, "Prev month": prev}).fillna(0)
    out["MoM %"] = (out["Revenue"] - out["Prev month"]) / out["Prev month"].replace(0, pd.NA)
    out["Share %"] = out["Revenue"] / out["Revenue"].sum()
    return out.sort_values("Revenue", ascending=False).head(top)


def top_products(sales: pd.DataFrame, month: pd.Period, top: int = 15) -> pd.DataFrame:
    s = sales[sales["Month"] == month]
    out = (s.groupby(["StockCode"])
            .agg(Description=("Description", "first"), Units=("Quantity", "sum"),
                 Revenue=("Revenue", "sum"), Orders=("InvoiceNo", "nunique"))
            .sort_values("Revenue", ascending=False).head(top))
    out["Avg price"] = out["Revenue"] / out["Units"]
    return out.reset_index()


def customer_mix(sales: pd.DataFrame, month: pd.Period) -> pd.DataFrame:
    """New vs returning customers in the month (based on first purchase date)."""
    known = sales.dropna(subset=["CustomerID"])
    first_month = known.groupby("CustomerID")["Month"].min()
    s = known[known["Month"] == month].copy()
    s["Type"] = s["CustomerID"].map(lambda c: "New" if first_month[c] == month else "Returning")
    out = s.groupby("Type").agg(Customers=("CustomerID", "nunique"), Revenue=("Revenue", "sum"))
    out["Revenue per customer"] = out["Revenue"] / out["Customers"]
    return out


def exceptions(sales: pd.DataFrame, month: pd.Period, threshold: float = -0.25, min_rev: float = 5000) -> pd.DataFrame:
    """Countries whose revenue dropped more than `threshold` vs last month -> follow-up list."""
    c = by_country(sales, month, top=10_000)
    flagged = c[(c["Prev month"] >= min_rev) & (c["MoM %"] <= threshold)].copy()
    flagged["Action"] = "Review with account owner"
    return flagged
