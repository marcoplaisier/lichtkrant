"""SPI driver for communication with PIC controller."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lichtkrant.config import Config

try:
    import RPi.GPIO as GPIO
    import spidev

    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class SPIDriver:
    """SPI communication driver with REQUEST line handshake."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._spi: spidev.SpiDev | None = None
        self._initialized = False

    def open(self) -> None:
        """Initialize SPI and GPIO."""
        if not HAS_HARDWARE:
            msg = "SPI hardware not available (spidev/RPi.GPIO not installed)"
            raise RuntimeError(msg)

        # Parse device path (e.g., "/dev/spidev0.0" -> bus=0, device=0)
        device_path = self.config.spi.device
        parts = device_path.replace("/dev/spidev", "").split(".")
        bus, device = int(parts[0]), int(parts[1])

        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.max_speed_hz = self.config.spi.speed_hz
        self._spi.mode = self.config.spi.mode

        # Set up REQUEST GPIO pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.config.gpio.request_pin, GPIO.IN)

        self._initialized = True

    def close(self) -> None:
        """Clean up SPI and GPIO."""
        if self._spi:
            self._spi.close()
            self._spi = None
        if HAS_HARDWARE and self._initialized:
            GPIO.cleanup(self.config.gpio.request_pin)
        self._initialized = False

    def wait_for_request(self, timeout: float = 5.0) -> bool:
        """Wait for PIC to signal ready via REQUEST line."""
        if not HAS_HARDWARE:
            return True

        active_level = GPIO.HIGH if self.config.gpio.request_active_high else GPIO.LOW
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            if GPIO.input(self.config.gpio.request_pin) == active_level:
                return True
            time.sleep(0.001)

        return False

    def send(self, data: bytes, timeout: float = 5.0) -> bool:
        """Send data to PIC after waiting for REQUEST signal."""
        if not self._initialized or not self._spi:
            raise RuntimeError("SPI not initialized. Call open() first.")

        if not self.wait_for_request(timeout):
            return False

        self._spi.xfer2(list(data))
        return True

    def __enter__(self) -> SPIDriver:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
