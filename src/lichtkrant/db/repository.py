"""SQLite repository for text storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from lichtkrant.db.models import Text


class TextRepository:
    """Repository for CRUD operations on texts."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and table exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS texts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT 'WHITE',
                    background TEXT NOT NULL DEFAULT 'NONE',
                    font TEXT NOT NULL DEFAULT 'KONGTEXT',
                    speed INTEGER NOT NULL DEFAULT 32,
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_text(self, row: sqlite3.Row) -> Text:
        """Convert a database row to a Text object."""
        return Text(
            id=row["id"],
            content=row["content"],
            color=row["color"],
            background=row["background"],
            font=row["font"],
            speed=row["speed"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def create(self, text: Text) -> Text:
        """Create a new text entry."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO texts (content, color, background, font, speed, active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    text.content,
                    text.color,
                    text.background,
                    text.font,
                    text.speed,
                    text.active,
                ),
            )
            conn.commit()
            text.id = cursor.lastrowid
            # Fetch the created_at timestamp
            row = conn.execute(
                "SELECT * FROM texts WHERE id = ?", (text.id,)
            ).fetchone()
            return self._row_to_text(row)

    def get(self, text_id: int) -> Text | None:
        """Get a text by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM texts WHERE id = ?", (text_id,)
            ).fetchone()
            return self._row_to_text(row) if row else None

    def get_all(self) -> list[Text]:
        """Get all texts ordered by ID."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM texts ORDER BY id").fetchall()
            return [self._row_to_text(row) for row in rows]

    def get_active(self) -> list[Text]:
        """Get all active texts ordered by ID."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM texts WHERE active = 1 ORDER BY id"
            ).fetchall()
            return [self._row_to_text(row) for row in rows]

    def update(self, text: Text) -> Text | None:
        """Update an existing text."""
        if text.id is None:
            return None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE texts
                SET content = ?, color = ?, background = ?, font = ?, speed = ?,
                    active = ?
                WHERE id = ?
                """,
                (
                    text.content,
                    text.color,
                    text.background,
                    text.font,
                    text.speed,
                    text.active,
                    text.id,
                ),
            )
            conn.commit()
            return self.get(text.id)

    def delete(self, text_id: int) -> bool:
        """Delete a text by ID."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM texts WHERE id = ?", (text_id,))
            conn.commit()
            return cursor.rowcount > 0

    def set_active(self, text_id: int, active: bool) -> Text | None:
        """Set the active status of a text."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE texts SET active = ? WHERE id = ?", (active, text_id)
            )
            conn.commit()
            return self.get(text_id)

    def get_next_active(self, current_id: int | None = None) -> Text | None:
        """Get the next active text after current_id, wrapping to start."""
        with self._connect() as conn:
            if current_id is not None:
                # Try to get next active text with ID > current_id
                row = conn.execute(
                    """
                    SELECT * FROM texts
                    WHERE active = 1 AND id > ?
                    ORDER BY id
                    LIMIT 1
                    """,
                    (current_id,),
                ).fetchone()
                if row:
                    return self._row_to_text(row)

            # Wrap around: get the first active text
            row = conn.execute(
                """
                SELECT * FROM texts
                WHERE active = 1
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()
            return self._row_to_text(row) if row else None
