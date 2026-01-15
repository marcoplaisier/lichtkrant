"""Main entry point for Lichtkrant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lichtkrant.config import Config
from lichtkrant.web import create_app


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Lichtkrant - LED Scrolling Display Controller"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default="/etc/lichtkrant/config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--no-spi",
        action="store_true",
        help="Run without SPI hardware (web interface only)",
    )
    parser.add_argument(
        "--no-wifi",
        action="store_true",
        help="Don't start WiFi access point",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask in debug mode",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = Config.load(args.config)

    # Initialize SPI if available and not disabled
    spi_driver = None
    if not args.no_spi:
        try:
            from lichtkrant.spi import SPIDriver

            spi_driver = SPIDriver(config)
            spi_driver.open()
            print(f"SPI initialized on {config.spi.device}")
        except Exception as e:
            print(f"Warning: Could not initialize SPI: {e}")
            print("Running in web-only mode")

    # Start WiFi access point if not disabled
    if not args.no_wifi:
        try:
            from lichtkrant.wifi import AccessPoint

            ap = AccessPoint(config)
            if ap.start():
                print(f"WiFi access point started: {config.wifi.ssid}")
                ip = ap.get_ip_address()
                if ip:
                    print(f"Connect to http://{ip}:{config.web.port}/")
            else:
                print("Warning: Could not start WiFi access point")
        except Exception as e:
            print(f"Warning: WiFi setup failed: {e}")

    # Create and run Flask app
    app = create_app(config, spi_driver)

    try:
        print(f"Starting web server on {config.web.host}:{config.web.port}")
        app.run(
            host=config.web.host,
            port=config.web.port,
            debug=args.debug,
        )
    finally:
        if spi_driver:
            spi_driver.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
