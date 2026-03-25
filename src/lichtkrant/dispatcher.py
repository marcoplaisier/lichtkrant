"""Background dispatcher for sending texts to the LED display."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lichtkrant.config import Config
    from lichtkrant.db import TextRepository
    from lichtkrant.db.models import Text
    from lichtkrant.spi import SPIDriver

from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor


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
                        segment.text,
                        segment.duration,
                        Color[segment.color],
                        scroll_off=segment.scroll_off,
                    )
                case _:
                    builder.add_text(segment.text, Color[segment.color])
        return builder.build()

    def _dispatch_loop(self) -> None:
        """Main dispatch loop running in background thread."""
        while self._running:
            result = self.repository.get_next_queue_entry(self._current_position)
            if result is None:
                # No queue entries, wait and retry
                time.sleep(1.0)
                continue

            entry, text = result

            # Build the message
            try:
                message = self._build_message(text)
            except (KeyError, ValueError):
                # Invalid enum values, skip this entry
                self._current_position = entry.position
                self._current_text_id = text.id
                continue

            # Wait for REQUEST and send
            if self.spi_driver.send(message):
                self._current_position = entry.position
                self._current_text_id = text.id
            else:
                # Timeout waiting for REQUEST, retry after short delay
                time.sleep(0.1)

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
