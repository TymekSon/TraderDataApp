"""Market data fetcher using the yfinance library."""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf
import time

logger = logging.getLogger("YFINANCE")


class YFinanceFetcher:
    """Fetches daily market prices from Yahoo Finance."""

    def __init__(self, range_days: int = 30):
        self.range_days = range_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_prices(
        self,
        symbols: List[str],
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        """Download daily OHLCV data for a list of symbols.

        Each symbol is fetched individually to avoid cross-symbol NaN
        alignment issues in yfinance's MultiIndex (e.g. ^TNX lacks
        Volume, which would drop entire rows for all symbols).

        Returns a DataFrame with columns:
            symbol, date, open, high, low, close, volume, change_pct
        """
        start = start or date.today() - timedelta(days=self.range_days)
        end = end or date.today()

        logger.info(
            "Downloading data for %s from %s to %s", symbols, start, end
        )

        end_iso = (end + timedelta(days=1)).isoformat()

        records = []
        for symbol in symbols:
            try:
                data = yf.download(
                    tickers=symbol,
                    start=start.isoformat(),
                    end=end_iso,
                    auto_adjust=True,
                    progress=False,
                )
                time.sleep(1)
            except Exception as exc:
                logger.warning("[YFINANCE] Failed to download %s: %s", symbol, exc)
                continue

            if data.empty:
                logger.warning("[YFINANCE] No data returned for %s", symbol)
                continue

            # Normalise columns – yfinance may return MultiIndex even for
            # a single ticker, e.g. columns = [('^TNX','Close'), ...]
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(0)

            # Map known OHLCV columns to canonical lowercase names,
            # matching regardless of formatting (e.g. "Adj Close",
            # "Close", "close", "CLOSE").
            column_map = {}
            for c in data.columns:
                col_lower = str(c).strip().lower()
                if "close" in col_lower:
                    column_map[c] = "close"
                elif "open" in col_lower:
                    column_map[c] = "open"
                elif "high" in col_lower:
                    column_map[c] = "high"
                elif "low" in col_lower:
                    column_map[c] = "low"
                elif "volume" in col_lower:
                    column_map[c] = "volume"

            data = data.rename(columns=column_map)

            if "close" not in data.columns:
                logger.warning(
                    "[YFINANCE] No close column found for %s (columns: %s)",
                    symbol, list(data.columns),
                )
                continue

            data = data.dropna(subset=["close"])
            for idx, row in data.iterrows():
                records.append(
                    {
                        "symbol": symbol,
                        "date": idx.date().isoformat(),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                    }
                )

        df = pd.DataFrame(records)
        if not df.empty:
            df["change_pct"] = df.groupby("symbol")["close"].pct_change() * 100
            logger.info("[YFINANCE] Fetched %d rows for %s", len(df), symbols)
        else:
            logger.warning("[YFINANCE] No data returned for any of %s", symbols)

        return df
