"""Flask web application for Lichtkrant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, redirect, render_template, request

if TYPE_CHECKING:
    from lichtkrant.config import Config
    from lichtkrant.db import TextRepository
    from lichtkrant.spi import SPIDriver

from lichtkrant.db.models import Text, TextSegment
from lichtkrant.protocol import Color, Font, MessageBuilder
from lichtkrant.protocol.constants import BackgroundColor


def create_app(
    config: Config,
    spi_driver: SPIDriver | None = None,
    repository: TextRepository | None = None,
    portal_ip: str | None = None,
) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["LICHTKRANT_CONFIG"] = config
    app.config["SPI_DRIVER"] = spi_driver
    app.config["REPOSITORY"] = repository

    valid_color_names = {c.name for c in Color}

    if portal_ip:
        portal_base = f"http://{portal_ip}:{config.web.port}"

        @app.before_request
        def captive_portal_redirect():
            host = request.host.split(":")[0]
            if host not in ("localhost", "127.0.0.1", portal_ip):
                return redirect(f"{portal_base}/welcome", code=302)

    # --- Page routes ---

    @app.route("/welcome")
    def welcome() -> str:
        """Captive portal landing page — minimal, prompts user to open browser."""
        return render_template("welcome.html")

    @app.route("/")
    def dashboard() -> str:
        """Dashboard page with queue status and direct send."""
        return render_template("dashboard.html")

    @app.route("/texts/")
    def texts_page() -> str:
        """Text management page."""
        return render_template("texts.html")

    @app.route("/queue/")
    def queue_page() -> str:
        """Queue management page."""
        return render_template("queue.html")

    # --- Direct send ---

    @app.route("/api/send", methods=["POST"])
    def send_message() -> tuple[dict, int]:
        """Send a message to the display."""
        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400

        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}, 400

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

        try:
            builder = MessageBuilder(background=background, speed=speed, font=font)
            builder.add_text(text, color)
            message = builder.build()
        except ValueError as e:
            return {"error": str(e)}, 400

        driver = app.config.get("SPI_DRIVER")
        if driver:
            if not driver.send(message):
                return {"error": "Display not ready (timeout waiting for REQUEST)"}, 503

        return {"success": True, "bytes_sent": len(message)}, 200

    # Legacy redirect for old /send endpoint
    @app.route("/send", methods=["POST"])
    def send_message_legacy() -> tuple[dict, int]:
        """Legacy redirect for direct send."""
        return send_message()

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
            host = "192.168.4.1"
        port = config.web.port
        url = f"http://{host}:{port}/"
        return {"url": url}

    # --- Text CRUD API ---

    def _extract_segments(data: dict) -> list[TextSegment]:
        """Extract segments from request data, supporting both formats."""
        if "segments" in data:
            segments = []
            for seg in data["segments"]:
                seg_type = seg.get("type", "text")
                if seg_type == "text":
                    text = seg.get("text", "")
                    if not text:
                        continue
                    color = seg.get("color", "WHITE").upper()
                    segments.append(TextSegment(text=text, color=color))
                elif seg_type == "pause":
                    segments.append(TextSegment(
                        type="pause",
                        duration=int(seg.get("duration", 1)),
                    ))
                elif seg_type in ("fast_blink", "slow_blink"):
                    segments.append(TextSegment(
                        type=seg_type,
                        times=int(seg.get("times", 1)),
                    ))
                elif seg_type == "flash":
                    text = seg.get("text", "")
                    if not text:
                        continue
                    segments.append(TextSegment(
                        type="flash",
                        text=text,
                        color=seg.get("color", "WHITE").upper(),
                        duration=int(seg.get("duration", 1)),
                        scroll_off=bool(seg.get("scroll_off", False)),
                    ))
            return segments
        # Legacy format: single content + color
        content = data.get("content", "")
        color = data.get("color", "WHITE").upper()
        if content:
            return [TextSegment(text=content, color=color)]
        return []

    def _validate_text_data(data: dict) -> tuple[dict | None, int | None]:
        """Validate text data, return (error_dict, status_code) or (None, None)."""
        segments = _extract_segments(data)
        if not segments:
            return {"error": "No content provided"}, 400

        for seg in segments:
            if seg.type in ("text", "flash") and seg.color not in valid_color_names:
                return {"error": f"Invalid color: {seg.color}"}, 400
            if seg.type == "pause" and not 1 <= seg.duration <= 255:
                return {"error": "Pause duration must be between 1 and 255"}, 400
            if seg.type in ("fast_blink", "slow_blink") and not 1 <= seg.times <= 255:
                return {"error": "Blink times must be between 1 and 255"}, 400
            if seg.type == "flash" and not 1 <= seg.duration <= 255:
                return {"error": "Flash duration must be between 1 and 255"}, 400

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

    @app.route("/api/texts", methods=["GET"])
    def api_list_texts() -> tuple[dict, int]:
        """List all texts."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503
        texts = repo.get_all()
        return {"texts": [t.to_dict() for t in texts]}, 200

    # Legacy endpoint
    @app.route("/texts", methods=["GET"])
    def list_texts() -> tuple[dict, int]:
        """Legacy: list all texts (JSON)."""
        return api_list_texts()

    @app.route("/api/texts", methods=["POST"])
    def api_create_text() -> tuple[dict, int]:
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
            segments=_extract_segments(data),
            background=data.get("background", "NONE").upper(),
            font=data.get("font", "KONGTEXT").upper(),
            speed=data.get("speed", 32),
        )
        created = repo.create(text)
        return {"text": created.to_dict()}, 201

    # Legacy endpoint
    @app.route("/texts", methods=["POST"])
    def create_text() -> tuple[dict, int]:
        """Legacy: create a text."""
        return api_create_text()

    @app.route("/api/texts/<int:text_id>", methods=["GET"])
    def api_get_text(text_id: int) -> tuple[dict, int]:
        """Get a single text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        text = repo.get(text_id)
        if not text:
            return {"error": "Text not found"}, 404
        return {"text": text.to_dict()}, 200

    @app.route("/texts/<int:text_id>", methods=["GET"])
    def get_text(text_id: int) -> tuple[dict, int]:
        return api_get_text(text_id)

    @app.route("/api/texts/<int:text_id>", methods=["PUT"])
    def api_update_text(text_id: int) -> tuple[dict, int]:
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
            segments=_extract_segments(data),
            background=data.get("background", "NONE").upper(),
            font=data.get("font", "KONGTEXT").upper(),
            speed=data.get("speed", 32),
        )
        updated = repo.update(text)
        if not updated:
            return {"error": "Failed to update text"}, 500
        return {"text": updated.to_dict()}, 200

    @app.route("/texts/<int:text_id>", methods=["PUT"])
    def update_text(text_id: int) -> tuple[dict, int]:
        return api_update_text(text_id)

    @app.route("/api/texts/<int:text_id>", methods=["DELETE"])
    def api_delete_text(text_id: int) -> tuple[dict, int]:
        """Delete a text."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        if not repo.delete(text_id):
            return {"error": "Text not found"}, 404
        return {"success": True}, 200

    @app.route("/texts/<int:text_id>", methods=["DELETE"])
    def delete_text(text_id: int) -> tuple[dict, int]:
        return api_delete_text(text_id)

    # --- Queue API ---

    @app.route("/api/queue", methods=["GET"])
    def api_get_queue() -> tuple[dict, int]:
        """Get the display queue with embedded text data."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        queue = repo.get_queue()
        entries = []
        for entry, text in queue:
            d = entry.to_dict()
            d["text"] = text.to_dict()
            entries.append(d)
        return {"queue": entries}, 200

    @app.route("/api/queue", methods=["POST"])
    def api_add_to_queue() -> tuple[dict, int]:
        """Add a text to the queue."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        data = request.get_json()
        if not data or "text_id" not in data:
            return {"error": "text_id is required"}, 400

        entry = repo.add_to_queue(data["text_id"])
        if not entry:
            return {"error": "Text not found"}, 404
        return {"entry": entry.to_dict()}, 201

    @app.route("/api/queue", methods=["PUT"])
    def api_reorder_queue() -> tuple[dict, int]:
        """Bulk reorder queue entries."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        data = request.get_json()
        if not data or "entries" not in data:
            return {"error": "entries array is required"}, 400

        entries = data["entries"]
        if not isinstance(entries, list):
            return {"error": "entries must be an array"}, 400

        for entry in entries:
            if "id" not in entry or "position" not in entry:
                return {"error": "Each entry must have id and position"}, 400

        repo.reorder_queue(entries)
        return {"success": True}, 200

    @app.route("/api/queue/<int:entry_id>", methods=["DELETE"])
    def api_remove_from_queue(entry_id: int) -> tuple[dict, int]:
        """Remove a queue entry."""
        repo = app.config.get("REPOSITORY")
        if not repo:
            return {"error": "Database not configured"}, 503

        if not repo.remove_from_queue(entry_id):
            return {"error": "Queue entry not found"}, 404
        return {"success": True}, 200

    return app
