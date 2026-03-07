"""Flask web application for Lichtkrant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, render_template, request

if TYPE_CHECKING:
    from lichtkrant.config import Config
    from lichtkrant.db import TextRepository
    from lichtkrant.spi import SPIDriver

from lichtkrant.db.models import Text
from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor


def create_app(
    config: Config,
    spi_driver: SPIDriver | None = None,
    repository: TextRepository | None = None,
) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["LICHTKRANT_CONFIG"] = config
    app.config["SPI_DRIVER"] = spi_driver
    app.config["REPOSITORY"] = repository

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

    # Text CRUD endpoints

    def _validate_text_data(data: dict) -> tuple[dict | None, int | None]:
        """Validate text data, return (error_dict, status_code) or (None, None)."""
        content = data.get("content", "")
        if not content:
            return {"error": "No content provided"}, 400

        color = data.get("color", "WHITE").upper()
        if color not in [c.name for c in Color]:
            return {"error": f"Invalid color: {color}"}, 400

        background = data.get("background", "NONE").upper()
        if background not in [c.name for c in BackgroundColor]:
            return {"error": f"Invalid background: {background}"}, 400

        font = data.get("font", "KONGTEXT").upper()
        if font not in [f.name for f in Font]:
            return {"error": f"Invalid font: {font}"}, 400

        speed = data.get("speed", 32)
        if not isinstance(speed, int) or not 1 <= speed <= 255:
            return {"error": "Speed must be between 1 and 255"}, 400

        return None, None

    @app.route("/texts", methods=["GET"])
    def list_texts() -> tuple[dict, int]:
        """List all texts."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503
        texts = repo.get_all()
        return {"texts": [t.to_dict() for t in texts]}, 200

    @app.route("/texts", methods=["POST"])
    def create_text() -> tuple[dict, int]:
        """Create a new text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400

        error, status = _validate_text_data(data)
        if error:
            return error, status  # type: ignore[return-value]

        text = Text(
            id=None,
            content=data["content"],
            color=data.get("color", "WHITE").upper(),
            background=data.get("background", "NONE").upper(),
            font=data.get("font", "KONGTEXT").upper(),
            speed=data.get("speed", 32),
            active=data.get("active", True),
        )
        created = repo.create(text)
        return {"text": created.to_dict()}, 201

    @app.route("/texts/<int:text_id>", methods=["GET"])
    def get_text(text_id: int) -> tuple[dict, int]:
        """Get a single text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        text = repo.get(text_id)
        if not text:
            return {"error": "Text not found"}, 404
        return {"text": text.to_dict()}, 200

    @app.route("/texts/<int:text_id>", methods=["PUT"])
    def update_text(text_id: int) -> tuple[dict, int]:
        """Update a text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        existing = repo.get(text_id)
        if not existing:
            return {"error": "Text not found"}, 404

        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400

        error, status = _validate_text_data(data)
        if error:
            return error, status  # type: ignore[return-value]

        text = Text(
            id=text_id,
            content=data["content"],
            color=data.get("color", "WHITE").upper(),
            background=data.get("background", "NONE").upper(),
            font=data.get("font", "KONGTEXT").upper(),
            speed=data.get("speed", 32),
            active=data.get("active", existing.active),
        )
        updated = repo.update(text)
        if not updated:
            return {"error": "Failed to update text"}, 500
        return {"text": updated.to_dict()}, 200

    @app.route("/texts/<int:text_id>", methods=["DELETE"])
    def delete_text(text_id: int) -> tuple[dict, int]:
        """Delete a text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        if not repo.delete(text_id):
            return {"error": "Text not found"}, 404
        return {"success": True}, 200

    @app.route("/texts/<int:text_id>/active", methods=["PATCH"])
    def toggle_text_active(text_id: int) -> tuple[dict, int]:
        """Toggle or set the active status of a text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        existing = repo.get(text_id)
        if not existing:
            return {"error": "Text not found"}, 404

        data = request.get_json() or {}
        # If 'active' provided, use it; otherwise toggle
        if "active" in data:
            new_active = bool(data["active"])
        else:
            new_active = not existing.active

        updated = repo.set_active(text_id, new_active)
        if not updated:
            return {"error": "Failed to update text"}, 500
        return {"text": updated.to_dict()}, 200

    return app
