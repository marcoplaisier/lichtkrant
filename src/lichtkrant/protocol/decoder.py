"""Protocol decoder — turns raw message bytes back into human-readable form."""

from __future__ import annotations

from lichtkrant.protocol.constants import (
    CONTROL_CHAR,
    HEADER_START,
    BackgroundColor,
    Color,
    ControlCode,
    Font,
)

# Reverse lookups
_COLORS = {int(c): c.name for c in Color}
_BG_COLORS = {int(c): c.name for c in BackgroundColor}
_FONTS = {int(f): f.name for f in Font}


def decode(data: bytes) -> list[str]:
    """Decode a protocol message into human-readable lines.

    Returns a list of description strings, one per logical element.
    """
    if len(data) < 8:
        return [f"Too short ({len(data)} bytes)"]

    lines: list[str] = []
    buf = list(data)

    # Header (6 bytes)
    if buf[0] != HEADER_START:
        lines.append(f"Warning: unexpected header byte 0x{buf[0]:02X}")

    bg = _BG_COLORS.get(buf[1], f"0x{buf[1]:02X}")
    speed = buf[2]
    font = _FONTS.get(buf[3], f"0x{buf[3]:02X}")
    lines.append(f"Header: bg={bg} speed={speed} font={font}")

    # Content (after 6-byte header, before 2-byte terminator)
    content = buf[6:-2]
    i = 0
    while i < len(content):
        byte = content[i]

        if byte == CONTROL_CHAR and i + 3 < len(content):
            code = content[i + 1]

            if code == ControlCode.PAUSE:
                seconds = content[i + 2]
                lines.append(f"Pause {seconds}s")
                i += 4
            elif code == ControlCode.FAST_BLINK:
                times = content[i + 2]
                lines.append(f"Fast blink x{times}")
                i += 4
            elif code == ControlCode.SLOW_BLINK:
                times = content[i + 2]
                lines.append(f"Slow blink x{times}")
                i += 4
            elif code in (
                ControlCode.FLASH_HOLD,
                ControlCode.FLASH_SCROLL_OFF,
            ):
                hold = content[i + 2]
                scroll = code == ControlCode.FLASH_SCROLL_OFF
                mode = "scroll-off" if scroll else "hold"
                i += 4  # skip control sequence

                # Read flash text until 0xFD 0xFD
                flash_text = []
                flash_color = None
                while i + 1 < len(content):
                    if (
                        content[i] == 0xFD
                        and i + 1 < len(content)
                        and content[i + 1] == 0xFD
                    ):
                        i += 2
                        break
                    flash_text.append(chr(content[i]))
                    flash_color = _COLORS.get(
                        content[i + 1], f"0x{content[i + 1]:02X}"
                    )
                    i += 2
                text = "".join(flash_text)
                color_str = f" color={flash_color}" if flash_color else ""
                lines.append(
                    f'Flash "{text}"{color_str} {hold}s {mode}'
                )
            elif code == ControlCode.LITERAL_HASH:
                # Escaped '#': next two bytes are CONTROL_CHAR, color
                if i + 3 < len(content):
                    color = _COLORS.get(
                        content[i + 3], f"0x{content[i + 3]:02X}"
                    )
                    lines.append(f'Text "#" color={color}')
                    i += 4
                else:
                    i += 2
            else:
                lines.append(
                    f"Unknown control 0x{code:02X} at offset {i}"
                )
                i += 4
        else:
            # Regular text: collect consecutive char+color pairs
            text_chars = []
            current_color = None
            while i + 1 < len(content) and content[i] != CONTROL_CHAR:
                char = chr(content[i])
                color = _COLORS.get(
                    content[i + 1], f"0x{content[i + 1]:02X}"
                )
                if current_color is None:
                    current_color = color
                if color != current_color:
                    # Flush current run
                    text = "".join(text_chars)
                    lines.append(
                        f'Text "{text}" color={current_color}'
                    )
                    text_chars = []
                    current_color = color
                text_chars.append(char)
                i += 2

            if text_chars:
                text = "".join(text_chars)
                lines.append(f'Text "{text}" color={current_color}')

    # Terminator check
    if data[-2:] != b"\xaa\xaa":
        lines.append(
            f"Warning: unexpected terminator "
            f"0x{data[-2]:02X} 0x{data[-1]:02X}"
        )

    return lines


def format_hex(data: bytes) -> str:
    """Format bytes as a hex dump string."""
    return " ".join(f"{b:02x}" for b in data)
