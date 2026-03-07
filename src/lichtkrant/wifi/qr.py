"""QR code generation for WiFi connection."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lichtkrant.config import Config

import qrcode
from qrcode.image.pure import PyPNGImage


def generate_wifi_qr(config: Config) -> bytes:
    """Generate a QR code for WiFi connection."""
    ssid = config.wifi.ssid
    password = config.wifi.password

    # WiFi QR code format
    wifi_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    img = qr.make_image(image_factory=PyPNGImage)

    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue()


def generate_url_qr(url: str) -> bytes:
    """Generate a QR code for a URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(image_factory=PyPNGImage)

    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue()
