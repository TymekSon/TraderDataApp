"""Forex Factory calendar scraper."""

import logging
from datetime import date, timedelta
from typing import List, Optional

from scrapers.base import fetch_page, retry

logger = logging.getLogger("FOREX")


class ForexFactoryScraper:
    """Scrapes economic calendar data from Forex Factory."""

    BASE_URL = "https://www.forexfactory.com/calendar"

    def __init__(self, events: Optional[List[str]] = None):
        self.events = events or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_calendar(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """Return a list of calendar event dicts for the given date range.

        Each dict contains:
            date, time, currency, event_name, importance,
            actual, forecast, previous, unit
        """
        start = start_date or date.today()
        end = end_date or start + timedelta(days=7)

        raw = self._fetch_raw(start, end)
        events = self._parse(raw)
        return self._filter_events(events)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry
    def _fetch_raw(self, start: date, end: date) -> str:
        """Fetch the raw HTML of the calendar page."""
        url = f"{self.BASE_URL}?day={start.isoformat()}"
        logger.info("Fetching Forex Factory calendar from %s", url)
        return fetch_page(url)

    def _parse(self, html: str) -> List[dict]:
        """Parse HTML into a list of event dicts.

        NOTE: Forex Factory uses a heavily dynamic / JavaScript‑rendered
        table.  The implementation below is a **skeleton** that shows the
        intended data shape.  In production you would use Selenium or
        reverse‑engineer the XHR API call.

        Returns a list of dicts with keys:
            date, time, currency, event_name, importance,
            actual, forecast, previous, unit
        """
        # Placeholder – real parsing would use BeautifulSoup + Selenium.
        # For now we return an empty list so the app can start.
        logger.warning(
            "ForexFactoryScraper._parse() is not fully implemented. "
            "A real Selenium/BeautifulSoup parser is required."
        )
        return []

    def _filter_events(self, events: List[dict]) -> List[dict]:
        """Keep only events whose names appear in self.events."""
        if not self.events:
            return events
        return [e for e in events if e.get("event_name") in self.events]
