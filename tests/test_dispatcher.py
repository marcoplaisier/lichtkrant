"""Tests for the text dispatcher."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from lichtkrant.config import Config
from lichtkrant.db.models import Text, TextSegment
from lichtkrant.db.repository import TextRepository
from lichtkrant.dispatcher import TextDispatcher
from lichtkrant.spi.spy import SpySPIDriver


def _make_repo():
    tmpdir = tempfile.mkdtemp()
    return TextRepository(Path(tmpdir) / "test.db")


def _make_text(content="Hello", color="WHITE"):
    return Text(
        id=None,
        segments=[TextSegment(text=content, color=color)],
        background="NONE",
        font="KONGTEXT",
        speed=32,
    )


class TestBuildMessage:
    """Test _build_message without running the dispatch loop."""

    def test_simple_text(self):
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)
        dispatcher = TextDispatcher(config, repo, spy)

        text = _make_text("Hi")
        msg = dispatcher._build_message(text)

        assert isinstance(msg, bytes)
        assert len(msg) > 8  # header + content + terminator
        assert msg[0] == 0xFE  # header start
        assert msg[-2:] == b"\xaa\xaa"  # terminator

    def test_multi_segment(self):
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)
        dispatcher = TextDispatcher(config, repo, spy)

        text = Text(
            id=None,
            segments=[
                TextSegment(text="Hello ", color="RED"),
                TextSegment(type="pause", duration=3),
                TextSegment(text="World", color="GREEN"),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        msg = dispatcher._build_message(text)
        assert isinstance(msg, bytes)
        assert len(msg) > 20

    def test_flash_segment(self):
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)
        dispatcher = TextDispatcher(config, repo, spy)

        text = Text(
            id=None,
            segments=[
                TextSegment(
                    type="flash", text="SALE", color="RED",
                    duration=2, scroll_off=True,
                ),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        msg = dispatcher._build_message(text)
        assert isinstance(msg, bytes)

    @patch("lichtkrant.dispatcher.render_template")
    def test_templates_are_rendered(self, mock_render):
        """Template variables in text segments are resolved."""
        mock_render.side_effect = lambda t: t.replace("{{date}}", "01 Jan 2026")

        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)
        dispatcher = TextDispatcher(config, repo, spy)

        text = _make_text("Today: {{date}}")
        dispatcher._build_message(text)
        mock_render.assert_called()


class TestDispatchLoop:
    """Test the dispatch loop with real repo and spy driver."""

    def test_dispatches_from_queue(self):
        """Dispatcher sends messages from the queue."""
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)

        # Create a text and add to queue
        created = repo.create(_make_text("Loop test"))
        repo.add_to_queue(created.id)

        dispatcher = TextDispatcher(config, repo, spy)
        dispatcher.start()

        # Wait for at least one message to be sent
        deadline = time.monotonic() + 2.0
        while len(spy.history) == 0 and time.monotonic() < deadline:
            time.sleep(0.05)

        dispatcher.stop()

        assert len(spy.history) >= 1
        assert dispatcher.current_text_id == created.id

    def test_empty_queue_does_not_crash(self):
        """Dispatcher handles empty queue gracefully."""
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)

        dispatcher = TextDispatcher(config, repo, spy)
        dispatcher.start()
        time.sleep(0.2)
        dispatcher.stop()

        assert len(spy.history) == 0

    def test_skips_invalid_text(self):
        """Dispatcher skips texts with invalid enum values."""
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)

        # Create text with invalid font
        bad = Text(
            id=None,
            segments=[TextSegment(text="Hi", color="WHITE")],
            background="NONE",
            font="NONEXISTENT",
            speed=32,
        )
        created_bad = repo.create(bad)
        repo.add_to_queue(created_bad.id)

        # Also add a valid text
        good = repo.create(_make_text("Valid"))
        repo.add_to_queue(good.id)

        dispatcher = TextDispatcher(config, repo, spy)
        dispatcher.start()

        deadline = time.monotonic() + 2.0
        while len(spy.history) == 0 and time.monotonic() < deadline:
            time.sleep(0.05)

        dispatcher.stop()

        # The valid text should have been sent
        assert len(spy.history) >= 1

    def test_start_stop_idempotent(self):
        """Starting/stopping multiple times doesn't crash."""
        config = Config()
        repo = _make_repo()
        spy = SpySPIDriver(config)

        dispatcher = TextDispatcher(config, repo, spy)
        dispatcher.start()
        dispatcher.start()  # double start
        dispatcher.stop()
        dispatcher.stop()  # double stop

    def test_send_failure_retries(self):
        """When SPI send fails, dispatcher retries."""
        config = Config()
        repo = _make_repo()

        # Create a mock driver that fails first, then always succeeds
        call_count = {"n": 0}
        mock_driver = MagicMock()

        def send_side_effect(*args, **kwargs):
            call_count["n"] += 1
            return call_count["n"] > 1

        mock_driver.send.side_effect = send_side_effect

        created = repo.create(_make_text("Retry"))
        repo.add_to_queue(created.id)

        dispatcher = TextDispatcher(config, repo, mock_driver)
        dispatcher.start()

        deadline = time.monotonic() + 2.0
        while mock_driver.send.call_count < 2 and time.monotonic() < deadline:
            time.sleep(0.05)

        dispatcher.stop()

        assert mock_driver.send.call_count >= 2
