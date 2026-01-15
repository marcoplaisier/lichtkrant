"""Database module for text storage."""

from lichtkrant.db.models import Text
from lichtkrant.db.repository import TextRepository

__all__ = ["Text", "TextRepository"]
