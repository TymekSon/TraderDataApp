"""FOMC statements scraper."""

import logging
import re
from typing import List, Optional

import bs4
import requests

from scrapers.base import DEFAULT_USER_AGENT, retry

logger = logging.getLogger("FOMC")


class FOMCScraper:
    """Scrapes FOMC statements from the Federal Reserve website."""

    BASE_URL = "https://www.federalreserve.gov"
    CALENDAR_URL = f"{BASE_URL}/monetarypolicy/fomccalendars.htm"

    HEADERS = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_statements_list(self) -> List[dict]:
        """Return a list of dicts: {'date': ..., 'title': ..., 'url': ...}."""
        return self._fetch_statements_list()

    def fetch_statement(self, url: str) -> Optional[str]:
        """Return the full text content of a single FOMC statement."""
        return self._fetch_statement_text(url)

    def update_statements(
        self, existing_urls: set
    ) -> List[dict]:
        """Return only statements whose URLs are not in *existing_urls*."""
        all_statements = self.get_statements_list()
        return [s for s in all_statements if s.get("url") not in existing_urls]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry
    def _fetch_statements_list(self) -> List[dict]:
        """Parse the FOMC calendar page for statement links."""
        logger.info("Fetching FOMC calendar from %s", self.CALENDAR_URL)
        resp = requests.get(self.CALENDAR_URL, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        statements: List[dict] = []

        # Look for links that point to FOMC statement HTML pages.
        # Typical pattern: /monetarypolicy/fomcminutesYYYYMMDD.htm
        for link in soup.find_all("a", href=re.compile(r"fomcminutes\d{8}\.htm")):
            href = link.get("href", "")
            full_url = self.BASE_URL + href if href.startswith("/") else href
            title = link.get_text(strip=True) or "FOMC Statement"
            statements.append({"url": full_url, "title": title})

        return statements

    @retry
    def _fetch_statement_text(self, url: str) -> Optional[str]:
        """Fetch and extract the main text of a single statement page."""
        logger.info("Fetching FOMC statement from %s", url)
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        # Try multiple selectors in case the page structure changes.
        content_div = (
            soup.select_one("div.col-xs-12.col-sm-8.col-md-8")
            or soup.select_one("div.statement")
            or soup.select_one("div#content")
            or soup.select_one("article")
        )

        if content_div is None:
            logger.warning("Could not find content div in %s", url)
            return None

        return content_div.get_text("\n", strip=True)
