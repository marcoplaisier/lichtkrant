"""Structural interface shared by the hardware and spy SPI drivers."""

from __future__ import annotations

from typing import Protocol


class Driver(Protocol):
    """Anything that can be handed to the dispatcher as an SPI driver."""

    def open(self) -> None: ...

    def close(self) -> None: ...

    def wait_for_request(self, timeout: float = 5.0) -> bool: ...

    def send(self, data: bytes, timeout: float = 5.0) -> bool: ...
