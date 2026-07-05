"""UI layout components for the Dash dashboard."""

from dash import html, dcc, dash_table

# ---------------------------------------------------------------------------
# Top‑level layout
# ---------------------------------------------------------------------------

layout = html.Div(
    children=[
        # ---------- Header ----------
        html.H1(
            "Trader Data App — Fundamental Analysis for ES Futures",
            style={"textAlign": "center", "marginBottom": 30},
        ),
        dcc.Tabs(
            id="tabs",
            value="tab-calendar",
            children=[
                dcc.Tab(label="📅 Economic Calendar", value="tab-calendar"),
                dcc.Tab(label="📊 Macro Dashboard", value="tab-macro"),
                dcc.Tab(label="📈 Market Comparison", value="tab-markets"),
                dcc.Tab(label="📝 FOMC Diff", value="tab-fomc"),
            ],
        ),
        html.Div(id="tab-content", style={"padding": "20px 10px"}),
        # macro-charts always in DOM – avoids race condition with switch_tab
        html.Div(id="macro-charts"),
        # Hidden store for intermediary data
        dcc.Store(id="store-data"),
        # Interval for periodic refresh (optional)
        dcc.Interval(id="interval-refresh", interval=300_000, n_intervals=0),
    ],
    style={"maxWidth": 1400, "margin": "0 auto", "fontFamily": "Arial, sans-serif"},
)

# ---------------------------------------------------------------------------
# Tab layouts
# ---------------------------------------------------------------------------

calendar_tab = html.Div(
    [
        html.Label("Date range:"),
        dcc.DatePickerRange(id="calendar-date-range"),
        html.Button("Refresh", id="btn-refresh-calendar", n_clicks=0),
        dash_table.DataTable(
            id="calendar-table",
            columns=[
                {"name": "Date", "id": "date"},
                {"name": "Time", "id": "time"},
                {"name": "Currency", "id": "currency"},
                {"name": "Event", "id": "event_name"},
                {"name": "Actual", "id": "actual"},
                {"name": "Forecast", "id": "forecast"},
                {"name": "Previous", "id": "previous"},
            ],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "5px"},
        ),
    ]
)

macro_tab = html.Div(
    [
        html.H3("Macroeconomic Indicators — Actual vs Forecast"),
        html.Button("Refresh", id="btn-refresh-macro", n_clicks=0),
    ]
)

markets_tab = html.Div(
    [
        html.H3("Market Price Comparison"),
        dcc.Graph(id="market-chart"),
        html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "20px", "marginTop": 10},
            children=[
                html.Div(style={"flex": 1}, children=[
                    html.Label("Time range (days):"),
                    dcc.Slider(
                        id="market-range-slider",
                        min=7,
                        max=90,
                        step=1,
                        value=30,
                        marks={7: "7d", 14: "14d", 30: "30d", 60: "60d", 90: "90d"},
                    ),
                ]),
            ],
        ),
    ]
)

fomc_tab = html.Div(
    [
        html.H3("Compare FOMC Statements", style={"marginBottom": 20}),
        html.Div(
            style={"display": "flex", "gap": "30px"},
            children=[
                # ── Left column: statement list ──
                html.Div(
                    style={"flex": "0 0 350px", "border": "1px solid #ccc", "borderRadius": 6, "padding": 10},
                    children=[
                        html.H5("Select two statements to compare:", style={"marginTop": 0}),
                        dcc.Checklist(
                            id="fomc-checklist",
                            options=[],
                            value=[],
                            labelStyle={"display": "block", "padding": "3px 0"},
                            inputStyle={"marginRight": 8},
                        ),
                        html.Div(id="fomc-selection-info", style={"marginTop": 10, "fontStyle": "italic", "color": "#888"}),
                    ],
                ),
                # ── Right column: diff output ──
                html.Div(
                    style={"flex": 1, "border": "1px solid #ccc", "borderRadius": 6, "padding": 15, "minHeight": 400},
                    children=[
                        html.H5("Comparison result:", style={"marginTop": 0}),
                        html.Div(
                            id="fomc-diff-output",
                            children="Select exactly two statements from the list on the left.",
                            style={"whiteSpace": "pre-wrap"},
                        ),
                    ],
                ),
            ],
        ),
    ]
)

# Map tab IDs to layouts
TAB_LAYOUTS = {
    "tab-calendar": calendar_tab,
    "tab-macro": macro_tab,
    "tab-markets": markets_tab,
    "tab-fomc": fomc_tab,
}
