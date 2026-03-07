"""Data models for text storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TextSegment:
    """A segment of text with its own color."""

    text: str
    color: str = "WHITE"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"text": self.text, "color": self.color}


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
        """Concatenate all segment texts for display."""
        return "".join(seg.text for seg in self.segments)

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
