"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import yaml

from lichtkrant.config import Config, DatabaseConfig


class TestConfigDefaults:
    def test_default_values(self):
        config = Config()
        assert config.web.port == 8080
        assert config.web.host == "0.0.0.0"
        assert config.spi.device == "/dev/spidev0.0"
        assert config.gpio.request_pin == 17
        assert config.wifi.ssid == "Lichtkrant"
        assert config.database.path == "~/.lichtkrant/texts.db"

    def test_database_resolved_path(self):
        db = DatabaseConfig(path="~/.lichtkrant/texts.db")
        resolved = db.resolved_path
        assert isinstance(resolved, Path)
        assert "~" not in str(resolved)


class TestConfigLoad:
    def test_load_missing_file_returns_defaults(self):
        config = Config.load("/nonexistent/path/config.yaml")
        assert config.web.port == 8080

    def test_load_from_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.safe_dump({
                "web": {"port": 9090, "host": "127.0.0.1"},
                "wifi": {"ssid": "TestNet"},
            }, f)
            f.flush()

            config = Config.load(f.name)

        assert config.web.port == 9090
        assert config.web.host == "127.0.0.1"
        assert config.wifi.ssid == "TestNet"
        # Unset values use defaults
        assert config.spi.device == "/dev/spidev0.0"

    def test_load_empty_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            f.flush()

            config = Config.load(f.name)

        assert config.web.port == 8080

    def test_load_partial_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.safe_dump({"spi": {"speed_hz": 250000}}, f)
            f.flush()

            config = Config.load(f.name)

        assert config.spi.speed_hz == 250000
        assert config.spi.device == "/dev/spidev0.0"  # default


class TestConfigSave:
    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"

            config = Config()
            config.web.port = 3000
            config.wifi.ssid = "MySign"
            config.save(path)

            loaded = Config.load(path)
            assert loaded.web.port == 3000
            assert loaded.wifi.ssid == "MySign"

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "config.yaml"
            Config().save(path)
            assert path.exists()
