"""Tests for protocol decoder."""

from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor
from lichtkrant.protocol.decoder import decode, format_hex


class TestDecode:
    """Tests for the decode function."""

    def test_simple_text(self) -> None:
        """Decode a simple text message."""
        msg = MessageBuilder(speed=32).add_text("Hi", Color.WHITE).build()
        lines = decode(msg)

        assert lines[0] == "Header: bg=NONE speed=32 font=KONGTEXT"
        assert 'Text "Hi" color=WHITE' in lines[1]

    def test_colored_text(self) -> None:
        """Decode text with a specific color."""
        msg = MessageBuilder().add_text("Hello", Color.RED).build()
        lines = decode(msg)

        assert any('Text "Hello" color=RED' in line for line in lines)

    def test_multi_color_text(self) -> None:
        """Decode text with multiple colors produces separate segments."""
        msg = (
            MessageBuilder()
            .add_text("AB", Color.RED)
            .add_text("CD", Color.BLUE)
            .build()
        )
        lines = decode(msg)

        assert any('"AB" color=RED' in line for line in lines)
        assert any('"CD" color=BLUE' in line for line in lines)

    def test_pause(self) -> None:
        """Decode a pause control sequence."""
        msg = (
            MessageBuilder()
            .add_text("A", Color.WHITE)
            .add_pause(5)
            .add_text("B", Color.WHITE)
            .build()
        )
        lines = decode(msg)

        assert any("Pause 5s" in line for line in lines)

    def test_fast_blink(self) -> None:
        msg = MessageBuilder().add_fast_blink(3).build()
        lines = decode(msg)
        assert any("Fast blink x3" in line for line in lines)

    def test_slow_blink(self) -> None:
        msg = MessageBuilder().add_slow_blink(2).build()
        lines = decode(msg)
        assert any("Slow blink x2" in line for line in lines)

    def test_flash_hold(self) -> None:
        msg = (
            MessageBuilder()
            .add_flash("GO", hold_seconds=4, color=Color.RED)
            .build()
        )
        lines = decode(msg)
        assert any(
            '"GO"' in line and "RED" in line and "4s" in line and "hold" in line
            for line in lines
        )

    def test_flash_scroll_off(self) -> None:
        msg = (
            MessageBuilder()
            .add_flash("X", hold_seconds=2, color=Color.GREEN, scroll_off=True)
            .build()
        )
        lines = decode(msg)
        assert any("scroll-off" in line for line in lines)

    def test_background_and_font(self) -> None:
        msg = MessageBuilder(
            background=BackgroundColor.RED,
            speed=100,
            font=Font.MUNRO_SMALL,
        ).add_text("X", Color.WHITE).build()
        lines = decode(msg)

        assert "bg=RED" in lines[0]
        assert "speed=100" in lines[0]
        assert "font=MUNRO_SMALL" in lines[0]

    def test_complex_message(self) -> None:
        """Decode a message with mixed segments."""
        msg = (
            MessageBuilder(
                background=BackgroundColor.BLUE, speed=50, font=Font.KONGTEXT
            )
            .add_text("Hello ", Color.WHITE)
            .add_pause(3)
            .add_fast_blink(2)
            .add_text("World", Color.GREEN)
            .add_flash("SALE", hold_seconds=5, color=Color.RED, scroll_off=True)
            .build()
        )
        lines = decode(msg)

        assert "bg=BLUE" in lines[0]
        assert any('"Hello " color=WHITE' in line for line in lines)
        assert any("Pause 3s" in line for line in lines)
        assert any("Fast blink x2" in line for line in lines)
        assert any('"World" color=GREEN' in line for line in lines)
        assert any('"SALE"' in line and "scroll-off" in line for line in lines)

    def test_too_short(self) -> None:
        lines = decode(b"\xfe\x00")
        assert "Too short" in lines[0]

    def test_roundtrip_all_segment_types(self) -> None:
        """Build a message with every segment type and verify decode."""
        msg = (
            MessageBuilder()
            .add_text("A", Color.CYAN)
            .add_pause(1)
            .add_fast_blink(4)
            .add_slow_blink(6)
            .add_flash("Z", hold_seconds=2, color=Color.MAGENTA)
            .add_text("B", Color.YELLOW)
            .build()
        )
        lines = decode(msg)

        # All should decode without errors
        assert not any("Unknown" in line for line in lines)
        assert not any("Warning" in line for line in lines)


class TestFormatHex:
    def test_format_hex(self) -> None:
        assert format_hex(b"\xfe\x00\x20") == "fe 00 20"

    def test_empty(self) -> None:
        assert format_hex(b"") == ""
