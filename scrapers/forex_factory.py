"""Forex Factory calendar scraper – integrated from spoulan's implementation.

Uses cloudscraper (Cloudflare bypass) + BeautifulSoup to parse the
dynamic Forex Factory calendar HTML week by week.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger("FOREX")

# ---------------------------------------------------------------------------
# Map Forex Factory event names → canonical names used in DB & charts.
# Order matters: first (pattern_lower, canonical_name) match wins.
# ---------------------------------------------------------------------------
EVENT_MAP: List[Tuple[str, str]] = [
    # ── CPI ────────────────────────────────────────────────────
    ("cpi y/y", "CPI y/y"),
    ("cpi (yoy)", "CPI y/y"),
    ("consumer price index (yoy)", "CPI y/y"),
    ("cpi m/m", "CPI m/m"),
    ("cpi (mom)", "CPI m/m"),
    ("consumer price index (mom)", "CPI m/m"),
    ("cpi core y/y", None),               # Core CPI – different metric
    ("cpi core m/m", None),
    ("core cpi", None),
    ("cpi ex food", None),
    ("cpi", None),                         # too ambiguous, skip
    # ── PPI ────────────────────────────────────────────────────
    ("ppi m/m", "PPI m/m"),
    ("ppi (mom)", "PPI m/m"),
    ("producer price index (mom)", "PPI m/m"),
    ("core ppi m/m", None),                # different metric
    ("ppi y/y", None),
    # ── Core PCE ───────────────────────────────────────────────
    ("core pce price index m/m", "Core PCE Price Index m/m"),
    ("core pce price index (mom)", "Core PCE Price Index m/m"),
    ("core pce (mom)", "Core PCE Price Index m/m"),
    ("pce price index m/m", "Core PCE Price Index m/m"),
    ("pce price index (mom)", "Core PCE Price Index m/m"),
    ("pce price index y/y", None),
    ("core pce y/y", None),
    # ── GDP ────────────────────────────────────────────────────
    ("gdp q/q", "GDP"),
    ("gdp (qoq)", "GDP"),
    ("gdp y/y", "GDP"),
    ("gdp m/m", "GDP"),
    ("gross domestic product", "GDP"),
    ("prelim gdp", "GDP"),
    ("final gdp", "GDP"),
    ("advance gdp", "GDP"),
    ("gdp annualized", "GDP"),
    ("gdp price index", None),             # sub‑event, skip
    ("gdp deflator", None),
    # ── Payrolls ───────────────────────────────────────────────
    ("non-farm employment change", "Non-Farm Employment Change"),
    ("nonfarm payrolls", "Non-Farm Employment Change"),
    ("nfp", "Non-Farm Employment Change"),
    ("change in nonfarm payrolls", "Non-Farm Employment Change"),
    ("adp non-farm", None),                # ADP report – different source
    ("adp employment", None),
    # ── Unemployment ───────────────────────────────────────────
    ("unemployment rate", "Unemployment Rate"),
    ("unemployment claims", None),         # weekly, different metric
    ("continuing jobless", None),
    ("initial jobless", None),
    # ── ISM ────────────────────────────────────────────────────
    ("ism manufacturing pmi", "ISM Manufacturing PMI"),
    ("ism manufacturing index", "ISM Manufacturing PMI"),
    ("ism services pmi", "ISM Services PMI"),
    ("ism services index", "ISM Services PMI"),
    ("ism non-manufacturing", "ISM Services PMI"),
    ("ism manufacturing employment", None), # sub‑index, skip
    ("ism manufacturing prices", None),
    # ── Retail Sales ───────────────────────────────────────────
    ("retail sales m/m", "Retail Sales"),
    ("retail sales (mom)", "Retail Sales"),
    ("retail sales y/y", "Retail Sales"),
    ("core retail sales m/m", "Retail Sales"),
    ("core retail sales (mom)", "Retail Sales"),
    ("advance retail sales", "Retail Sales"),
    ("retail sales ex autos", "Retail Sales"),
    ("retail sales", "Retail Sales"),       # catch‑all last
    # ── FOMC / Fed ─────────────────────────────────────────────
    ("fomc statement", "FOMC"),
    ("fomc minutes", "FOMC"),
    ("fomc press conference", "FOMC"),
    ("fomc meeting", "FOMC"),
    ("fomc decision", "FOMC"),
    ("federal funds rate", "FOMC"),
    ("fed interest rate decision", "FOMC"),
    ("federal reserve", "Federal Reserve"),
    ("jackson hole", "Jackson Hole"),
    # ── Other ──────────────────────────────────────────────────
    ("bank holiday", "Bank Holiday"),
]


class ForexFactoryScraper:
    """Scrapes economic calendar data from Forex Factory."""

    BASE_URL = "https://www.forexfactory.com/calendar"

    def __init__(self, events: Optional[List[str]] = None, currency: str = "USD"):
        self.events = events or []
        self.currency = currency
        self._scraper = cloudscraper.create_scraper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_calendar(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """Return a list of calendar event dicts for the given date range."""
        start = start_date or date.today()
        end = end_date or start + timedelta(days=7)
        return self._fetch_range(start, end)

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def _fetch_range(self, start: date, end: date) -> List[dict]:
        """Scrape all calendar weeks between *start* and *end*.
        
        Collects ALL USD events (no type filtering).  Each event gets
        an ``event_category`` via :func:`_normalize_event` (canonical
        name for chart grouping), while the raw FF name is stored in
        ``event_name``.
        """
        all_events: List[dict] = []
        seen: set = set()

        logger.info(
            "[FOREX] Range: %s → %s | currency=%s (all events)",
            start, end, self.currency,
        )

        urls = self._weekly_urls(start, end)
        for i, url in enumerate(urls):
            try:
                html = self._fetch(url)
            except Exception as exc:
                logger.warning("[FOREX] %s failed: %s", url, exc)
                continue

            year = self._year_from_url(url)
            week_events = self._parse_html(html, year, self.currency)
            for ev in week_events:
                ev["event_category"] = _normalize_event(ev["event_name"])
                key = (ev["date"], ev["time"], ev["currency"], ev["event_name"])
                if key not in seen:
                    seen.add(key)
                    all_events.append(ev)

            if (i + 1) % 10 == 0:
                logger.info(
                    "[FOREX] Progress: %d/%d weeks, %d events so far",
                    i + 1, len(urls), len(all_events),
                )

        logger.info("[FOREX] Done: %d weeks, %d unique events", len(urls), len(all_events))
        return all_events

    def _fetch(self, url: str) -> str:
        """Fetch a Forex Factory weekly calendar page via cloudscraper."""
        resp = self._scraper.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _weekly_urls(start: date, end: date) -> List[str]:
        """Generate Forex Factory weekly calendar URLs for the date range."""
        current = start - timedelta(days=start.weekday())
        urls = []
        while current <= end:
            week_str = current.strftime("%b%d.%Y").lower()
            urls.append(f"https://www.forexfactory.com/calendar?week={week_str}")
            current += timedelta(weeks=1)
        return urls

    @staticmethod
    def _year_from_url(url: str) -> int:
        """Extract the year from a weekly URL like ...?week=jun29.2026."""
        try:
            return int(url.split("week=")[-1].split(".")[-1])
        except (IndexError, ValueError):
            return date.today().year

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _impact_level(impact_class) -> str:
        classes = " ".join(impact_class)
        if "impact-yel" in classes:
            return "Non-economic"
        if "impact-gra" in classes:
            return "Low"
        if "impact-ora" in classes:
            return "Medium"
        if "impact-red" in classes:
            return "High"
        return "None"

    @staticmethod
    def _format_date(date_str: str, year: int) -> str:
        """Parse 'Thu Jul 3' → '2026-07-03'."""
        try:
            return datetime.strptime(date_str, "%a %b %d").replace(year=year).strftime("%Y-%m-%d")
        except ValueError:
            return date_str

    @staticmethod
    def _parse_html(html: str, year: int, currency: str) -> List[dict]:
        """Parse FF weekly calendar HTML – all *currency* events, no type filter."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"class": "calendar__table"})
        if not table:
            return []

        rows = table.find_all("tr", {"class": "calendar__row"})
        data: List[dict] = []
        last_time = ""

        for row in rows:
            date_cell = row.find_previous("tr", {"class": "calendar__row--day-breaker"})
            date_str = date_cell.text.strip() if date_cell else ""
            formatted_date = ForexFactoryScraper._format_date(date_str, year)

            time_cell = row.find("td", {"class": "calendar__time"})
            time_str = time_cell.text.strip() if time_cell else ""
            if time_str:
                last_time = time_str
            else:
                time_str = last_time

            curr_cell = row.find("td", {"class": "calendar__currency"})
            curr = curr_cell.text.strip() if curr_cell else ""

            event_cell = row.find("td", {"class": "calendar__event"})
            event = event_cell.text.strip() if event_cell else ""

            # ── Filter: currency only ──────────────────────────
            if currency and curr.upper() != currency.upper():
                continue

            impact_cell = row.find("td", {"class": "calendar__impact"})
            impact = "None"
            if impact_cell:
                span = impact_cell.find("span")
                if span and span.get("class"):
                    impact = ForexFactoryScraper._impact_level(span.get("class"))

            actual = row.find("td", {"class": "calendar__actual"})
            forecast = row.find("td", {"class": "calendar__forecast"})
            previous = row.find("td", {"class": "calendar__previous"})

            if formatted_date.strip() and time_str.strip() and curr.strip() and event.strip():
                data.append({
                    "date": formatted_date,
                    "time": time_str,
                    "currency": curr,
                    "event_name": event,
                    "importance": impact,
                    "actual": actual.text.strip() if actual else "",
                    "forecast": forecast.text.strip() if forecast else "",
                    "previous": previous.text.strip() if previous else "",
                    "unit": "",
                })

        return data


# ---------------------------------------------------------------------------
# Module‑level helper
# ---------------------------------------------------------------------------

def _normalize_event(ff_name: str) -> str:
    """Map a raw FF event name to its canonical form via EVENT_MAP."""
    lower = ff_name.lower()
    for pattern, canonical in EVENT_MAP:
        if pattern in lower:
            if canonical is None:
                return ff_name  # explicitly excluded
            return canonical
    return ff_name
