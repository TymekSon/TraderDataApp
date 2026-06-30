"""General helper utilities – date formatting, validation, etc."""

import logging
from datetime import date, datetime
from typing import Optional, Union

logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_date(value: Union[str, date, None]) -> Optional[date]:
    """Parse a date from string (YYYY-MM-DD) or return the date as‑is."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (ValueError, TypeError):
        logger.warning("Cannot parse date: %s", value)
        return None


def format_date(d: Optional[date]) -> str:
    """Return a date formatted as YYYY-MM-DD or empty string."""
    if d is None:
        return ""
    return d.strftime(DATE_FORMAT)


def format_datetime(dt: Optional[datetime]) -> str:
    """Return a datetime formatted as YYYY-MM-DD HH:MM:SS or empty string."""
    if dt is None:
        return ""
    return dt.strftime(DATETIME_FORMAT)


def safe_float(value: Optional[str]) -> Optional[float]:
    """Cast a string to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value.replace(",", "").replace("%", ""))
    except (ValueError, AttributeError):
        return None
