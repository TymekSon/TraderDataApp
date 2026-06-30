"""Database manager for SQLite operations."""

import sqlite3
import logging
import threading
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("DB")


class Database:
    """Manages SQLite database connection and operations.

    Uses thread‑local connections so that each Flask/Dash worker thread
    gets its own connection (SQLite connections are not thread‑safe).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    # ------------------------------------------------------------------
    # Connection management (thread‑local)
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return the connection for the current thread (create if needed)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
            logger.info(
                "DB connection opened for thread %s", threading.current_thread().name
            )
        return self._local.conn

    def close(self) -> None:
        """Close the connection for the current thread."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
            logger.info("DB connection closed.")

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(
        self, query: str, params: Optional[Union[tuple, Dict[str, Any]]] = None
    ) -> sqlite3.Cursor:
        """Execute a single query with optional parameters."""
        conn = self._get_conn()
        cursor = conn.execute(query, params or ())
        conn.commit()
        return cursor

    def fetch_all(
        self, query: str, params: Optional[Union[tuple, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return all rows as dicts."""
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def fetch_one(
        self, query: str, params: Optional[Union[tuple, Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return the first row as a dict."""
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a row into the table and return the last row id."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = self.execute(query, tuple(data.values()))
        return cursor.lastrowid

    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
    ) -> None:
        """Insert or update a row using ON CONFLICT upsert logic."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(
            f"{col}=excluded.{col}" for col in data if col not in conflict_columns
        )
        conflict_target = ", ".join(conflict_columns)

        query = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict_target}) DO UPDATE SET {updates}"
        )
        self.execute(query, tuple(data.values()))
