"""Flask web application for Lichtkrant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, render_template, request

if TYPE_CHECKING:
    from lichtkrant.config import Config
    from lichtkrant.spi import SPIDriver

from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor


def create_app(config: Config, spi_driver: SPIDriver | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["LICHTKRANT_CONFIG"] = config
    app.config["SPI_DRIVER"] = spi_driver

    @app.route("/")
    def index() -> str:
        """Main page with message input form."""
        return render_template("index.html")

    @app.route("/send", methods=["POST"])
    def send_message() -> tuple[dict, int]:
        """Send a message to the display."""
        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400

        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}, 400

        # Parse options
        color_name = data.get("color", "WHITE").upper()
        bg_name = data.get("background", "NONE").upper()
        font_name = data.get("font", "KONGTEXT").upper()
        speed = data.get("speed", 32)

        try:
            color = Color[color_name]
        except KeyError:
            return {"error": f"Invalid color: {color_name}"}, 400

        try:
            background = BackgroundColor[bg_name]
        except KeyError:
            return {"error": f"Invalid background: {bg_name}"}, 400

        try:
            font = Font[font_name]
        except KeyError:
            return {"error": f"Invalid font: {font_name}"}, 400

        if not 1 <= speed <= 255:
            return {"error": "Speed must be between 1 and 255"}, 400

        # Build message
        try:
            builder = MessageBuilder(background=background, speed=speed, font=font)
            builder.add_text(text, color)
            message = builder.build()
        except ValueError as e:
            return {"error": str(e)}, 400

        # Send via SPI if driver available
        driver = app.config.get("SPI_DRIVER")
        if driver:
            if not driver.send(message):
                return {"error": "Display not ready (timeout waiting for REQUEST)"}, 503

        return {"success": True, "bytes_sent": len(message)}, 200

    @app.route("/colors")
    def get_colors() -> dict:
        """Return available colors."""
        return {
            "text_colors": [c.name for c in Color],
            "background_colors": [c.name for c in BackgroundColor],
        }

    @app.route("/fonts")
    def get_fonts() -> dict:
        """Return available fonts."""
        return {"fonts": [f.name for f in Font]}

    @app.route("/generate-hotspot-url")
    def generate_hotspot_url() -> dict:
        """Generate the captive portal URL for QR code."""
        host = config.web.host
        if host == "0.0.0.0":
            host = "192.168.4.1"  # Default AP gateway
        port = config.web.port
        url = f"http://{host}:{port}/"
        return {"url": url}

    return app
