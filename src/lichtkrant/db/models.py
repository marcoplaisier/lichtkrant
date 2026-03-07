"""Data models for text storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Text:
    """A text message to be displayed on the LED sign."""

    id: int | None
    content: str
    color: str
    background: str
    font: str
    speed: int
    active: bool
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "color": self.color,
            "background": self.background,
            "font": self.font,
            "speed": self.speed,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
