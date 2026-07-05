"""Database initialisation script – creates all tables, indexes, and imports CSV."""

import logging
import os
import glob
from data.database import Database
from data.models import ALL_TABLES

logger = logging.getLogger("DB")


def init_db(db_path: str, csv_folder: str = None) -> Database:
    """Create all tables and indexes, return a Database instance.

    If *csv_folder* is provided, imports all CSV files from that folder
    (only USD events) — skips if data already present.
    """
    db = Database(db_path)

    # ── Detect old schema (no event_category column) → recreate ──
    try:
        db.fetch_one("SELECT event_category FROM forex_calendar LIMIT 1")
    except Exception:
        logger.info("[DB] Old schema detected — recreating forex_calendar table")
        db.execute("DROP TABLE IF EXISTS forex_calendar")

    for create_sql, indexes in ALL_TABLES:
        db.execute(create_sql)
        for idx_sql in indexes:
            db.execute(idx_sql)

    logger.info("Database initialised: %s", db_path)

    # ── Import CSV historical data if folder is given ────────────
    if csv_folder and os.path.isdir(csv_folder):
        cnt = db.fetch_one("SELECT COUNT(*) AS n FROM forex_calendar")
        if cnt and cnt["n"] > 100:
            logger.info("[DB] Already have %d events — skipping CSV import", cnt["n"])
        else:
            csv_files = sorted(glob.glob(os.path.join(csv_folder, "*.csv")))
            total = 0
            for f in csv_files:
                n = db.import_csv_bulk(f, currency="USD")
                total += n
                logger.info("[DB] CSV import: %s → %d rows", os.path.basename(f), n)
            logger.info("[DB] Total CSV import: %d rows", total)

    # ── Re‑normalize event categories (EVENT_MAP may have changed) ──
    try:
        from scrapers.forex_factory import _normalize_event
        rows = db.fetch_all("SELECT id, event_name, event_category FROM forex_calendar")
        updated = 0
        for r in rows:
            new_cat = _normalize_event(r["event_name"])
            if new_cat != r["event_category"]:
                db.execute(
                    "UPDATE forex_calendar SET event_category = ? WHERE id = ?",
                    (new_cat, r["id"]),
                )
                updated += 1
        if updated:
            logger.info("[DB] Re‑normalized %d event categories", updated)
    except Exception as exc:
        logger.warning("[DB] Re‑normalization skipped: %s", exc)

    return db
