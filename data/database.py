"""Database manager for SQLite operations."""

import sqlite3
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite database connection and operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Create and return a database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            logger.info("Connected to database: %s", self.db_path)
        return self.conn

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed.")

    def execute(
        self, query: str, params: Optional[Union[tuple, Dict[str, Any]]] = None
    ) -> sqlite3.Cursor:
        """Execute a single query with optional parameters."""
        conn = self.connect()
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
        """Insert or update a row using ON CONFLICT upsert logic.

        Args:
            table: Target table name.
            data: Column-value mapping.
            conflict_columns: Columns that define a unique conflict.
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{col}=excluded.{col}" for col in data if col not in conflict_columns)
        conflict_target = ", ".join(conflict_columns)

        query = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict_target}) DO UPDATE SET {updates}"
        )
        self.execute(query, tuple(data.values()))
