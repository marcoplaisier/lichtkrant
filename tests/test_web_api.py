"""Tests for web API endpoints."""

import tempfile
from pathlib import Path

import pytest

from lichtkrant.config import Config
from lichtkrant.db.repository import TextRepository
from lichtkrant.web import create_app


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TextRepository(Path(tmpdir) / "test.db")


@pytest.fixture
def app(repo):
    config = Config()
    app = create_app(config, repository=repo)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_text_data():
    return {
        "segments": [{"type": "text", "text": "Hello", "color": "WHITE"}],
        "background": "NONE",
        "font": "KONGTEXT",
        "speed": 32,
    }


# --- Page routes ---


class TestPageRoutes:
    def test_dashboard(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_texts_page(self, client):
        response = client.get("/texts/")
        assert response.status_code == 200

    def test_queue_page(self, client):
        response = client.get("/queue/")
        assert response.status_code == 200

    def test_welcome_page(self, client):
        response = client.get("/welcome")
        assert response.status_code == 200


# --- Colors & fonts ---


class TestMetaEndpoints:
    def test_get_colors(self, client):
        response = client.get("/colors")
        assert response.status_code == 200
        data = response.get_json()
        assert "text_colors" in data
        assert "background_colors" in data
        assert "WHITE" in data["text_colors"]

    def test_get_fonts(self, client):
        response = client.get("/fonts")
        assert response.status_code == 200
        data = response.get_json()
        assert "fonts" in data
        assert "KONGTEXT" in data["fonts"]


# --- Direct send ---


class TestDirectSend:
    def test_send_message(self, client):
        response = client.post(
            "/api/send",
            json={"text": "Hello", "color": "WHITE", "speed": 32},
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_send_legacy_endpoint(self, client):
        response = client.post(
            "/send",
            json={"text": "Hello"},
        )
        assert response.status_code == 200

    def test_send_no_json(self, client):
        response = client.post(
            "/api/send",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_send_empty_text(self, client):
        response = client.post("/api/send", json={"text": ""})
        assert response.status_code == 400

    def test_send_invalid_color(self, client):
        response = client.post(
            "/api/send", json={"text": "Hi", "color": "NOPE"}
        )
        assert response.status_code == 400

    def test_send_invalid_background(self, client):
        response = client.post(
            "/api/send", json={"text": "Hi", "background": "NOPE"}
        )
        assert response.status_code == 400

    def test_send_invalid_font(self, client):
        response = client.post(
            "/api/send", json={"text": "Hi", "font": "NOPE"}
        )
        assert response.status_code == 400

    def test_send_invalid_speed(self, client):
        response = client.post(
            "/api/send", json={"text": "Hi", "speed": 0}
        )
        assert response.status_code == 400


# --- Text CRUD ---


class TestTextCRUD:
    def test_list_texts_empty(self, client):
        response = client.get("/api/texts")
        assert response.status_code == 200
        assert response.get_json()["texts"] == []

    def test_create_text(self, client, sample_text_data):
        response = client.post("/api/texts", json=sample_text_data)
        assert response.status_code == 201
        text = response.get_json()["text"]
        assert text["id"] == 1
        assert text["content"] == "Hello"

    def test_create_text_no_json(self, client):
        response = client.post(
            "/api/texts",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_text_empty_segments(self, client):
        response = client.post("/api/texts", json={"segments": []})
        assert response.status_code == 400

    def test_create_text_invalid_color(self, client):
        response = client.post("/api/texts", json={
            "segments": [{"type": "text", "text": "Hi", "color": "NOPE"}],
        })
        assert response.status_code == 400

    def test_create_text_invalid_speed(self, client):
        response = client.post("/api/texts", json={
            "segments": [{"type": "text", "text": "Hi", "color": "WHITE"}],
            "speed": 999,
        })
        assert response.status_code == 400

    def test_create_text_legacy_format(self, client):
        response = client.post("/api/texts", json={
            "content": "Legacy text",
            "color": "RED",
        })
        assert response.status_code == 201
        text = response.get_json()["text"]
        assert text["content"] == "Legacy text"

    def test_get_text(self, client, sample_text_data):
        create = client.post("/api/texts", json=sample_text_data)
        text_id = create.get_json()["text"]["id"]

        response = client.get(f"/api/texts/{text_id}")
        assert response.status_code == 200
        assert response.get_json()["text"]["id"] == text_id

    def test_get_text_not_found(self, client):
        response = client.get("/api/texts/999")
        assert response.status_code == 404

    def test_update_text(self, client, sample_text_data):
        create = client.post("/api/texts", json=sample_text_data)
        text_id = create.get_json()["text"]["id"]

        updated_data = {
            "segments": [{"type": "text", "text": "Updated", "color": "RED"}],
            "background": "NONE",
            "font": "KONGTEXT",
            "speed": 50,
        }
        response = client.put(f"/api/texts/{text_id}", json=updated_data)
        assert response.status_code == 200
        assert response.get_json()["text"]["content"] == "Updated"
        assert response.get_json()["text"]["speed"] == 50

    def test_update_text_not_found(self, client, sample_text_data):
        response = client.put("/api/texts/999", json=sample_text_data)
        assert response.status_code == 404

    def test_update_text_no_json(self, client, sample_text_data):
        create = client.post("/api/texts", json=sample_text_data)
        text_id = create.get_json()["text"]["id"]
        response = client.put(
            f"/api/texts/{text_id}",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_delete_text(self, client, sample_text_data):
        create = client.post("/api/texts", json=sample_text_data)
        text_id = create.get_json()["text"]["id"]

        response = client.delete(f"/api/texts/{text_id}")
        assert response.status_code == 200

        response = client.get(f"/api/texts/{text_id}")
        assert response.status_code == 404

    def test_delete_text_not_found(self, client):
        response = client.delete("/api/texts/999")
        assert response.status_code == 404

    def test_list_texts_after_create(self, client, sample_text_data):
        client.post("/api/texts", json=sample_text_data)
        client.post("/api/texts", json=sample_text_data)

        response = client.get("/api/texts")
        assert len(response.get_json()["texts"]) == 2

    def test_legacy_list_endpoint(self, client, sample_text_data):
        """Legacy GET /texts returns same data as /api/texts."""
        client.post("/api/texts", json=sample_text_data)
        response = client.get("/texts")
        assert response.status_code == 200
        assert len(response.get_json()["texts"]) == 1


# --- Queue API ---


class TestQueueAPI:
    def _create_text(self, client):
        response = client.post("/api/texts", json={
            "segments": [{"type": "text", "text": "Test", "color": "WHITE"}],
        })
        return response.get_json()["text"]["id"]

    def test_get_queue_empty(self, client):
        response = client.get("/api/queue")
        assert response.status_code == 200
        assert response.get_json()["queue"] == []

    def test_add_to_queue(self, client):
        text_id = self._create_text(client)
        response = client.post("/api/queue", json={"text_id": text_id})
        assert response.status_code == 201
        entry = response.get_json()["entry"]
        assert entry["text_id"] == text_id

    def test_add_to_queue_missing_text_id(self, client):
        response = client.post("/api/queue", json={})
        assert response.status_code == 400

    def test_add_to_queue_nonexistent_text(self, client):
        response = client.post("/api/queue", json={"text_id": 999})
        assert response.status_code == 404

    def test_get_queue_with_entries(self, client):
        text_id = self._create_text(client)
        client.post("/api/queue", json={"text_id": text_id})
        client.post("/api/queue", json={"text_id": text_id})

        response = client.get("/api/queue")
        queue = response.get_json()["queue"]
        assert len(queue) == 2
        # Each entry should have embedded text data
        assert "text" in queue[0]
        assert queue[0]["text"]["content"] == "Test"

    def test_remove_from_queue(self, client):
        text_id = self._create_text(client)
        add = client.post("/api/queue", json={"text_id": text_id})
        entry_id = add.get_json()["entry"]["id"]

        response = client.delete(f"/api/queue/{entry_id}")
        assert response.status_code == 200

        queue = client.get("/api/queue").get_json()["queue"]
        assert len(queue) == 0

    def test_remove_nonexistent_entry(self, client):
        response = client.delete("/api/queue/999")
        assert response.status_code == 404

    def test_reorder_queue(self, client):
        t1 = self._create_text(client)
        t2 = self._create_text(client)
        e1 = client.post("/api/queue", json={"text_id": t1}).get_json()["entry"]
        e2 = client.post("/api/queue", json={"text_id": t2}).get_json()["entry"]

        # Swap order
        response = client.put("/api/queue", json={
            "entries": [
                {"id": e1["id"], "position": 20},
                {"id": e2["id"], "position": 10},
            ]
        })
        assert response.status_code == 200

        queue = client.get("/api/queue").get_json()["queue"]
        assert queue[0]["text_id"] == t2
        assert queue[1]["text_id"] == t1

    def test_reorder_queue_no_json(self, client):
        response = client.put(
            "/api/queue",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reorder_queue_invalid_entries(self, client):
        response = client.put("/api/queue", json={"entries": "not a list"})
        assert response.status_code == 400

    def test_reorder_queue_missing_fields(self, client):
        response = client.put("/api/queue", json={
            "entries": [{"id": 1}]
        })
        assert response.status_code == 400

    def test_delete_text_removes_queue_entries(self, client):
        """Deleting a text cascades to its queue entries."""
        text_id = self._create_text(client)
        client.post("/api/queue", json={"text_id": text_id})

        client.delete(f"/api/texts/{text_id}")
        queue = client.get("/api/queue").get_json()["queue"]
        assert len(queue) == 0


# --- No-repo error paths ---


class TestNoRepository:
    def test_list_texts_no_repo(self):
        config = Config()
        app = create_app(config)
        app.config["TESTING"] = True
        with app.test_client() as client:
            response = client.get("/api/texts")
            assert response.status_code == 503

    def test_get_queue_no_repo(self):
        config = Config()
        app = create_app(config)
        app.config["TESTING"] = True
        with app.test_client() as client:
            response = client.get("/api/queue")
            assert response.status_code == 503
