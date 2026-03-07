"""Configuration management for Lichtkrant."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SPIConfig:
    """SPI configuration."""

    device: str = "/dev/spidev0.0"
    speed_hz: int = 125000
    mode: int = 0


@dataclass
class GPIOConfig:
    """GPIO configuration."""

    request_pin: int = 17
    request_active_high: bool = False


@dataclass
class WiFiConfig:
    """WiFi access point configuration."""

    ssid: str = "Lichtkrant"
    password: str = "lichtkrant"


@dataclass
class WebConfig:
    """Web server configuration."""

    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: str = "~/.lichtkrant/texts.db"

    @property
    def resolved_path(self) -> Path:
        """Return expanded path."""
        return Path(self.path).expanduser()


@dataclass
class Config:
    """Main configuration container."""

    spi: SPIConfig = field(default_factory=SPIConfig)
    gpio: GPIOConfig = field(default_factory=GPIOConfig)
    wifi: WiFiConfig = field(default_factory=WiFiConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def load(cls, path: Path | str = "/etc/lichtkrant/config.yaml") -> Config:
        """Load configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(
            spi=SPIConfig(**data.get("spi", {})),
            gpio=GPIOConfig(**data.get("gpio", {})),
            wifi=WiFiConfig(**data.get("wifi", {})),
            web=WebConfig(**data.get("web", {})),
            database=DatabaseConfig(**data.get("database", {})),
        )

    def save(self, path: Path | str = "/etc/lichtkrant/config.yaml") -> None:
        """Save configuration to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "spi": {
                "device": self.spi.device,
                "speed_hz": self.spi.speed_hz,
                "mode": self.spi.mode,
            },
            "gpio": {
                "request_pin": self.gpio.request_pin,
                "request_active_high": self.gpio.request_active_high,
            },
            "wifi": {
                "ssid": self.wifi.ssid,
                "password": self.wifi.password,
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
            },
            "database": {
                "path": self.database.path,
            },
        }

        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)
