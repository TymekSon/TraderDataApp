"""Database initialisation script – creates all tables and indexes."""

import logging
from data.database import Database
from data.models import ALL_TABLES

logger = logging.getLogger(__name__)


def init_db(db_path: str) -> Database:
    """Create all tables and indexes, return a Database instance."""
    db = Database(db_path)
    db.connect()

    for create_sql, indexes in ALL_TABLES:
        db.execute(create_sql)
        for idx_sql in indexes:
            db.execute(idx_sql)

    logger.info("Database initialised: %s", db_path)
    return db
