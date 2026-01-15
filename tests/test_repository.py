"""Tests for text repository."""

import tempfile
from pathlib import Path

import pytest

from lichtkrant.db.models import Text
from lichtkrant.db.repository import TextRepository


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
        text = Text(
            id=None,
            content="Hello World",
            color="WHITE",
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=True,
        )
        created = repository.create(text)

        assert created.id is not None
        assert created.id == 1
        assert created.content == "Hello World"
        assert created.active is True
        assert created.created_at is not None

    def test_get_text(self, repository: TextRepository) -> None:
        """Test retrieving a text by ID."""
        text = Text(
            id=None,
            content="Test",
            color="RED",
            background="NONE",
            font="KONGTEXT",
            speed=50,
            active=True,
        )
        created = repository.create(text)

        retrieved = repository.get(created.id)  # type: ignore[arg-type]
        assert retrieved is not None
        assert retrieved.content == "Test"
        assert retrieved.color == "RED"

    def test_get_nonexistent_returns_none(self, repository: TextRepository) -> None:
        """Test that getting a non-existent ID returns None."""
        assert repository.get(999) is None

    def test_get_all(self, repository: TextRepository) -> None:
        """Test getting all texts."""
        for i in range(3):
            text = Text(
                id=None,
                content=f"Text {i}",
                color="WHITE",
                background="NONE",
                font="KONGTEXT",
                speed=32,
                active=True,
            )
            repository.create(text)

        all_texts = repository.get_all()
        assert len(all_texts) == 3
        assert all_texts[0].content == "Text 0"
        assert all_texts[2].content == "Text 2"

    def test_get_active(self, repository: TextRepository) -> None:
        """Test getting only active texts."""
        for i, active in enumerate([True, False, True]):
            text = Text(
                id=None,
                content=f"Text {i}",
                color="WHITE",
                background="NONE",
                font="KONGTEXT",
                speed=32,
                active=active,
            )
            repository.create(text)

        active_texts = repository.get_active()
        assert len(active_texts) == 2
        assert all(t.active for t in active_texts)

    def test_update_text(self, repository: TextRepository) -> None:
        """Test updating a text."""
        text = Text(
            id=None,
            content="Original",
            color="WHITE",
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=True,
        )
        created = repository.create(text)

        created.content = "Updated"
        created.color = "RED"
        updated = repository.update(created)

        assert updated is not None
        assert updated.content == "Updated"
        assert updated.color == "RED"

    def test_delete_text(self, repository: TextRepository) -> None:
        """Test deleting a text."""
        text = Text(
            id=None,
            content="To Delete",
            color="WHITE",
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=True,
        )
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
        text = Text(
            id=None,
            content="Test",
            color="WHITE",
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=True,
        )
        created = repository.create(text)

        updated = repository.set_active(created.id, False)  # type: ignore[arg-type]
        assert updated is not None
        assert updated.active is False

        updated = repository.set_active(created.id, True)  # type: ignore[arg-type]
        assert updated is not None
        assert updated.active is True


class TestGetNextActive:
    """Tests for the get_next_active cycling logic."""

    def test_get_next_active_first(self, repository: TextRepository) -> None:
        """Test getting first active text when no current ID."""
        for i in range(3):
            text = Text(
                id=None,
                content=f"Text {i}",
                color="WHITE",
                background="NONE",
                font="KONGTEXT",
                speed=32,
                active=True,
            )
            repository.create(text)

        first = repository.get_next_active(None)
        assert first is not None
        assert first.id == 1

    def test_get_next_active_cycles(self, repository: TextRepository) -> None:
        """Test that get_next_active cycles through texts in order."""
        for i in range(3):
            text = Text(
                id=None,
                content=f"Text {i}",
                color="WHITE",
                background="NONE",
                font="KONGTEXT",
                speed=32,
                active=True,
            )
            repository.create(text)

        # Start from beginning
        t1 = repository.get_next_active(None)
        assert t1 is not None and t1.id == 1

        # Get next
        t2 = repository.get_next_active(1)
        assert t2 is not None and t2.id == 2

        # Get next
        t3 = repository.get_next_active(2)
        assert t3 is not None and t3.id == 3

        # Should wrap around to first
        t4 = repository.get_next_active(3)
        assert t4 is not None and t4.id == 1

    def test_get_next_active_skips_inactive(self, repository: TextRepository) -> None:
        """Test that get_next_active skips inactive texts."""
        for i, active in enumerate([True, False, True]):
            text = Text(
                id=None,
                content=f"Text {i}",
                color="WHITE",
                background="NONE",
                font="KONGTEXT",
                speed=32,
                active=active,
            )
            repository.create(text)

        # Should get id=1 (first active)
        t1 = repository.get_next_active(None)
        assert t1 is not None and t1.id == 1

        # Should skip id=2 (inactive) and get id=3
        t2 = repository.get_next_active(1)
        assert t2 is not None and t2.id == 3

        # Should wrap to id=1
        t3 = repository.get_next_active(3)
        assert t3 is not None and t3.id == 1

    def test_get_next_active_no_active_texts(
        self, repository: TextRepository
    ) -> None:
        """Test get_next_active returns None when no active texts."""
        text = Text(
            id=None,
            content="Inactive",
            color="WHITE",
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=False,
        )
        repository.create(text)

        assert repository.get_next_active(None) is None

    def test_get_next_active_empty_db(self, repository: TextRepository) -> None:
        """Test get_next_active returns None on empty database."""
        assert repository.get_next_active(None) is None
