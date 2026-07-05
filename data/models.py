"""Table definitions and schema constants."""

# ---------------------------------------------------------------------------
# Forex Factory calendar table
# ---------------------------------------------------------------------------
FOREX_CALENDAR_TABLE = """
CREATE TABLE IF NOT EXISTS forex_calendar (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    time            TEXT,
    currency        TEXT    DEFAULT 'USD',
    event_name      TEXT    NOT NULL,
    event_category  TEXT,
    importance      TEXT    DEFAULT 'None',
    actual          TEXT,
    forecast        TEXT,
    previous        TEXT,
    unit            TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    UNIQUE(date, time, currency, event_name)
);
"""

FOREX_CALENDAR_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_forex_date ON forex_calendar(date);",
    "CREATE INDEX IF NOT EXISTS idx_forex_event ON forex_calendar(event_name);",
    "CREATE INDEX IF NOT EXISTS idx_forex_category ON forex_calendar(event_category);",
]

# ---------------------------------------------------------------------------
# FOMC statements table
# ---------------------------------------------------------------------------
FOMC_STATEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS fomc_statements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    title       TEXT,
    content     TEXT    NOT NULL,
    url         TEXT,
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(date, url)
);
"""

FOMC_STATEMENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fomc_date ON fomc_statements(date);",
]

# ---------------------------------------------------------------------------
# Market prices table
# ---------------------------------------------------------------------------
MARKET_PRICES_TABLE = """
CREATE TABLE IF NOT EXISTS market_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(symbol, date)
);
"""

MARKET_PRICES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_market_symbol ON market_prices(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_market_date ON market_prices(date);",
]

# ---------------------------------------------------------------------------
# All schemas combined for easy iteration
# ---------------------------------------------------------------------------
ALL_TABLES = [
    (FOREX_CALENDAR_TABLE, FOREX_CALENDAR_INDEXES),
    (FOMC_STATEMENTS_TABLE, FOMC_STATEMENTS_INDEXES),
    (MARKET_PRICES_TABLE, MARKET_PRICES_INDEXES),
]
