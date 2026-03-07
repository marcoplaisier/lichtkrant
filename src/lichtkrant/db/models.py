"""Data models for text storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TextSegment:
    """A segment of text with its own color, or a control sequence.

    type can be: "text", "pause", "fast_blink", "slow_blink", "flash"
    """

    text: str = ""
    color: str = "WHITE"
    type: str = "text"
    duration: int = 0  # seconds for pause; hold_seconds for flash
    times: int = 0  # repeat count for blink
    scroll_off: bool = False  # flash: scroll off vs instant off

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d: dict = {"type": self.type}
        match self.type:
            case "pause":
                d["duration"] = self.duration
            case "fast_blink" | "slow_blink":
                d["times"] = self.times
            case "flash":
                d["text"] = self.text
                d["color"] = self.color
                d["duration"] = self.duration
                d["scroll_off"] = self.scroll_off
            case _:  # "text"
                d["text"] = self.text
                d["color"] = self.color
        return d


@dataclass
class Text:
    """A text message to be displayed on the LED sign."""

    id: int | None
    segments: list[TextSegment]
    background: str
    font: str
    speed: int
    active: bool
    created_at: datetime | None = None

    @property
    def content(self) -> str:
        """Concatenate text from text and flash segments for display."""
        return "".join(
            seg.text for seg in self.segments if seg.type in ("text", "flash")
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "segments": [seg.to_dict() for seg in self.segments],
            "background": self.background,
            "font": self.font,
            "speed": self.speed,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
