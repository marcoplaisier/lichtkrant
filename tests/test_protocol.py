"""Tests for message protocol builder."""

import pytest

from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import HEADER_START, TERMINATOR, BackgroundColor


class TestMessageBuilder:
    """Tests for MessageBuilder class."""

    def test_basic_message(self) -> None:
        """Test building a basic message."""
        builder = MessageBuilder()
        builder.add_text("Hi", Color.WHITE)
        msg = builder.build()

        # Check header
        assert msg[0] == HEADER_START
        assert msg[1] == BackgroundColor.NONE
        assert msg[3] == Font.KONGTEXT

        # Check terminator
        assert msg[-2:] == TERMINATOR

    def test_text_encoding(self) -> None:
        """Test that text is properly encoded with colors."""
        builder = MessageBuilder()
        builder.add_text("AB", Color.RED)
        msg = builder.build()

        # After 6-byte header: 'A' (0x41), RED (0x20), 'B' (0x42), RED (0x20)
        assert msg[6] == ord("A")
        assert msg[7] == Color.RED
        assert msg[8] == ord("B")
        assert msg[9] == Color.RED

    def test_non_ascii_rejected(self) -> None:
        """Test that non-ASCII characters are rejected."""
        builder = MessageBuilder()
        with pytest.raises(ValueError, match="Non-ASCII"):
            builder.add_text("Hello\u00e9")

    def test_speed_validation(self) -> None:
        """Test speed parameter validation."""
        with pytest.raises(ValueError, match="Speed"):
            MessageBuilder(speed=0)

        with pytest.raises(ValueError, match="Speed"):
            MessageBuilder(speed=256)

    def test_pause_sequence(self) -> None:
        """Test pause control sequence."""
        builder = MessageBuilder()
        builder.add_pause(5)
        msg = builder.build()

        # After header: '#' (0x23), 0x01 (pause), 0x05 (seconds), 0x00
        assert msg[6] == ord("#")
        assert msg[7] == 0x01
        assert msg[8] == 5
        assert msg[9] == 0x00

    def test_chaining(self) -> None:
        """Test that builder methods can be chained."""
        msg = (
            MessageBuilder()
            .add_text("Hello", Color.GREEN)
            .add_pause(2)
            .add_text("World", Color.BLUE)
            .build()
        )
        assert isinstance(msg, bytes)
        assert len(msg) > 8  # Header + some content + terminator
