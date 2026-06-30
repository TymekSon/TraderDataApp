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
    # Markets tab – chart + cards
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("market-chart", "figure"),
        Output("market-cards", "children"),
        Input("market-range-slider", "value"),
        Input("market-normalise", "value"),
    )
    def update_market_chart(range_days, normalise):
        symbols = config.get("markets", {}).get("symbols", [])
        end = date.today()
        start = end - timedelta(days=range_days)

        fetcher = YFinanceFetcher()
        df = fetcher.fetch_prices(symbols, start=start, end=end)
        if df.empty:
            return {}, html.Div("No data available.")

        normalise_flag = "normalise" in (normalise or [])

        import plotly.graph_objects as go

        fig = go.Figure()
        cards = []

        for symbol in symbols:
            sym_df = df[df["symbol"] == symbol].sort_values("date")
            if sym_df.empty:
                continue

            dates = sym_df["date"].tolist()
            closes = sym_df["close"].tolist()

            if normalise_flag and closes and closes[0] != 0:
                base = closes[0]
                values = [(c / base) * 100 for c in closes]
                name_label = f"{symbol} (norm)"
            else:
                values = closes
                name_label = symbol

            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=values,
                    mode="lines",
                    name=name_label,
                )
            )

            # Card with latest change %
            last_row = sym_df.iloc[-1]
            change = last_row.get("change_pct")
            if change is not None:
                color = "green" if change >= 0 else "red"
                cards.append(
                    html.Div(
                        [
                            html.H5(symbol),
                            html.Span(
                                f"{change:+.2f}%",
                                style={"color": color, "fontWeight": "bold"},
                            ),
                        ],
                        style={
                            "border": "1px solid #ddd",
                            "borderRadius": 8,
                            "padding": "10px 15px",
                            "minWidth": 120,
                            "textAlign": "center",
                        },
                    )
                )

        fig.update_layout(
            title="Market Prices",
            xaxis_title="Date",
            yaxis_title="Normalised Price" if normalise_flag else "Price (USD)",
            hovermode="x unified",
        )
        return fig, cards

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
