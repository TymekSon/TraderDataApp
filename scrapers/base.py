"""Shared utilities for scrapers (User‑Agent rotation, retries, etc.)."""

import logging
import time
from typing import Callable, Optional, TypeVar

import requests

logger = logging.getLogger("SCRAPER")

T = TypeVar("T")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_page(url: str, timeout: int = 30) -> str:
    """Fetch a page with standard headers and return its text content."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def retry(
    func: Callable[..., T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[..., T]:
    """Decorator that retries *func* with exponential backoff."""

    def wrapper(*args, **kwargs) -> T:
        last_exc = None
        wait = delay
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exc = e
                logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt,
                    max_retries,
                    func.__name__,
                    e,
                )
                if attempt < max_retries:
                    time.sleep(wait)
                    wait *= backoff
        raise last_exc  # type: ignore[misc]

    return wrapper
