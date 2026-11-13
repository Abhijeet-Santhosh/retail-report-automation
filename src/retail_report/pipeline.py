"""Load, clean and validate the Online Retail transactions.

Each step is a small pure function so it can be unit-tested and reused.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

RAW_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country"]

# Stock codes that are fees/adjustments rather than products
NON_PRODUCT_CODES = {"POST", "DOT", "M", "C2", "BANK CHARGES", "AMAZONFEE",
                     "CRUK", "PADS", "D", "S", "B", "m"}


@dataclass
class QualityReport:
    """What the cleaning step removed, so every run is auditable."""
    rows_in: int = 0
    rows_out: int = 0
    removed: dict[str, int] = field(default_factory=dict)

    def as_frame(self) -> pd.DataFrame:
        rows = [("Rows loaded", self.rows_in)]
        rows += [(f"Removed: {k}", v) for k, v in self.removed.items()]
        rows.append(("Rows used for reporting", self.rows_out))
        return pd.DataFrame(rows, columns=["Check", "Rows"])


def load_transactions(path: str | Path) -> pd.DataFrame:
    """Read the raw CSV/XLSX export and enforce the expected schema and types."""
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype={"InvoiceNo": str, "StockCode": str})
    else:
        df = pd.read_csv(path, dtype={"InvoiceNo": str, "StockCode": str}, encoding="utf-8")
    # UCI's Online Retail II uses slightly different column names
    df = df.rename(columns={"Invoice": "InvoiceNo", "Price": "UnitPrice", "Customer ID": "CustomerID"})
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Input file is missing columns: {sorted(missing)}")
    df = df[RAW_COLUMNS].copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], format="mixed")
    log.info("Loaded %s rows from %s", f"{len(df):,}", path.name)
    return df


def clean_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, QualityReport]:
    """Split raw rows into clean sales and returns, logging every exclusion.

    Returns (sales, returns, quality_report).
    """
    qr = QualityReport(rows_in=len(df))
    df = df.copy()

    def drop(mask: pd.Series, reason: str) -> None:
        nonlocal df
        qr.removed[reason] = int(mask.sum())
        df = df[~mask]

    drop(df.duplicated(), "exact duplicate rows")
    drop(df["StockCode"].str.upper().isin({c.upper() for c in NON_PRODUCT_CODES}), "fees / postage / manual adjustments")
    drop(df["UnitPrice"] <= 0, "zero or negative unit price")

    is_return = df["InvoiceNo"].str.startswith("C") | (df["Quantity"] < 0)
    returns = df[is_return].copy()
    qr.removed["returns / cancellations (reported separately)"] = int(is_return.sum())
    sales = df[~is_return].copy()

    sales["CustomerID"] = sales["CustomerID"].astype("Int64")
    returns["CustomerID"] = returns["CustomerID"].astype("Int64")
    for frame in (sales, returns):
        frame["Revenue"] = frame["Quantity"] * frame["UnitPrice"]
        frame["Month"] = frame["InvoiceDate"].dt.to_period("M")
    returns["Revenue"] = returns["Revenue"].abs()

    qr.rows_out = len(sales)
    log.info("Clean sales rows: %s | returns rows: %s", f"{len(sales):,}", f"{len(returns):,}")
    return sales, returns, qr


def validate(sales: pd.DataFrame) -> list[str]:
    """Hard checks that should never fail after cleaning. Returns list of problems."""
    problems = []
    if (sales["Quantity"] <= 0).any():
        problems.append("non-positive quantities in sales")
    if (sales["UnitPrice"] <= 0).any():
        problems.append("non-positive prices in sales")
    if sales["InvoiceDate"].isna().any():
        problems.append("missing invoice dates")
    if sales.empty:
        problems.append("no sales rows after cleaning")
    return problems
