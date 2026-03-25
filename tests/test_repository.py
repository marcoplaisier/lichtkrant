"""Tests for text repository."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from lichtkrant.db.models import Text, TextSegment
from lichtkrant.db.repository import TextRepository


def _make_text(content="Hello World", color="WHITE", **kwargs):
    """Helper to create a Text with segments from simple content+color."""
    defaults = {
        "id": None,
        "segments": [TextSegment(text=content, color=color)],
        "background": "NONE",
        "font": "KONGTEXT",
        "speed": 32,
    }
    defaults.update(kwargs)
    return Text(**defaults)


@pytest.fixture
def repository() -> TextRepository:
    """Create a repository with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield TextRepository(db_path)


class TestTextRepository:
    """Tests for TextRepository class."""

    def test_create_text(self, repository: TextRepository) -> None:
        """Test creating a text entry."""
        text = _make_text("Hello World")
        created = repository.create(text)

        assert created.id is not None
        assert created.id == 1
        assert created.content == "Hello World"
        assert created.created_at is not None

    def test_get_text(self, repository: TextRepository) -> None:
        """Test retrieving a text by ID."""
        text = _make_text("Test", "RED", speed=50)
        created = repository.create(text)

        retrieved = repository.get(created.id)  # type: ignore[arg-type]
        assert retrieved is not None
        assert retrieved.content == "Test"
        assert retrieved.segments[0].color == "RED"

    def test_get_nonexistent_returns_none(self, repository: TextRepository) -> None:
        """Test that getting a non-existent ID returns None."""
        assert repository.get(999) is None

    def test_get_all(self, repository: TextRepository) -> None:
        """Test getting all texts."""
        for i in range(3):
            repository.create(_make_text(f"Text {i}"))

        all_texts = repository.get_all()
        assert len(all_texts) == 3
        assert all_texts[0].content == "Text 0"
        assert all_texts[2].content == "Text 2"

    def test_update_text(self, repository: TextRepository) -> None:
        """Test updating a text."""
        text = _make_text("Original")
        created = repository.create(text)

        created.segments = [TextSegment(text="Updated", color="RED")]
        updated = repository.update(created)

        assert updated is not None
        assert updated.content == "Updated"
        assert updated.segments[0].color == "RED"

    def test_delete_text(self, repository: TextRepository) -> None:
        """Test deleting a text."""
        text = _make_text("To Delete")
        created = repository.create(text)

        result = repository.delete(created.id)  # type: ignore[arg-type]
        assert result is True
        assert repository.get(created.id) is None  # type: ignore[arg-type]

    def test_delete_nonexistent_returns_false(
        self, repository: TextRepository
    ) -> None:
        """Test that deleting a non-existent ID returns False."""
        assert repository.delete(999) is False

    def test_create_multi_segment_text(self, repository: TextRepository) -> None:
        """Test creating a text with multiple color segments."""
        text = Text(
            id=None,
            segments=[
                TextSegment(text="Hello ", color="RED"),
                TextSegment(text="World", color="BLUE"),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        created = repository.create(text)

        assert created.content == "Hello World"
        assert len(created.segments) == 2
        assert created.segments[0].text == "Hello "
        assert created.segments[0].color == "RED"
        assert created.segments[1].text == "World"
        assert created.segments[1].color == "BLUE"

        # Verify round-trip through database
        retrieved = repository.get(created.id)  # type: ignore[arg-type]
        assert retrieved is not None
        assert len(retrieved.segments) == 2
        assert retrieved.segments[0].color == "RED"
        assert retrieved.segments[1].color == "BLUE"

    def test_migration_from_old_schema_with_active(self) -> None:
        """Test migration from old schema with active column to new schema + queue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "migrate.db"

            # Create old-schema database manually
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE texts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segments TEXT NOT NULL DEFAULT '[]',
                    background TEXT NOT NULL DEFAULT 'NONE',
                    font TEXT NOT NULL DEFAULT 'KONGTEXT',
                    speed INTEGER NOT NULL DEFAULT 32,
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO texts (segments, active) VALUES (?, ?)",
                (json.dumps([{"text": "Active text", "color": "WHITE"}]), True),
            )
            conn.execute(
                "INSERT INTO texts (segments, active) VALUES (?, ?)",
                (json.dumps([{"text": "Inactive text", "color": "RED"}]), False),
            )
            conn.execute(
                "INSERT INTO texts (segments, active) VALUES (?, ?)",
                (json.dumps([{"text": "Also active", "color": "GREEN"}]), True),
            )
            conn.commit()
            conn.close()

            # Open with new repository — should trigger migration
            repo = TextRepository(db_path)
            texts = repo.get_all()
            assert len(texts) == 3

            # Active column should be gone
            with repo._connect() as c:
                columns = [
                    row[1]
                    for row in c.execute("PRAGMA table_info(texts)").fetchall()
                ]
                assert "active" not in columns

            # Active texts should be in queue
            queue = repo.get_queue()
            assert len(queue) == 2
            queue_text_ids = [text.id for _, text in queue]
            assert 1 in queue_text_ids  # Active text
            assert 3 in queue_text_ids  # Also active
            assert 2 not in queue_text_ids  # Inactive text

    def test_migration_from_content_color_schema(self) -> None:
        """Test migration from old content+color schema to segments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "migrate.db"

            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE texts (
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
            conn.execute(
                "INSERT INTO texts (content, color) VALUES (?, ?)",
                ("Old text", "GREEN"),
            )
            conn.commit()
            conn.close()

            repo = TextRepository(db_path)
            texts = repo.get_all()
            assert len(texts) == 1
            assert texts[0].content == "Old text"
            assert len(texts[0].segments) == 1
            assert texts[0].segments[0].text == "Old text"
            assert texts[0].segments[0].color == "GREEN"

    def test_create_pause_segment(self, repository: TextRepository) -> None:
        """Test creating a text with a pause control segment."""
        text = Text(
            id=None,
            segments=[
                TextSegment(text="Hello", color="WHITE"),
                TextSegment(type="pause", duration=5),
                TextSegment(text="World", color="RED"),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        created = repository.create(text)
        retrieved = repository.get(created.id)

        assert retrieved is not None
        assert len(retrieved.segments) == 3
        assert retrieved.segments[1].type == "pause"
        assert retrieved.segments[1].duration == 5

    def test_create_mixed_segments(self, repository: TextRepository) -> None:
        """Test creating a text with all segment types."""
        text = Text(
            id=None,
            segments=[
                TextSegment(text="Intro", color="GREEN"),
                TextSegment(type="pause", duration=2),
                TextSegment(type="fast_blink", times=3),
                TextSegment(type="slow_blink", times=5),
                TextSegment(
                    type="flash", text="SALE!", color="RED",
                    duration=4, scroll_off=True,
                ),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        created = repository.create(text)
        retrieved = repository.get(created.id)

        assert retrieved is not None
        assert len(retrieved.segments) == 5
        assert retrieved.segments[0].type == "text"
        assert retrieved.segments[1].type == "pause"
        assert retrieved.segments[1].duration == 2
        assert retrieved.segments[2].type == "fast_blink"
        assert retrieved.segments[2].times == 3
        assert retrieved.segments[3].type == "slow_blink"
        assert retrieved.segments[3].times == 5
        assert retrieved.segments[4].type == "flash"
        assert retrieved.segments[4].text == "SALE!"
        assert retrieved.segments[4].duration == 4
        assert retrieved.segments[4].scroll_off is True

    def test_backward_compat_no_type_key(self, repository: TextRepository) -> None:
        """Test that old JSON without a type key is parsed as 'text'."""
        with repository._connect() as conn:
            segments_json = json.dumps([{"text": "Legacy", "color": "BLUE"}])
            conn.execute(
                "INSERT INTO texts (segments, background, font, speed)"
                " VALUES (?, ?, ?, ?)",
                (segments_json, "NONE", "KONGTEXT", 32),
            )
            conn.commit()

        texts = repository.get_all()
        assert len(texts) == 1
        assert texts[0].segments[0].type == "text"
        assert texts[0].segments[0].text == "Legacy"
        assert texts[0].segments[0].color == "BLUE"

    def test_content_property_skips_control_segments(self) -> None:
        """Test that Text.content only includes text and flash segments."""
        text = Text(
            id=None,
            segments=[
                TextSegment(text="Hello ", color="WHITE"),
                TextSegment(type="pause", duration=2),
                TextSegment(type="fast_blink", times=3),
                TextSegment(type="flash", text="SALE", color="RED", duration=1),
                TextSegment(text=" World", color="WHITE"),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        assert text.content == "Hello SALE World"


class TestQueue:
    """Tests for queue CRUD operations."""

    def test_add_to_queue(self, repository: TextRepository) -> None:
        """Test adding a text to the queue."""
        text = repository.create(_make_text("Hello"))
        entry = repository.add_to_queue(text.id)

        assert entry is not None
        assert entry.text_id == text.id
        assert entry.position == 10

    def test_add_to_queue_nonexistent_text(self, repository: TextRepository) -> None:
        """Test adding a nonexistent text to queue returns None."""
        assert repository.add_to_queue(999) is None

    def test_add_multiple_to_queue(self, repository: TextRepository) -> None:
        """Test adding multiple texts to queue appends at end."""
        t1 = repository.create(_make_text("First"))
        t2 = repository.create(_make_text("Second"))

        e1 = repository.add_to_queue(t1.id)
        e2 = repository.add_to_queue(t2.id)

        assert e1.position < e2.position

    def test_add_same_text_twice(self, repository: TextRepository) -> None:
        """Test that the same text can appear in queue multiple times."""
        text = repository.create(_make_text("Repeat"))
        e1 = repository.add_to_queue(text.id)
        e2 = repository.add_to_queue(text.id)

        assert e1.id != e2.id
        assert e1.text_id == e2.text_id
        assert e1.position < e2.position

    def test_get_queue(self, repository: TextRepository) -> None:
        """Test getting the full queue with text data."""
        t1 = repository.create(_make_text("First"))
        t2 = repository.create(_make_text("Second"))
        repository.add_to_queue(t1.id)
        repository.add_to_queue(t2.id)

        queue = repository.get_queue()
        assert len(queue) == 2
        entry1, text1 = queue[0]
        entry2, text2 = queue[1]
        assert text1.content == "First"
        assert text2.content == "Second"
        assert entry1.position < entry2.position

    def test_get_queue_empty(self, repository: TextRepository) -> None:
        """Test getting empty queue."""
        assert repository.get_queue() == []

    def test_remove_from_queue(self, repository: TextRepository) -> None:
        """Test removing a queue entry."""
        text = repository.create(_make_text("Hello"))
        entry = repository.add_to_queue(text.id)

        assert repository.remove_from_queue(entry.id) is True
        assert repository.get_queue() == []

    def test_remove_nonexistent_from_queue(self, repository: TextRepository) -> None:
        """Test removing a nonexistent queue entry."""
        assert repository.remove_from_queue(999) is False

    def test_reorder_queue(self, repository: TextRepository) -> None:
        """Test reordering queue entries."""
        t1 = repository.create(_make_text("First"))
        t2 = repository.create(_make_text("Second"))
        e1 = repository.add_to_queue(t1.id)
        e2 = repository.add_to_queue(t2.id)

        # Swap positions
        repository.reorder_queue([
            {"id": e1.id, "position": 20},
            {"id": e2.id, "position": 10},
        ])

        queue = repository.get_queue()
        assert len(queue) == 2
        assert queue[0][1].content == "Second"
        assert queue[1][1].content == "First"

    def test_delete_text_cascades_to_queue(self, repository: TextRepository) -> None:
        """Test that deleting a text removes its queue entries."""
        text = repository.create(_make_text("Will delete"))
        repository.add_to_queue(text.id)
        repository.add_to_queue(text.id)

        assert len(repository.get_queue()) == 2
        repository.delete(text.id)
        assert len(repository.get_queue()) == 0


class TestGetNextQueueEntry:
    """Tests for the get_next_queue_entry cycling logic."""

    def test_get_next_first(self, repository: TextRepository) -> None:
        """Test getting first queue entry when no current position."""
        t1 = repository.create(_make_text("First"))
        repository.add_to_queue(t1.id)

        result = repository.get_next_queue_entry(None)
        assert result is not None
        entry, text = result
        assert text.content == "First"

    def test_get_next_cycles(self, repository: TextRepository) -> None:
        """Test that get_next_queue_entry cycles through entries."""
        t1 = repository.create(_make_text("First"))
        t2 = repository.create(_make_text("Second"))
        t3 = repository.create(_make_text("Third"))
        repository.add_to_queue(t1.id)
        repository.add_to_queue(t2.id)
        repository.add_to_queue(t3.id)

        r1 = repository.get_next_queue_entry(None)
        assert r1 is not None
        assert r1[1].content == "First"

        r2 = repository.get_next_queue_entry(r1[0].position)
        assert r2 is not None
        assert r2[1].content == "Second"

        r3 = repository.get_next_queue_entry(r2[0].position)
        assert r3 is not None
        assert r3[1].content == "Third"

        # Wraps around
        r4 = repository.get_next_queue_entry(r3[0].position)
        assert r4 is not None
        assert r4[1].content == "First"

    def test_get_next_empty_queue(self, repository: TextRepository) -> None:
        """Test get_next_queue_entry returns None on empty queue."""
        assert repository.get_next_queue_entry(None) is None

    def test_get_next_single_entry(self, repository: TextRepository) -> None:
        """Test cycling with a single queue entry."""
        text = repository.create(_make_text("Only one"))
        repository.add_to_queue(text.id)

        r1 = repository.get_next_queue_entry(None)
        assert r1 is not None
        assert r1[1].content == "Only one"

        # Wraps to same entry
        r2 = repository.get_next_queue_entry(r1[0].position)
        assert r2 is not None
        assert r2[1].content == "Only one"
