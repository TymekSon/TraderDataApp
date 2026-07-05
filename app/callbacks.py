"""Dash callbacks – wire UI components to data sources."""

import logging
from datetime import date, datetime, timedelta

import pandas as pd
from dash.dependencies import Input, Output, State
from dash import dcc, html

from data.database import Database
from data.db_init import init_db
from scrapers.forex_factory import ForexFactoryScraper
from scrapers.fomc import FOMCScraper
from fetchers.yfinance_fetcher import YFinanceFetcher
from utils.diff_utils import generate_diff_html

logger = logging.getLogger(__name__)


def _scrape_fomc_statements(db):
    """Scrape FOMC statements from the Fed website and insert into DB."""
    scraper = FOMCScraper()
    existing = db.fetch_all("SELECT url FROM fomc_statements")
    existing_urls = {r["url"] for r in existing}

    new_links = scraper.update_statements(existing_urls)
    if not new_links:
        logger.info("[FOMC] No new statements to fetch.")
        return

    for link in new_links:
        result = scraper.fetch_statement_with_date(link["url"])
        if result is None:
            continue
        db.upsert(
            "fomc_statements",
            {
                "date": result["date"],
                "title": result["title"],
                "content": result["content"],
                "url": result["url"],
            },
            conflict_columns=["date", "url"],
        )
        logger.info("[FOMC] Inserted statement: %s — %s", result["date"], result["title"])


