"""Write the monthly pack: formatted Excel workbook, charts and a one-page HTML summary."""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ACCENT = "#1F4E79"


def _fmt(v, kind):
    if v is None or pd.isna(v):
        return "–"
    if kind == "money":
        return f"£{v:,.0f}"
    if kind == "pct":
        return f"{v:+.1%}" if kind == "pct" else f"{v:.1%}"
    return f"{v:,.0f}"


KPI_KIND = {"Revenue": "money", "Orders": "int", "Average order value": "money",
            "Active customers": "int", "Units sold": "int",
            "Return rate (value)": "share", "Share of revenue from guest checkouts": "share"}


def kpi_frame(summary: dict) -> pd.DataFrame:
    rows = []
    for k, d in summary.items():
        rows.append({"KPI": k, "This month": d["value"], "Last month": d["prev"], "Change %": d["change"]})
    return pd.DataFrame(rows)


def charts(trend: pd.DataFrame, countries: pd.DataFrame, outdir: Path) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {}

    fig, ax = plt.subplots(figsize=(8, 3.2))
    x = trend.index.astype(str)
    ax.bar(x, trend["Revenue"] / 1000, color=ACCENT)
    ax.set_ylabel("Revenue (£k)")
    ax.set_title("Monthly revenue trend", loc="left", fontsize=11)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    paths["trend"] = outdir / "revenue_trend.png"
    fig.savefig(paths["trend"], dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.2))
    c = countries.head(8).iloc[::-1]
    ax.barh(c.index, c["Revenue"] / 1000, color=ACCENT)
    ax.set_xlabel("Revenue (£k)")
    ax.set_title("Top countries this month", loc="left", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    paths["countries"] = outdir / "top_countries.png"
    fig.savefig(paths["countries"], dpi=150); plt.close(fig)
    return paths


def write_excel(path: Path, month, kpis: pd.DataFrame, trend, countries, products, mix, flags, quality) -> None:
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        wb = xw.book
        head = wb.add_format({"bold": True, "font_color": "white", "bg_color": ACCENT, "border": 1})
        money = wb.add_format({"num_format": "£#,##0"})
        pct = wb.add_format({"num_format": "+0.0%;-0.0%;0.0%"})
        share = wb.add_format({"num_format": "0.0%"})
        num = wb.add_format({"num_format": "#,##0"})
        title = wb.add_format({"bold": True, "font_size": 14, "font_color": ACCENT})

        def sheet(df, name, formats, index=True):
            df.to_excel(xw, sheet_name=name, startrow=2, index=index)
            ws = xw.sheets[name]
            ws.write(0, 0, f"{name} – {month}", title)
            cols = ([df.index.name or ""] if index else []) + list(df.columns)
            for i, c in enumerate(cols):
                ws.write(2, i, str(c), head)
                ws.set_column(i, i, max(14, min(45, len(str(c)) + 4)), formats.get(c))
            ws.freeze_panes(3, 0)
            return ws

        # Summary sheet: per-row formats because each KPI has its own unit
        kpis.to_excel(xw, sheet_name="Summary", startrow=2, index=False)
        ws = xw.sheets["Summary"]
        ws.write(0, 0, f"Monthly sales pack – {month}", title)
        for i, c in enumerate(kpis.columns):
            ws.write(2, i, c, head)
        ws.set_column(0, 0, 38); ws.set_column(1, 3, 16)
        for r, row in kpis.iterrows():
            kind = KPI_KIND[row["KPI"]]
            f = money if kind == "money" else share if kind == "share" else num
            ws.write_number(3 + r, 1, float(row["This month"]), f)
            ws.write_number(3 + r, 2, float(row["Last month"]), f)
            if pd.notna(row["Change %"]):
                ws.write_number(3 + r, 3, float(row["Change %"]), pct)
        ws.insert_image(12, 0, str(path.parent / "charts" / "revenue_trend.png"), {"x_scale": 0.6, "y_scale": 0.6})

        sheet(trend.rename_axis("Month").reset_index().assign(Month=lambda d: d["Month"].astype(str)), "Trend",
              {"Revenue": money, "AOV": money, "Orders": num, "Customers": num}, index=False)
        sheet(countries.rename_axis("Country"), "Countries",
              {"Revenue": money, "Prev month": money, "MoM %": pct, "Share %": share})
        sheet(products, "Top products", {"Revenue": money, "Units": num, "Avg price": money}, index=False)
        sheet(mix, "Customer mix", {"Revenue": money, "Revenue per customer": money, "Customers": num})
        sheet(flags.rename_axis("Country") if len(flags) else pd.DataFrame({"Note": ["No countries breached the threshold"]}),
              "Exceptions", {"Revenue": money, "Prev month": money, "MoM %": pct, "Share %": share}, index=len(flags) > 0)
        sheet(quality, "Data quality", {"Rows": num}, index=False)


def write_html(path: Path, month, kpis: pd.DataFrame, flags: pd.DataFrame, chart_paths: dict, quality: pd.DataFrame) -> None:
    cards = []
    for _, r in kpis.iterrows():
        kind = KPI_KIND[r["KPI"]]
        val = (f"{r['This month']:.1%}" if kind == "share" else _fmt(r["This month"], kind))
        chg = "" if pd.isna(r["Change %"]) else f"{r['Change %']:+.1%} vs last month"
        cards.append(f"<div class='card'><div class='k'>{html.escape(r['KPI'])}</div>"
                     f"<div class='v'>{val}</div><div class='c'>{chg}</div></div>")
    flag_rows = "".join(f"<li><b>{html.escape(str(i))}</b>: {r['MoM %']:+.0%} vs last month (£{r['Revenue']:,.0f})</li>"
                        for i, r in flags.iterrows()) or "<li>No countries breached the threshold.</li>"
    q = "".join(f"<tr><td>{html.escape(a)}</td><td>{b:,}</td></tr>" for a, b in quality.itertuples(index=False))
    path.write_text(f"""<!doctype html><html><head><meta charset='utf-8'><title>Sales pack {month}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#222;max-width:900px}}
h1{{color:{ACCENT};margin-bottom:4px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.card{{border:1px solid #ddd;border-radius:8px;padding:12px}} .k{{font-size:12px;color:#666}} .v{{font-size:22px;font-weight:600}}
.c{{font-size:12px;color:#444}} img{{max-width:100%}} table{{border-collapse:collapse}} td{{border-bottom:1px solid #eee;padding:4px 12px}}</style>
</head><body><h1>Monthly sales pack – {month}</h1><p>Generated automatically from the transactions export.</p>
<div class='grid'>{''.join(cards)}</div>
<h2>Revenue trend</h2><img src='charts/{chart_paths['trend'].name}'>
<h2>Top countries</h2><img src='charts/{chart_paths['countries'].name}'>
<h2>Exceptions to follow up</h2><ul>{flag_rows}</ul>
<h2>Data quality</h2><table>{q}</table></body></html>""", encoding="utf-8")
