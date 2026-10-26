"""Tests for the system time module and its web API."""

from datetime import datetime
from unittest.mock import patch

import pytest

from lichtkrant import system_time
from lichtkrant.config import Config
from lichtkrant.web import create_app


@pytest.fixture
def client():
    app = create_app(Config())
    app.config["TESTING"] = True
    return app.test_client()


class TestParseTime:
    def test_naive_local_time(self):
        assert system_time.parse_time("2026-10-01T14:30:00") == datetime(
            2026, 10, 1, 14, 30
        )

    def test_without_seconds(self):
        assert system_time.parse_time("2026-10-01T14:30") == datetime(
            2026, 10, 1, 14, 30
        )

    def test_with_utc_offset(self):
        parsed = system_time.parse_time("2026-10-01T14:30:00+02:00")
        assert parsed.utcoffset() is not None

    @pytest.mark.parametrize("value", ["", "not a date", None, 12345, "2026-13-01"])
    def test_invalid(self, value):
        with pytest.raises(ValueError):
            system_time.parse_time(value)

    @pytest.mark.parametrize("value", ["1999-12-31T23:59", "2100-01-01T00:00"])
    def test_out_of_range(self, value):
        with pytest.raises(ValueError):
            system_time.parse_time(value)


class TestSetSystemTime:
    def test_sets_realtime_clock(self):
        new_time = datetime(2026, 10, 1, 14, 30)
        with (
            patch("lichtkrant.system_time.time.clock_settime") as settime,
            patch("lichtkrant.system_time._sync_hardware_clock") as sync,
        ):
            system_time.set_system_time(new_time)
        settime.assert_called_once_with(
            system_time.time.CLOCK_REALTIME, new_time.timestamp()
        )
        sync.assert_called_once()

    def test_no_hardware_clock_sync_on_failure(self):
        with (
            patch(
                "lichtkrant.system_time.time.clock_settime",
                side_effect=PermissionError,
            ),
            patch("lichtkrant.system_time._sync_hardware_clock") as sync,
            pytest.raises(PermissionError),
        ):
            system_time.set_system_time(datetime(2026, 10, 1))
        sync.assert_not_called()


class TestSystemTimeApi:
    def test_config_page(self, client):
        response = client.get("/config/")
        assert response.status_code == 200
        assert b"Configuration" in response.data

    def test_get_time(self, client):
        response = client.get("/api/system/time")
        assert response.status_code == 200
        data = response.get_json()
        datetime.fromisoformat(data["time"])
        assert "timezone" in data

    def test_set_time(self, client):
        with patch("lichtkrant.system_time.set_system_time") as set_time:
            response = client.put(
                "/api/system/time", json={"time": "2026-10-01T14:30:00"}
            )
        assert response.status_code == 200
        set_time.assert_called_once_with(datetime(2026, 10, 1, 14, 30))
        assert "time" in response.get_json()

    @pytest.mark.parametrize(
        "payload",
        [{}, {"time": ""}, {"time": "nonsense"}, {"time": "1980-01-01T00:00"}],
    )
    def test_set_time_invalid(self, client, payload):
        with patch("lichtkrant.system_time.set_system_time") as set_time:
            response = client.put("/api/system/time", json=payload)
        assert response.status_code == 400
        assert "error" in response.get_json()
        set_time.assert_not_called()

    def test_set_time_no_json(self, client):
        response = client.put("/api/system/time", data="x")
        assert response.status_code == 400

    def test_set_time_permission_denied(self, client):
        with patch(
            "lichtkrant.system_time.set_system_time", side_effect=PermissionError
        ):
            response = client.put(
                "/api/system/time", json={"time": "2026-10-01T14:30:00"}
            )
        assert response.status_code == 403

    def test_set_time_os_error(self, client):
        with patch(
            "lichtkrant.system_time.set_system_time", side_effect=OSError("boom")
        ):
            response = client.put(
                "/api/system/time", json={"time": "2026-10-01T14:30:00"}
            )
        assert response.status_code == 500
