"""Message builder for LED display protocol."""

from __future__ import annotations

from lichtkrant.protocol.constants import (
    CONTROL_CHAR,
    FLASH_END_MARKER,
    HEADER_START,
    TERMINATOR,
    BackgroundColor,
    Color,
    ControlCode,
    Font,
)


class MessageBuilder:
    """Build messages for the LED display protocol."""

    def __init__(
        self,
        background: BackgroundColor = BackgroundColor.NONE,
        speed: int = 0x20,
        font: Font = Font.KONGTEXT,
    ) -> None:
        if not 0x01 <= speed <= 0xFF:
            raise ValueError("Speed must be between 0x01 and 0xFF")

        self._background = background
        self._speed = speed
        self._font = font
        self._content: list[int] = []

    def add_text(self, text: str, color: Color = Color.WHITE) -> MessageBuilder:
        """Add colored text to the message."""
        for char in text:
            code = ord(char)
            if code > 0x7F:
                raise ValueError(f"Non-ASCII character not allowed: {char!r}")
            if char == "#":
                # Escape literal '#' using control sequence
                escape_seq = [
                    CONTROL_CHAR, ControlCode.LITERAL_HASH, CONTROL_CHAR, color
                ]
                self._content.extend(escape_seq)
            else:
                self._content.extend([code, color])
        return self

    def add_pause(self, seconds: int) -> MessageBuilder:
        """Add a pause in the scroll."""
        if not 0 < seconds <= 255:
            raise ValueError("Pause seconds must be between 1 and 255")
        self._content.extend([CONTROL_CHAR, ControlCode.PAUSE, seconds, 0x00])
        return self

    def add_fast_blink(self, times: int) -> MessageBuilder:
        """Add fast blink effect."""
        if not 0 < times <= 255:
            raise ValueError("Blink times must be between 1 and 255")
        self._content.extend([CONTROL_CHAR, ControlCode.FAST_BLINK, times, 0x00])
        return self

    def add_slow_blink(self, times: int) -> MessageBuilder:
        """Add slow blink effect."""
        if not 0 < times <= 255:
            raise ValueError("Blink times must be between 1 and 255")
        self._content.extend([CONTROL_CHAR, ControlCode.SLOW_BLINK, times, 0x00])
        return self

    def add_flash(
        self,
        text: str,
        hold_seconds: int,
        color: Color = Color.WHITE,
        scroll_off: bool = False,
    ) -> MessageBuilder:
        """Add flash text (instant on, hold, then off or scroll off)."""
        if not 0 < hold_seconds <= 255:
            raise ValueError("Hold seconds must be between 1 and 255")

        code = ControlCode.FLASH_SCROLL_OFF if scroll_off else ControlCode.FLASH_HOLD
        self._content.extend([CONTROL_CHAR, code, hold_seconds, 0x00])

        # Add flash content
        for char in text:
            char_code = ord(char)
            if char_code > 0x7F:
                raise ValueError(f"Non-ASCII character not allowed: {char!r}")
            self._content.extend([char_code, color])

        # End flash content
        self._content.extend(FLASH_END_MARKER)
        return self

    def build(self) -> bytes:
        """Build the complete message bytes."""
        header = bytes([
            HEADER_START,
            self._background,
            self._speed,
            self._font,
            0x00,
            0x00,
        ])
        return header + bytes(self._content) + TERMINATOR

    def clear(self) -> MessageBuilder:
        """Clear the message content."""
        self._content.clear()
        return self
