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
    @dash_app.callback(Output("tab-content", "children"), Input("tabs", "value"))
    def switch_tab(tab_id: str):
        from app.layout import TAB_LAYOUTS  # avoid circular import at top level
        return TAB_LAYOUTS.get(tab_id, html.Div("Unknown tab"))

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
            events=config.get("forexfactory", {}).get("events", [])
        )
        rows = scraper.get_calendar()
        return rows

    # ------------------------------------------------------------------
    # Macro dashboard tab
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("macro-table", "data"),
        Input("btn-refresh-macro", "n_clicks"),
    )
    def refresh_macro(n_clicks):
        rows = db.fetch_all(
            """
            SELECT event_name, date, actual, forecast, previous
            FROM forex_calendar
            WHERE event_name IN (
                'CPI','CPI m/m','PPI m/m','Non-Farm Employment Change',
                'Unemployment Rate','GDP','Core Retail Sales',
                'Core PCE Price Index m/m','ISM Manufacturing PMI',
                'ISM Services PMI'
            )
            ORDER BY date DESC
            LIMIT 20
            """
        )
        return rows

    # ------------------------------------------------------------------
    # Markets tab – chart
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("market-chart", "figure"),
        Input("market-range-slider", "value"),
        Input("market-normalise", "value"),
    )
    def update_market_chart(range_days, normalise):
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

        normalise_flag = "normalise" in (normalise or [])

        logger.info("[MARKETS] Raw data: %d rows, %d symbols", len(df), df["symbol"].nunique())

        # ── Align all series to a common date range ────────────────
        date_ranges = {}
        for symbol in symbols:
            sym_df = df[df["symbol"] == symbol].dropna(subset=["close"])
            if not sym_df.empty:
                date_ranges[symbol] = (
                    sym_df["date"].min(), sym_df["date"].max()
                )

        if len(date_ranges) > 1:
            common_start = max(d[0] for d in date_ranges.values())
            common_end = min(d[1] for d in date_ranges.values())
            logger.info("[MARKETS] Common range: %s to %s", common_start, common_end)
            if common_start <= common_end:
                before = len(df)
                df = df[(df["date"] >= common_start) & (df["date"] <= common_end)]
                logger.info("[MARKETS] After alignment: %d rows (was %d)", len(df), before)

        fig = go.Figure()

        for symbol in symbols:
            sym_df = df[df["symbol"] == symbol].sort_values("date")
            if sym_df.empty:
                logger.info("[MARKETS] No data for %s after alignment", symbol)
                continue

            display_name = SYMBOL_NAMES.get(symbol, symbol)
            dates = sym_df["date"].tolist()
            closes = sym_df["close"].tolist()

            if normalise_flag and closes and closes[0] != 0:
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
            yaxis_title="Normalised Price" if normalise_flag else "Price (USD)",
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
