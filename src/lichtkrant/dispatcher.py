"""Background dispatcher for sending texts to the LED display."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from lichtkrant.config import Config
    from lichtkrant.db import TextRepository
    from lichtkrant.db.models import Text
    from lichtkrant.spi import SPIDriver

from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor
from lichtkrant.templating import render as render_template


class TextDispatcher:
    """Background thread that monitors REQUEST line and sends texts."""

    def __init__(
        self,
        config: Config,
        repository: TextRepository,
        spi_driver: SPIDriver,
    ) -> None:
        self.config = config
        self.repository = repository
        self.spi_driver = spi_driver
        self._current_position: int | None = None
        self._current_text_id: int | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def _build_message(self, text: Text) -> bytes:
        """Build protocol message from a Text object."""
        builder = MessageBuilder(
            background=BackgroundColor[text.background],
            speed=text.speed,
            font=Font[text.font],
        )
        for segment in text.segments:
            match segment.type:
                case "pause":
                    builder.add_pause(segment.duration)
                case "fast_blink":
                    builder.add_fast_blink(segment.times)
                case "slow_blink":
                    builder.add_slow_blink(segment.times)
                case "flash":
                    builder.add_flash(
                        render_template(segment.text),
                        segment.duration,
                        Color[segment.color],
                        scroll_off=segment.scroll_off,
                    )
                case _:
                    builder.add_text(
                        render_template(segment.text),
                        Color[segment.color],
                    )
        return builder.build()

    def _dispatch_loop(self) -> None:
        """Main dispatch loop running in background thread."""
        logger.info("Dispatch loop started")
        empty_logged = False
        while self._running:
            result = self.repository.get_next_queue_entry(self._current_position)
            if result is None:
                if not empty_logged:
                    logger.info(
                        "Queue empty (after position=%s); idling",
                        self._current_position,
                    )
                    empty_logged = True
                time.sleep(1.0)
                continue
            empty_logged = False

            entry, text = result
            logger.info(
                "Next queue entry: position=%d text_id=%s",
                entry.position,
                text.id,
            )

            # Build the message
            try:
                message = self._build_message(text)
            except (KeyError, ValueError) as exc:
                logger.warning(
                    "Skipping text_id=%s at position=%d: invalid field (%s)",
                    text.id,
                    entry.position,
                    exc,
                )
                self._current_position = entry.position
                self._current_text_id = text.id
                continue

            logger.debug(
                "Built message for text_id=%s (%d bytes); "
                "waiting for REQUEST before sending",
                text.id,
                len(message),
            )

            # Wait for REQUEST and send
            if self.spi_driver.send(message):
                logger.info(
                    "Dispatched text_id=%s at position=%d",
                    text.id,
                    entry.position,
                )
                self._current_position = entry.position
                self._current_text_id = text.id
            else:
                logger.warning(
                    "SPI send failed for text_id=%s (REQUEST timeout); retrying",
                    text.id,
                )
                time.sleep(0.1)
        logger.info("Dispatch loop stopped")

    def start(self) -> None:
        """Start the dispatcher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the dispatcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def current_text_id(self) -> int | None:
        """Return the ID of the currently displayed text."""
        return self._current_text_id
