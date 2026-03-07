"""Tests for text repository."""

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
        "active": True,
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
        assert created.active is True
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

    def test_get_active(self, repository: TextRepository) -> None:
        """Test getting only active texts."""
        for i, active in enumerate([True, False, True]):
            repository.create(_make_text(f"Text {i}", active=active))

        active_texts = repository.get_active()
        assert len(active_texts) == 2
        assert all(t.active for t in active_texts)

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

    def test_set_active(self, repository: TextRepository) -> None:
        """Test setting active status."""
        text = _make_text("Test")
        created = repository.create(text)

        updated = repository.set_active(created.id, False)  # type: ignore[arg-type]
        assert updated is not None
        assert updated.active is False

        updated = repository.set_active(created.id, True)  # type: ignore[arg-type]
        assert updated is not None
        assert updated.active is True

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
            active=True,
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

    def test_migration_from_old_schema(self) -> None:
        """Test migration from old content+color schema to segments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "migrate.db"

            # Create old-schema database manually
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

            # Open with new repository — should trigger migration
            repo = TextRepository(db_path)
            texts = repo.get_all()
            assert len(texts) == 1
            assert texts[0].content == "Old text"
            assert len(texts[0].segments) == 1
            assert texts[0].segments[0].text == "Old text"
            assert texts[0].segments[0].color == "GREEN"


class TestGetNextActive:
    """Tests for the get_next_active cycling logic."""

    def test_get_next_active_first(self, repository: TextRepository) -> None:
        """Test getting first active text when no current ID."""
        for i in range(3):
            repository.create(_make_text(f"Text {i}"))

        first = repository.get_next_active(None)
        assert first is not None
        assert first.id == 1

    def test_get_next_active_cycles(self, repository: TextRepository) -> None:
        """Test that get_next_active cycles through texts in order."""
        for i in range(3):
            repository.create(_make_text(f"Text {i}"))

        t1 = repository.get_next_active(None)
        assert t1 is not None and t1.id == 1

        t2 = repository.get_next_active(1)
        assert t2 is not None and t2.id == 2

        t3 = repository.get_next_active(2)
        assert t3 is not None and t3.id == 3

        t4 = repository.get_next_active(3)
        assert t4 is not None and t4.id == 1

    def test_get_next_active_skips_inactive(self, repository: TextRepository) -> None:
        """Test that get_next_active skips inactive texts."""
        for i, active in enumerate([True, False, True]):
            repository.create(_make_text(f"Text {i}", active=active))

        t1 = repository.get_next_active(None)
        assert t1 is not None and t1.id == 1

        t2 = repository.get_next_active(1)
        assert t2 is not None and t2.id == 3

        t3 = repository.get_next_active(3)
        assert t3 is not None and t3.id == 1

    def test_get_next_active_no_active_texts(
        self, repository: TextRepository
    ) -> None:
        """Test get_next_active returns None when no active texts."""
        repository.create(_make_text("Inactive", active=False))
        assert repository.get_next_active(None) is None

    def test_get_next_active_empty_db(self, repository: TextRepository) -> None:
        """Test get_next_active returns None on empty database."""
        assert repository.get_next_active(None) is None
