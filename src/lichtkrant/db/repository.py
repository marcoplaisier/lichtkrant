"""SQLite repository for text storage."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from lichtkrant.db.models import QueueEntry, Text, TextSegment


class TextRepository:
    """Repository for CRUD operations on texts and the display queue."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS texts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segments TEXT NOT NULL DEFAULT '[]',
                    background TEXT NOT NULL DEFAULT 'NONE',
                    font TEXT NOT NULL DEFAULT 'KONGTEXT',
                    speed INTEGER NOT NULL DEFAULT 32,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_id INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_position ON queue(position)"
            )
            conn.commit()
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Run all necessary migrations."""
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(texts)").fetchall()
        ]

        # Migration: old content+color schema -> segments
        if "content" in columns:
            if "segments" not in columns:
                conn.execute(
                    "ALTER TABLE texts ADD COLUMN segments TEXT NOT NULL DEFAULT '[]'"
                )
            rows = conn.execute("SELECT id, content, color FROM texts").fetchall()
            for row in rows:
                segments_json = json.dumps(
                    [{"text": row["content"], "color": row["color"]}]
                )
                conn.execute(
                    "UPDATE texts SET segments = ? WHERE id = ?",
                    (segments_json, row["id"]),
                )
            conn.commit()

        # Migration: drop active column (migrate active texts to queue)
        if "active" in columns:
            # Collect active text IDs before dropping the column
            active_rows = conn.execute(
                "SELECT id FROM texts WHERE active = 1 ORDER BY id"
            ).fetchall()
            active_ids = [
                (row["id"], (i + 1) * 10)
                for i, row in enumerate(active_rows)
            ]

            # Drop the active column by recreating the table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS texts_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segments TEXT NOT NULL DEFAULT '[]',
                    background TEXT NOT NULL DEFAULT 'NONE',
                    font TEXT NOT NULL DEFAULT 'KONGTEXT',
                    speed INTEGER NOT NULL DEFAULT 32,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO texts_new
                    (id, segments, background, font, speed, created_at)
                SELECT id, segments, background, font, speed, created_at
                FROM texts
            """)
            conn.execute("DROP TABLE texts")
            conn.execute("ALTER TABLE texts_new RENAME TO texts")

            # Now insert queue entries (after texts table is rebuilt)
            for text_id, position in active_ids:
                conn.execute(
                    "INSERT INTO queue (text_id, position) VALUES (?, ?)",
                    (text_id, position),
                )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _parse_segments(segments_json: str) -> list[TextSegment]:
        """Parse JSON segments string into TextSegment list."""
        raw = json.loads(segments_json)
        return [
            TextSegment(
                text=s.get("text", ""),
                color=s.get("color", "WHITE"),
                type=s.get("type", "text"),
                duration=s.get("duration", 0),
                times=s.get("times", 0),
                scroll_off=s.get("scroll_off", False),
            )
            for s in raw
        ]

    @staticmethod
    def _serialize_segments(segments: list[TextSegment]) -> str:
        """Serialize TextSegment list to JSON string."""
        return json.dumps([seg.to_dict() for seg in segments])

    def _row_to_text(self, row: sqlite3.Row) -> Text:
        """Convert a database row to a Text object."""
        return Text(
            id=row["id"],
            segments=self._parse_segments(row["segments"]),
            background=row["background"],
            font=row["font"],
            speed=row["speed"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # --- Text CRUD ---

    def create(self, text: Text) -> Text:
        """Create a new text entry."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO texts (segments, background, font, speed)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self._serialize_segments(text.segments),
                    text.background,
                    text.font,
                    text.speed,
                ),
            )
            conn.commit()
            text.id = cursor.lastrowid
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

    def update(self, text: Text) -> Text | None:
        """Update an existing text."""
        if text.id is None:
            return None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE texts
                SET segments = ?, background = ?, font = ?, speed = ?
                WHERE id = ?
                """,
                (
                    self._serialize_segments(text.segments),
                    text.background,
                    text.font,
                    text.speed,
                    text.id,
                ),
            )
            conn.commit()
            return self.get(text.id)

    def delete(self, text_id: int) -> bool:
        """Delete a text by ID. Queue entries are cascade-deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM texts WHERE id = ?", (text_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Queue CRUD ---

    def get_queue(self) -> list[tuple[QueueEntry, Text]]:
        """Get queue entries with their texts, ordered by position."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT q.id AS q_id, q.text_id, q.position,
                       t.id AS t_id, t.segments, t.background, t.font,
                       t.speed, t.created_at
                FROM queue q
                JOIN texts t ON q.text_id = t.id
                ORDER BY q.position
            """).fetchall()
            result = []
            for row in rows:
                entry = QueueEntry(
                    id=row["q_id"],
                    text_id=row["text_id"],
                    position=row["position"],
                )
                text = Text(
                    id=row["t_id"],
                    segments=self._parse_segments(row["segments"]),
                    background=row["background"],
                    font=row["font"],
                    speed=row["speed"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                result.append((entry, text))
            return result

    def add_to_queue(self, text_id: int) -> QueueEntry | None:
        """Add a text to the end of the queue."""
        with self._connect() as conn:
            # Verify text exists
            text_row = conn.execute(
                "SELECT id FROM texts WHERE id = ?", (text_id,)
            ).fetchone()
            if not text_row:
                return None

            # Get max position
            row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM queue"
            ).fetchone()
            new_position = row["max_pos"] + 10

            cursor = conn.execute(
                "INSERT INTO queue (text_id, position) VALUES (?, ?)",
                (text_id, new_position),
            )
            conn.commit()
            return QueueEntry(
                id=cursor.lastrowid,
                text_id=text_id,
                position=new_position,
            )

    def remove_from_queue(self, entry_id: int) -> bool:
        """Remove a queue entry by its ID."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM queue WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def reorder_queue(self, entries: list[dict]) -> bool:
        """Bulk update queue positions. entries: [{id, position}, ...]"""
        with self._connect() as conn:
            for entry in entries:
                conn.execute(
                    "UPDATE queue SET position = ? WHERE id = ?",
                    (entry["position"], entry["id"]),
                )
            conn.commit()
            return True

    def get_next_queue_entry(
        self, current_position: int | None = None
    ) -> tuple[QueueEntry, Text] | None:
        """Get the next queue entry after current_position, wrapping to start.

        Used by the dispatcher to cycle through the queue. When the end is
        reached, wraps back to the first entry.

        Args:
            current_position: Position of the last-displayed entry, or None
                to start from the beginning.

        Returns:
            Tuple of (QueueEntry, Text) for the next entry, or None if the
            queue is empty.
        """
        with self._connect() as conn:
            if current_position is not None:
                row = conn.execute(
                    """
                    SELECT q.id AS q_id, q.text_id, q.position,
                           t.id AS t_id, t.segments, t.background, t.font,
                           t.speed, t.created_at
                    FROM queue q
                    JOIN texts t ON q.text_id = t.id
                    WHERE q.position > ?
                    ORDER BY q.position
                    LIMIT 1
                    """,
                    (current_position,),
                ).fetchone()
                if row:
                    entry = QueueEntry(
                        id=row["q_id"],
                        text_id=row["text_id"],
                        position=row["position"],
                    )
                    text = Text(
                        id=row["t_id"],
                        segments=self._parse_segments(row["segments"]),
                        background=row["background"],
                        font=row["font"],
                        speed=row["speed"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                    return entry, text

            # Wrap to start
            row = conn.execute(
                """
                SELECT q.id AS q_id, q.text_id, q.position,
                       t.id AS t_id, t.segments, t.background, t.font,
                       t.speed, t.created_at
                FROM queue q
                JOIN texts t ON q.text_id = t.id
                ORDER BY q.position
                LIMIT 1
                """
            ).fetchone()
            if row:
                entry = QueueEntry(
                    id=row["q_id"],
                    text_id=row["text_id"],
                    position=row["position"],
                )
                text = Text(
                    id=row["t_id"],
                    segments=self._parse_segments(row["segments"]),
                    background=row["background"],
                    font=row["font"],
                    speed=row["speed"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                return entry, text
            return None
