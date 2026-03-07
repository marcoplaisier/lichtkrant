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

    def test_none_color(self) -> None:
        """Test that NONE (0x00) color is available and encodes correctly."""
        assert Color.NONE == 0x00
        builder = MessageBuilder()
        builder.add_text("A", Color.NONE)
        msg = builder.build()
        assert msg[6] == ord("A")
        assert msg[7] == Color.NONE

    def test_multi_color_text(self) -> None:
        """Test building a message with multiple color segments."""
        builder = MessageBuilder()
        builder.add_text("Hi", Color.RED)
        builder.add_text("Lo", Color.BLUE)
        msg = builder.build()

        # 'H' RED 'i' RED 'L' BLUE 'o' BLUE
        assert msg[6] == ord("H")
        assert msg[7] == Color.RED
        assert msg[8] == ord("i")
        assert msg[9] == Color.RED
        assert msg[10] == ord("L")
        assert msg[11] == Color.BLUE
        assert msg[12] == ord("o")
        assert msg[13] == Color.BLUE

    def test_build_message_with_control_segments(self) -> None:
        """Test building a message with mixed text and control segments.

        Simulates what the dispatcher does: text + pause + blink + flash.
        """
        from lichtkrant.db.models import Text, TextSegment
        from lichtkrant.protocol.constants import BackgroundColor

        text = Text(
            id=1,
            segments=[
                TextSegment(text="Hi", color="WHITE"),
                TextSegment(type="pause", duration=3),
                TextSegment(type="fast_blink", times=2),
                TextSegment(
                    type="flash", text="GO", color="RED",
                    duration=5, scroll_off=True,
                ),
            ],
            background="NONE",
            font="KONGTEXT",
            speed=32,
            active=True,
        )

        # Build message the same way the dispatcher does
        builder = MessageBuilder(
            background=BackgroundColor[text.background],
            speed=text.speed,
            font=Font[text.font],
        )
        for seg in text.segments:
            match seg.type:
                case "pause":
                    builder.add_pause(seg.duration)
                case "fast_blink":
                    builder.add_fast_blink(seg.times)
                case "slow_blink":
                    builder.add_slow_blink(seg.times)
                case "flash":
                    builder.add_flash(
                        seg.text, seg.duration, Color[seg.color],
                        scroll_off=seg.scroll_off,
                    )
                case _:
                    builder.add_text(seg.text, Color[seg.color])

        msg = builder.build()

        # Verify header
        assert msg[0] == HEADER_START
        # Verify it built successfully and has content
        assert len(msg) > 8
        assert msg[-2:] == TERMINATOR

        # Verify text "Hi" is in the message (first segment)
        assert msg[6] == ord("H")
        assert msg[7] == Color.WHITE