def register_callbacks(dash_app, db: Database, config: dict):
    """Attach all Dash callbacks to the app instance."""

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("tab-content", "children"),
        Input("tabs", "value"),
    )
    def switch_tab(tab_id: str):
        from app.layout import TAB_LAYOUTS
        return TAB_LAYOUTS.get(tab_id, html.Div("Unknown tab"))

    # Show/hide macro-charts (always in DOM, race-condition-free)
    @dash_app.callback(
        Output("macro-charts", "style"),
        Input("tabs", "value"),
    )
    def toggle_macro_charts(tab_id: str):
        visible = tab_id == "tab-macro"
        logger.info("[MACRO] toggle_macro_charts: tab=%s visible=%s", tab_id, visible)
        if visible:
            return {"padding": "0 10px", "display": "block"}
        return {"display": "none"}

    # ------------------------------------------------------------------
    # Helper: save scraped rows to DB
    # ------------------------------------------------------------------
    def _save_to_db(rows):
        for row in rows:
            db.upsert(
                "forex_calendar",
                {
                    "date": row.get("date", ""),
                    "time": row.get("time", ""),
                    "currency": row.get("currency", "USD"),
                    "event_name": row.get("event_name", ""),
                    "event_category": row.get("event_category", ""),
                    "importance": row.get("importance", "None"),
                    "actual": row.get("actual", ""),
                    "forecast": row.get("forecast", ""),
                    "previous": row.get("previous", ""),
                    "unit": row.get("unit", ""),
                },
                conflict_columns=["date", "time", "currency", "event_name"],
            )

    # ------------------------------------------------------------------
    # Economic Calendar tab
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("calendar-table", "data"),
        Input("btn-refresh-calendar", "n_clicks"),
        State("calendar-date-range", "start_date"),
        State("calendar-date-range", "end_date"),
    )
    def refresh_calendar(n_clicks, start_date, end_date):
        scraper = ForexFactoryScraper(
            currency=config.get("forexfactory", {}).get("currency", "USD"),
        )
        rows = scraper.get_calendar(start_date=start_date, end_date=end_date)
        _save_to_db(rows)
        logger.info("[CALENDAR] Saved %d events to database", len(rows))
        return rows

    # ------------------------------------------------------------------
    # Macro dashboard tab
    # ------------------------------------------------------------------
    MACRO_INDICATORS = [
        "CPI y/y",
        "CPI m/m",
        "PPI m/m",
        "Core PCE Price Index m/m",
        "GDP",
        "Non-Farm Employment Change",
        "Unemployment Rate",
        "ISM Manufacturing PMI",
        "ISM Services PMI",
        "Retail Sales",
    ]

    @dash_app.callback(
        Output("macro-charts", "children"),
        Input("btn-refresh-macro", "n_clicks"),
        Input("tabs", "value"),
    )
    def refresh_macro(n_clicks, tab_value):
        import plotly.graph_objects as go
        from dash import dcc

        logger.info("[MACRO] refresh_macro fired: tab=%s", tab_value)

        # ── Auto‑scrape when entering macro tab ──────────────────
        if tab_value == "tab-macro":
            matching = db.fetch_one(
                "SELECT COUNT(*) AS n FROM forex_calendar "
                "WHERE event_category IN ({})".format(
                    ",".join("?" for _ in MACRO_INDICATORS)
                ),
                tuple(MACRO_INDICATORS),
            )
            match_n = matching["n"] if matching else 0
            logger.info("[MACRO] DB matching events: %d", match_n)
            if match_n < 20:
                logger.info(
                    "[MACRO] %d matching in DB — scraping 2016→today+30d", match_n
                )
                scraper = ForexFactoryScraper(
                    currency=config.get("forexfactory", {}).get("currency", "USD"),
                )
                year_start = date(2016, 7, 1)
                year_end = date.today() + timedelta(days=30)
                rows = scraper.get_calendar(start_date=year_start, end_date=year_end)
                _save_to_db(rows)
                logger.info("[MACRO] Scraped %d events", len(rows))

        # ── Generate charts from DB ──────────────────────────────
        charts = []
        for ind in MACRO_INDICATORS:
            rows = db.fetch_all(
                "SELECT date, actual, forecast FROM forex_calendar "
                "WHERE event_category = ? AND actual != '' ORDER BY date ASC",
                (ind,),
            )
            if not rows:
                logger.info("[MACRO] No data for %s", ind)
                continue

            logger.info("[MACRO] %s: %d rows, first=%s last=%s",
                         ind, len(rows), rows[0]["date"], rows[-1]["date"])

            dates = [r["date"] for r in rows]
            actuals, forecasts = [], []
            for r in rows:
                try:
                    actuals.append(float(r["actual"].replace("%", "").replace("K", "").replace("M", "").replace("B", "")))
                except (ValueError, AttributeError):
                    actuals.append(None)
                try:
                    forecasts.append(float(r["forecast"].replace("%", "").replace("K", "").replace("M", "").replace("B", "")))
                except (ValueError, AttributeError):
                    forecasts.append(None)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates, y=actuals, mode="lines+markers", name="Actual",
                line=dict(color="#1f77b4", width=2), marker=dict(size=6),
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=forecasts, mode="lines+markers", name="Forecast",
                line=dict(color="#1f77b4", width=2, dash="dot"),
                marker=dict(size=4, symbol="circle-open"), opacity=0.5,
            ))
            fig.update_layout(
                title=ind, height=250,
                margin=dict(l=40, r=20, t=40, b=30),
                legend=dict(orientation="h", y=1.1),
                hovermode="x unified", template="plotly_white",
            )
            charts.append(dcc.Graph(figure=fig))

        if not charts:
            return html.Div(
                "No macro data — scrape in progress or DB empty. Click Refresh.",
                style={"padding": 20, "fontSize": 16, "color": "#888"},
            )

        return html.Div(charts, style={"display": "flex", "flexDirection": "column", "gap": "10px"})

    # ------------------------------------------------------------------
    # Markets tab – chart
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("market-chart", "figure"),
        Input("market-range-slider", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_market_chart(range_days, n_intervals):
        import plotly.graph_objects as go

        symbols = config.get("markets", {}).get("symbols", [])

        # Descriptive names for the UI
        SYMBOL_NAMES = {
            "^TNX": "US 10Y Yield",
            "DX-Y.NYB": "US Dollar Index",
            "BTC-USD": "Bitcoin",
            "GC=F": "Gold",
            "CL=F": "Crude Oil",
            "ES=F": "S&P 500 E-mini",
        }

        end = date.today()
        start = end - timedelta(days=range_days)

        fetcher = YFinanceFetcher()
        df = fetcher.fetch_prices(symbols, start=start, end=end)
        if df.empty:
            logger.info("[MARKETS] No data returned from yfinance")
            fig = go.Figure()
            fig.update_layout(title="Market Prices — no data available")
            return fig

        # ── Persist to database ───────────────────────────────────
        for _, row in df.iterrows():
            db.upsert(
                "market_prices",
                {
                    "symbol": row["symbol"],
                    "date": row["date"],
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                },
                conflict_columns=["symbol", "date"],
            )
        logger.info("[MARKETS] Saved %d rows to market_prices", len(df))

        logger.info("[MARKETS] Raw data: %d rows, %d symbols", len(df), df["symbol"].nunique())

        # ── Plot each symbol with its own full date range ──────────
        fig = go.Figure()

        for symbol in symbols:
            sym_df = df[df["symbol"] == symbol].sort_values("date")
            if sym_df.empty:
                logger.info("[MARKETS] No data for %s after alignment", symbol)
                continue

            display_name = SYMBOL_NAMES.get(symbol, symbol)
            dates = sym_df["date"].tolist()
            closes = sym_df["close"].tolist()

            if closes and closes[0] != 0:
                base = closes[0]
                values = [(c / base) * 100 for c in closes]
            else:
                values = closes

            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=values,
                    mode="lines",
                    name=display_name,
                )
            )

        logger.info("[MARKETS] Figure has %d traces", len(fig.data))

        fig.update_layout(
            title="Market Prices",
            xaxis_title="Date",
            yaxis_title="Normalised Price (start = 100%)",
            hovermode="x unified",
        )
        return fig

    # ------------------------------------------------------------------
    # FOMC diff tab
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("fomc-checklist", "options"),
        Output("fomc-checklist", "value"),
        Input("tabs", "value"),
    )
    def populate_fomc_list(tab_value):
        """Populate checklist with statements; auto-scrape if DB is empty."""
        # ── Auto‑scrape when entering the FOMC tab ──────────────────
        if tab_value == "tab-fomc":
            rows = db.fetch_all("SELECT COUNT(*) AS cnt FROM fomc_statements")
            if rows and rows[0]["cnt"] == 0:
                logger.info("[FOMC] No statements in DB — starting scrape…")
                _scrape_fomc_statements(db)

        rows = db.fetch_all(
            "SELECT id, date, title FROM fomc_statements ORDER BY date DESC"
        )
        options = [
            {"label": f"{r['date']} — {r['title'] or 'Statement'}", "value": r["id"]}
            for r in rows
        ]
        return options, []

    @dash_app.callback(
        Output("fomc-diff-output", "children"),
        Output("fomc-selection-info", "children"),
        Input("fomc-checklist", "value"),
    )
    def show_fomc_diff(selected_ids):
        if len(selected_ids) < 2:
            info = f"Selected {len(selected_ids)}/2 — choose two statements."
            return "Select exactly two statements from the list on the left.", info

        if len(selected_ids) > 2:
            info = "Please un-select one — only two statements can be compared."
            return "Please select exactly two statements.", info

        # Exactly 2 – treat older (smaller id) as old text, newer as new
        old_id, new_id = sorted(selected_ids)

        old_row = db.fetch_one(
            "SELECT content, date, title FROM fomc_statements WHERE id = ?", (old_id,)
        )
        new_row = db.fetch_one(
            "SELECT content, date, title FROM fomc_statements WHERE id = ?", (new_id,)
        )

        if not old_row or not new_row:
            return "Statement not found in database.", ""

        logger.info("[FOMC] Comparing statement %s (%s) vs %s (%s)",
                     old_id, old_row["date"], new_id, new_row["date"])

        diff_html = generate_diff_html(old_row["content"], new_row["content"])
        info = f"Comparing: {old_row['date']} ← → {new_row['date']}"

        # Render raw HTML inside an iframe (safe & reliable in Dash 4.x)
        srcdoc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 10px; white-space: pre-wrap; }}
</style>
</head>
<body>{diff_html}</body>
</html>"""
        return html.Iframe(
            srcDoc=srcdoc,
            style={"width": "100%", "height": "600px", "border": "1px solid #ddd", "borderRadius": 6},
        ), info
