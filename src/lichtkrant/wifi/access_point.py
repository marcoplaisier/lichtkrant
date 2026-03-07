"""WiFi access point management using NetworkManager."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lichtkrant.config import Config

logger = logging.getLogger(__name__)

DNSMASQ_CONF_PATH = Path("/etc/NetworkManager/dnsmasq-shared.d/lichtkrant-portal.conf")


class AccessPoint:
    """Manage WiFi access point using nmcli."""

    CONNECTION_NAME = "Lichtkrant-AP"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._active = False
        self._gateway_ip: str | None = None

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
            gateway_ip = self._get_gateway_ip()
            if gateway_ip:
                self._gateway_ip = gateway_ip
                self._setup_captive_portal(gateway_ip)
            return True

        return False

    def stop(self) -> bool:
        """Stop the WiFi access point."""
        self._teardown_captive_portal()
        result = subprocess.run(
            ["nmcli", "connection", "down", self.CONNECTION_NAME],
            capture_output=True,
        )
        if result.returncode == 0:
            self._active = False
            self._gateway_ip = None
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

    def get_ip_address(self) -> str | None:
        """Get the IP address of the access point interface."""
        if self._gateway_ip:
            return self._gateway_ip
        return self._get_gateway_ip()

    def _get_gateway_ip(self) -> str | None:
        """Query the AP's IP address from nmcli."""
        result = subprocess.run(
            [
                "nmcli",
                "-t",
                "-f",
                "IP4.ADDRESS",
                "connection",
                "show",
                self.CONNECTION_NAME,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                # Format: IP4.ADDRESS[1]:10.42.0.1/24
                if ":" in line:
                    addr = line.split(":", 1)[1]
                    # Strip CIDR prefix
                    return addr.split("/")[0]
        return None

    def _setup_captive_portal(self, gateway_ip: str) -> None:
        """Set up DNS interception and port 80 redirect for captive portal."""
        web_port = self.config.web.port

        # Write dnsmasq config to intercept all DNS queries
        try:
            DNSMASQ_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
            DNSMASQ_CONF_PATH.write_text(f"address=/#/{gateway_ip}\n")
            logger.info("Wrote dnsmasq captive portal config: %s", DNSMASQ_CONF_PATH)
        except OSError as e:
            logger.warning("Could not write dnsmasq config: %s", e)
            return

        # Restart dnsmasq by toggling the connection so it picks up the config
        subprocess.run(
            ["nmcli", "connection", "down", self.CONNECTION_NAME],
            capture_output=True,
        )
        subprocess.run(
            ["nmcli", "connection", "up", self.CONNECTION_NAME],
            capture_output=True,
        )

        # Redirect port 80 → web_port on the AP interface
        subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                "PREROUTING",
                "-i",
                "wlan0",
                "-p",
                "tcp",
                "--dport",
                "80",
                "-j",
                "REDIRECT",
                "--to-port",
                str(web_port),
            ],
            capture_output=True,
        )
        logger.info(
            "Captive portal: DNS → %s, port 80 → %d", gateway_ip, web_port
        )

    def _teardown_captive_portal(self) -> None:
        """Remove DNS interception and port 80 redirect."""
        web_port = self.config.web.port

        # Remove dnsmasq config
        try:
            if DNSMASQ_CONF_PATH.exists():
                DNSMASQ_CONF_PATH.unlink()
                logger.info("Removed dnsmasq captive portal config")
        except OSError as e:
            logger.warning("Could not remove dnsmasq config: %s", e)

        # Remove iptables rule
        subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-D",
                "PREROUTING",
                "-i",
                "wlan0",
                "-p",
                "tcp",
                "--dport",
                "80",
                "-j",
                "REDIRECT",
                "--to-port",
                str(web_port),
            ],
            capture_output=True,
        )
        logger.info("Captive portal teardown complete")
