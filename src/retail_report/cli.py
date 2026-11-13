"""Command line entry point.

    python -m retail_report --input data/online-retail.csv --month 2011-11
    python -m retail_report --input data/online-retail.csv --all-months
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from . import kpis as K
from .outputs import charts, kpi_frame, write_excel, write_html
from .pipeline import clean_transactions, load_transactions, validate

log = logging.getLogger("retail_report")


def build_pack(sales, returns, quality, month: pd.Period, outroot: Path) -> Path:
    outdir = outroot / str(month)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = K.month_summary(sales, returns, month)
    kp = kpi_frame(summary)
    trend = K.monthly_trend(sales, month)
    countries = K.by_country(sales, month)
    products = K.top_products(sales, month)
    mix = K.customer_mix(sales, month)
    flags = K.exceptions(sales, month)
    cp = charts(trend, countries, outdir / "charts")
    xlsx = outdir / f"sales_pack_{month}.xlsx"
    write_excel(xlsx, month, kp, trend, countries, products, mix, flags, quality.as_frame())
    write_html(outdir / "summary.html", month, kp, flags, cp, quality.as_frame())
    log.info("Pack for %s written to %s", month, outdir)
    return xlsx


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Automated monthly sales pack")
    p.add_argument("--input", required=True, help="CSV or XLSX transactions export")
    p.add_argument("--month", help="Reporting month YYYY-MM (default: latest complete month)")
    p.add_argument("--all-months", action="store_true", help="Build a pack for every complete month")
    p.add_argument("--out", default="reports", help="Output folder")
    a = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    t0 = time.perf_counter()
    sales, returns, quality = clean_transactions(load_transactions(a.input))
    problems = validate(sales)
    if problems:
        log.error("Validation failed: %s", "; ".join(problems))
        return 1

    months = sorted(sales["Month"].unique())
    last_day = sales["InvoiceDate"].max()
    if last_day.day < last_day.days_in_month:  # drop a partial final month
        months = months[:-1]

    targets = months[1:] if a.all_months else [pd.Period(a.month, "M") if a.month else months[-1]]
    for m in targets:
        if m not in months:
            log.error("Month %s not in data (available %s to %s)", m, months[0], months[-1])
            return 1
        build_pack(sales, returns, quality, m, Path(a.out))
    log.info("Done: %d pack(s) in %.1fs", len(targets), time.perf_counter() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
