"""Tests for display brightness: protocol header, storage, dispatcher and API."""

import tempfile
from pathlib import Path

import pytest

from lichtkrant.config import Config
from lichtkrant.db.models import Text, TextSegment
from lichtkrant.db.repository import TextRepository
from lichtkrant.dispatcher import TextDispatcher
from lichtkrant.protocol import MessageBuilder
from lichtkrant.protocol.decoder import decode
from lichtkrant.spi.spy import SpySPIDriver
from lichtkrant.web import create_app

BRIGHTNESS_BYTE = 4
SPARE_BYTE = 5


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TextRepository(Path(tmpdir) / "test.db")


@pytest.fixture
def client(repo):
    app = create_app(Config(), repository=repo)
    app.config["TESTING"] = True
    return app.test_client()


class TestBuilder:
    def test_default_is_brightest(self):
        msg = MessageBuilder().add_text("A").build()
        assert msg[BRIGHTNESS_BYTE] == 4
        assert msg[SPARE_BYTE] == 0x00

    @pytest.mark.parametrize("level", [1, 2, 3, 4])
    def test_level_in_first_spare_byte(self, level):
        msg = MessageBuilder(brightness=level).add_text("A").build()
        assert msg[BRIGHTNESS_BYTE] == level
        assert msg[SPARE_BYTE] == 0x00

    @pytest.mark.parametrize("level", [0, 5, -1, 255])
    def test_out_of_range(self, level):
        with pytest.raises(ValueError):
            MessageBuilder(brightness=level)

    def test_decoder_shows_brightness(self):
        msg = MessageBuilder(brightness=2).add_text("A").build()
        assert "brightness=2" in decode(msg)[0]


class TestRepository:
    def test_default(self, repo):
        assert repo.get_brightness() == 4

    def test_set_and_persist(self, repo):
        repo.set_brightness(2)
        assert TextRepository(repo.db_path).get_brightness() == 2

    def test_overwrite(self, repo):
        repo.set_brightness(1)
        repo.set_brightness(3)
        assert repo.get_brightness() == 3

    @pytest.mark.parametrize("level", [0, 5])
    def test_set_out_of_range(self, repo, level):
        with pytest.raises(ValueError):
            repo.set_brightness(level)

    def test_corrupt_value_falls_back_to_default(self, repo):
        repo._set_setting("brightness", "bright")
        assert repo.get_brightness() == 4


class TestDispatcher:
    def test_message_uses_stored_brightness(self, repo):
        config = Config()
        repo.set_brightness(1)
        dispatcher = TextDispatcher(config, repo, SpySPIDriver(config))
        text = Text(
            id=None,
            segments=[TextSegment(text="Hi", color="WHITE")],
            background="NONE",
            font="KONGTEXT",
            speed=32,
        )
        assert dispatcher._build_message(text)[BRIGHTNESS_BYTE] == 1


class TestApi:
    def test_get_default(self, client):
        response = client.get("/api/settings/brightness")
        assert response.status_code == 200
        assert response.get_json() == {"brightness": 4, "min": 1, "max": 4}

    def test_set(self, client, repo):
        response = client.put("/api/settings/brightness", json={"brightness": 2})
        assert response.status_code == 200
        assert response.get_json()["brightness"] == 2
        assert repo.get_brightness() == 2

    @pytest.mark.parametrize(
        "payload",
        [{}, {"brightness": 0}, {"brightness": 5}, {"brightness": "3"},
         {"brightness": 2.5}, {"brightness": True}],
    )
    def test_set_invalid(self, client, repo, payload):
        response = client.put("/api/settings/brightness", json=payload)
        assert response.status_code == 400
        assert repo.get_brightness() == 4

    def test_no_repository(self):
        client = create_app(Config()).test_client()
        assert client.get("/api/settings/brightness").status_code == 503
        response = client.put("/api/settings/brightness", json={"brightness": 2})
        assert response.status_code == 503
