"""Protocol constants for LED display communication."""

from enum import IntEnum


class Color(IntEnum):
    """Color codes for text and background."""

    # Text colors
    GREEN = 0x10
    RED = 0x20
    BLUE = 0x30
    YELLOW = 0x40
    CYAN = 0x50
    MAGENTA = 0x60
    WHITE = 0x70


class BackgroundColor(IntEnum):
    """Background color codes."""

    NONE = 0x00
    GREEN = 0x84
    RED = 0x88
    BLUE = 0x8C
    YELLOW = 0x90
    CYAN = 0x94
    MAGENTA = 0x98
    WHITE = 0x9C


class Font(IntEnum):
    """Available fonts."""

    KONGTEXT = 0x01
    CUSTOM = 0x02
    MUNRO_SMALL = 0x03


class ControlCode(IntEnum):
    """Control sequence codes."""

    PAUSE = 0x01
    FAST_BLINK = 0x02
    SLOW_BLINK = 0x03
    FLASH_SCROLL_OFF = 0x04
    FLASH_HOLD = 0x05
    LITERAL_HASH = 0x06


# Protocol markers
HEADER_START = 0xFE
TERMINATOR = bytes([0xAA, 0xAA])
FLASH_END_MARKER = bytes([0xFD, 0xFD])
CONTROL_CHAR = ord("#")
