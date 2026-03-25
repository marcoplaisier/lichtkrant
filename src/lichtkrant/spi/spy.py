"""Spy SPI driver that logs messages instead of sending to hardware."""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

from lichtkrant.protocol.decoder import decode, format_hex

if TYPE_CHECKING:
    from lichtkrant.config import Config

logger = logging.getLogger(__name__)


class SpySPIDriver:
    """Drop-in SPIDriver replacement that decodes and logs all messages."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.history: deque[bytes] = deque(maxlen=1000)
        self._message_count = 0

    def open(self) -> None:
        """No-op — no hardware to initialize."""
        logger.info("SpySPIDriver: ready (dry-run mode)")

    def close(self) -> None:
        """No-op."""

    def wait_for_request(self, timeout: float = 5.0) -> bool:
        """Always ready."""
        return True

    def send(self, data: bytes, timeout: float = 5.0) -> bool:
        """Record and log the message."""
        self._message_count += 1
        self.history.append(data)

        parts = decode(data)
        header = f"[SPI #{self._message_count}]"
        for line in parts:
            logger.info("%s %s", header, line)
        logger.info("%s Hex: %s", header, format_hex(data))
        logger.info("%s Length: %d bytes", header, len(data))
        return True

    def __enter__(self) -> SpySPIDriver:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
