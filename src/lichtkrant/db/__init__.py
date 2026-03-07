"""Database module for text storage."""

from lichtkrant.db.models import Text, TextSegment
from lichtkrant.db.repository import TextRepository

__all__ = ["Text", "TextSegment", "TextRepository"]
