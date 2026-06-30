"""Market data fetcher using the yfinance library."""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf

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

        Returns a DataFrame with columns:
            symbol, date, open, high, low, close, volume, change_pct
        """
        start = start or date.today() - timedelta(days=self.range_days)
        end = end or date.today()

        logger.info(
            "Downloading data for %s from %s to %s", symbols, start, end
        )

        data = yf.download(
            tickers=symbols,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            group_by="ticker",
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            logger.warning("[YFINANCE] No data returned for %s", symbols)
            return pd.DataFrame()

        records = []
        if isinstance(data.columns, pd.MultiIndex):
            # Multi-index: columns = (ticker, OHLCV)
            for symbol in symbols:
                if symbol not in data.columns.levels[0]:
                    logger.warning("[YFINANCE] Symbol %s not found in response", symbol)
                    continue
                sym_data = data[symbol].dropna()
                for idx, row in sym_data.iterrows():
                    records.append(
                        {
                            "symbol": symbol,
                            "date": idx.date().isoformat(),
                            "open": row.get("Open"),
                            "high": row.get("High"),
                            "low": row.get("Low"),
                            "close": row.get("Close"),
                            "volume": row.get("Volume"),
                        }
                    )
        else:
            # Single symbol – flat columns
            symbol = symbols[0] if symbols else "UNKNOWN"
            for idx, row in data.iterrows():
                records.append(
                    {
                        "symbol": symbol,
                        "date": idx.date().isoformat(),
                        "open": row.get("Open"),
                        "high": row.get("High"),
                        "low": row.get("Low"),
                        "close": row.get("Close"),
                        "volume": row.get("Volume"),
                    }
                )

        df = pd.DataFrame(records)
        if not df.empty:
            df["change_pct"] = df.groupby("symbol")["close"].pct_change() * 100
            logger.info("[YFINANCE] Fetched %d rows for %s", len(df), symbols)

        return df
