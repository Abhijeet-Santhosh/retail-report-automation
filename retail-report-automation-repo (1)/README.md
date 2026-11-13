# Retail Sales Report Automation (Python)

Turns a raw transactions export into a finished **monthly sales pack** – formatted Excel workbook, charts and a one-page HTML summary – in one command. It replaces the usual manual routine of filtering, pivoting, copy-pasting into a template and re-checking numbers every month.

**Run time:** ~3 seconds per month on 540k rows (11 monthly packs in under 8 seconds).

## What it produces

For each reporting month, `reports/YYYY-MM/` contains:

| Output | Contents |
|---|---|
| `sales_pack_YYYY-MM.xlsx` | **Summary** (KPIs vs last month + trend chart), **Trend**, **Countries** (MoM %, share), **Top products**, **Customer mix** (new vs returning), **Exceptions** (follow-up list), **Data quality** (audit of every row removed) |
| `summary.html` | One-page management summary with KPI cards, charts and exceptions |
| `charts/*.png` | Revenue trend and top-country charts |

KPIs: revenue, orders, average order value, active customers, units, return rate (value) and share of revenue from guest checkouts – each with change vs prior month.

## How it works

```
load_transactions()  ->  clean_transactions()  ->  validate()  ->  KPIs / breakdowns  ->  Excel + HTML + charts
   schema & types        duplicates, fees,         hard checks       pandas groupby        xlsxwriter, matplotlib
                         bad prices, returns
                         split out & logged
```

- **Auditable cleaning:** every exclusion (duplicates, postage/fee codes, zero prices, cancellations) is counted and written to the *Data quality* sheet, so numbers can be reconciled back to the source.
- **Exception-based monitoring:** countries with revenue down more than 25% vs last month (above a minimum size) are flagged for follow-up instead of burying them in a table.
- **Partial months** are detected and excluded automatically.
- **Tested:** `pytest` covers the cleaning rules and KPI logic.

## Run it

```bash
pip install -r requirements.txt
# data: UCI "Online Retail" dataset (CSV or the Online Retail II XLSX both work)
python -m retail_report --input data/online-retail.csv --month 2011-11
python -m retail_report --input data/online-retail.csv --all-months
pytest -q
```

(From the repo root, set `PYTHONPATH=src` or run `pip install -e .`.)

To schedule it, point Windows Task Scheduler or cron at the command above on the first working day of each month.

## Data

[UCI Machine Learning Repository – Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail): ~540k transactions from a UK-based online retailer, Dec 2010 – Dec 2011. The raw file is not committed (see `.gitignore`).

## Project structure

```
src/retail_report/
  pipeline.py   load, clean, validate
  kpis.py       KPI and breakdown calculations
  outputs.py    Excel workbook, charts, HTML summary
  cli.py        command-line entry point
tests/          unit tests for cleaning and KPI logic
```

## Ideas to extend

- Read straight from SQL (Snowflake / SQL Server) instead of a file export
- Email the HTML summary automatically (e.g. via Power Automate or SMTP)
- Add a budget/target file and report variance vs plan
