"""WiFi access point management using NetworkManager."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lichtkrant.config import Config


class AccessPoint:
    """Manage WiFi access point using nmcli."""

    CONNECTION_NAME = "Lichtkrant-AP"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._active = False

    def start(self) -> bool:
        """Start the WiFi access point."""
        ssid = self.config.wifi.ssid
        password = self.config.wifi.password

        # Delete existing connection if present
        subprocess.run(
            ["nmcli", "connection", "delete", self.CONNECTION_NAME],
            capture_output=True,
        )

        # Create new hotspot
        result = subprocess.run(
            [
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                "ifname",
                "wlan0",
                "con-name",
                self.CONNECTION_NAME,
                "ssid",
                ssid,
                "password",
                password,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            self._active = True
            return True

        return False

    def stop(self) -> bool:
        """Stop the WiFi access point."""
        result = subprocess.run(
            ["nmcli", "connection", "down", self.CONNECTION_NAME],
            capture_output=True,
        )
        if result.returncode == 0:
            self._active = False
            return True
        return False

    def is_active(self) -> bool:
        """Check if the access point is currently active."""
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,STATE", "connection", "show", "--active"],
            capture_output=True,
            text=True,
        )
        return self.CONNECTION_NAME in result.stdout

    @staticmethod
    def get_ip_address() -> str | None:
        """Get the IP address of the access point interface."""
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            addresses = result.stdout.strip().split()
            # Return first address (typically the AP address)
            return addresses[0] if addresses else None
        return None
