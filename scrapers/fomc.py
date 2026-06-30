"""FOMC statements scraper.

Scrapes:
  1. List of FOMC statement URLs from the Fed calendar page.
  2. Full statement text from individual statement pages.

Configuration (config.yaml):
  fomc:
    url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    statement_selector: "div.col-xs-12.col-sm-8.col-md-8"
    xPath: /html/body/div[7]/div[2]/div/div[3]
"""

import logging
import re
from datetime import datetime
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

    # Regex for FOMC statement press release links.
    # Pattern: /newsevents/pressreleases/monetaryYYYYMMDD[a-z].htm
    STATEMENT_RE = re.compile(r"/newsevents/pressreleases/monetary\d{8}[a-z]?\.htm")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_statements_list(self) -> List[dict]:
        """Return a list of dicts: {'date': ..., 'title': ..., 'url': ...}.

        Scrapes the FOMC calendar page for press release links.
        """
        return self._fetch_statements_list()

    def fetch_statement(self, url: str) -> Optional[str]:
        """Return the full text content of a single FOMC statement."""
        result = self.fetch_statement_with_date(url)
        return result["content"] if result else None

    def fetch_statement_with_date(self, url: str) -> Optional[dict]:
        """Return {'date': 'YYYY-MM-DD', 'content': '...', 'title': '...'}."""
        logger.info("[FOMC] Fetching statement from %s", url)
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()
        # Fix encoding – Fed site sometimes uses Windows‑1252 for special chars
        if resp.encoding and resp.encoding.upper() != "UTF-8":
            resp.encoding = resp.apparent_encoding or "utf-8"

        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        # ── Extract date ────────────────────────────────────────────
        date_str = self._extract_date(soup, url)

        # ── Extract title ───────────────────────────────────────────
        title_tag = soup.select_one("h3.title")
        title = title_tag.get_text(strip=True) if title_tag else "FOMC Statement"

        # ── Extract content ─────────────────────────────────────────
        content = self._extract_content(soup, url)
        if content is None:
            return None

        logger.info(
            "[FOMC] Successfully fetched statement from %s (date=%s)",
            url, date_str,
        )
        return {
            "date": date_str,
            "title": title,
            "content": content,
            "url": url,
        }

    def update_statements(self, existing_urls: set) -> List[dict]:
        """Return only statements whose URLs are not in *existing_urls*."""
        all_statements = self.get_statements_list()
        new_ones = [s for s in all_statements if s.get("url") not in existing_urls]
        if new_ones:
            logger.info("[FOMC] Found %d new statement(s) to fetch", len(new_ones))
        return new_ones

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry
    def _fetch_statements_list(self) -> List[dict]:
        """Parse the FOMC calendar page for press release links."""
        logger.info("[FOMC] Fetching calendar from %s", self.CALENDAR_URL)
        resp = requests.get(self.CALENDAR_URL, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        statements: List[dict] = []
        seen_urls: set = set()

        for link in soup.find_all("a", href=self.STATEMENT_RE):
            href = link.get("href", "")
            full_url = self.BASE_URL + href if href.startswith("/") else href

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract date from URL: monetaryYYYYMMDD…
            m = re.search(r"monetary(\d{4})(\d{2})(\d{2})", href)
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""

            title = link.get_text(strip=True) or "FOMC Statement"
            statements.append({"date": date_str, "title": title, "url": full_url})

        # Sort newest first
        statements.sort(key=lambda s: s["date"], reverse=True)
        logger.info("[FOMC] Found %d statement links on calendar page", len(statements))
        return statements

    def _extract_date(self, soup: bs4.BeautifulSoup, url: str) -> str:
        """Extract the publication date from the statement page."""
        time_tag = soup.select_one("p.article__time")
        if time_tag:
            raw = time_tag.get_text(strip=True)
            # e.g. "June 17, 2026"
            for fmt in ("%B %d, %Y", "%B %d %Y"):
                try:
                    return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # Fallback: extract from URL
        m = re.search(r"monetary(\d{4})(\d{2})(\d{2})", url)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        logger.warning("[FOMC] Could not extract date from %s", url)
        return ""

    def _extract_content(
        self, soup: bs4.BeautifulSoup, url: str
    ) -> Optional[str]:
        """Extract the statement text from the page.

        Strategy (ordered by priority):
          1. The content div identified via config selector
             (div.col-xs-12.col-sm-8.col-md-8) — but skip the .heading sibling.
          2. The #article div and look for the content column.
          3. Generic fallbacks.
        """
        # ── Try the content div (without .heading class) ────────────
        content_div = soup.select_one(
            "div.col-xs-12.col-sm-8.col-md-8:not(.heading)"
        )
        if content_div:
            text = content_div.get_text("\n", strip=True)
            if len(text) > 100:
                return text

        # ── Try all matching divs and pick the one with most text ───
        all_matches = soup.select("div.col-xs-12.col-sm-8.col-md-8")
        text_candidates = []
        for div in all_matches:
            # Skip the heading div
            if "heading" in div.get("class", []):
                continue
            txt = div.get_text("\n", strip=True)
            if len(txt) > 100:
                text_candidates.append(txt)

        if text_candidates:
            # Return the longest text block
            return max(text_candidates, key=len)

        # ── Fallbacks ───────────────────────────────────────────────
        for sel in ("div#article", "div.statement", "article", "div#content"):
            div = soup.select_one(sel)
            if div:
                txt = div.get_text("\n", strip=True)
                if len(txt) > 100:
                    return txt

        logger.warning("[FOMC] Could not find content div in %s", url)
        return None
