# Lichtkrant

Raspberry Pi controller for a "Lichtkrant" (Dutch: light newspaper) — a scrolling LED matrix display. The display hardware (PIC18F27K40 + NeoRGB LED matrices) communicates over SPI with the Pi, which provides a web interface for managing messages.

## Features

- Web UI for creating, editing, and scheduling scrolling text messages
- Per-segment text colors and control sequences (pause, blink, flash)
- Automatic text rotation with active/inactive toggling
- WiFi access point with captive portal for standalone operation
- SPI communication with REQUEST line handshake

## Installation on Raspberry Pi 5

### Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS (Bookworm or later)
- Python 3.11+
- SPI enabled
- The Lichtkrant display hardware connected via SPI

### 1. Enable SPI

```bash
sudo raspi-config nonint do_spi 0
```

Or use `raspi-config` interactively: Interface Options → SPI → Enable. Reboot after enabling.

Verify SPI is available:

```bash
ls /dev/spidev*
```

You should see `/dev/spidev0.0` (and possibly `/dev/spidev0.1`).

### 2. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3-dev git swig liblgpio-dev
```

### 3. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 4. Clone and install

```bash
git clone <repository-url> ~/lichtkrant
cd ~/lichtkrant
uv sync --extra hw
```

### 5. Configure

```bash
sudo mkdir -p /etc/lichtkrant
sudo cp config/config.yaml.example /etc/lichtkrant/config.yaml
sudo nano /etc/lichtkrant/config.yaml
```

Default configuration:

```yaml
spi:
  device: "/dev/spidev0.0"
  speed_hz: 500000
  mode: 0

gpio:
  request_pin: 17          # BCM pin for REQUEST handshake line
  request_active_high: true

wifi:
  ssid: "Lichtkrant"
  password: "lichtkrant"

web:
  host: "0.0.0.0"
  port: 8080
```

Adjust `request_pin` and `request_active_high` to match your wiring.

### 6. Run

```bash
# Full mode (SPI + WiFi AP + web)
uv run lichtkrant

# Web interface only (no SPI hardware needed)
uv run lichtkrant --no-spi --no-wifi

# With custom config
uv run lichtkrant -c /path/to/config.yaml

# Debug mode
uv run lichtkrant --debug --no-spi --no-wifi
```

Open `http://<pi-ip>:8080` in a browser, or connect to the "Lichtkrant" WiFi network and the captive portal will open automatically.

### 7. Run as a systemd service

Create the service file:

```bash
sudo tee /etc/systemd/system/lichtkrant.service > /dev/null << 'EOF'
[Unit]
Description=Lichtkrant LED Display Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/lichtkrant
ExecStart=/root/.local/bin/uv run lichtkrant
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

> **Note:** The service runs as root because SPI and GPIO access require it. Adjust `WorkingDirectory` and `ExecStart` paths if you installed elsewhere.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lichtkrant
sudo systemctl start lichtkrant
```

Check status:

```bash
sudo systemctl status lichtkrant
sudo journalctl -u lichtkrant -f
```

### Wiring

| Pi 5 (BCM) | PIC18F27K40 | Function |
|-------------|-------------|----------|
| GPIO 10 (MOSI) | SDI | SPI data |
| GPIO 11 (SCLK) | SCK | SPI clock |
| GPIO 8 (CE0) | SS | SPI chip select |
| GPIO 17 | REQUEST pin | Handshake (PIC signals ready) |
| GND | GND | Common ground |

The REQUEST pin is active-high by default (configurable in `config.yaml`).

## Captive Portal

When the WiFi access point is active, a captive portal is set up automatically so that connecting devices see a "Sign in to network" popup that opens the web UI. This works by:

1. **DNS interception** — a dnsmasq config in `/etc/NetworkManager/dnsmasq-shared.d/` resolves all DNS queries to the Pi's gateway IP
2. **Port 80 redirect** — an nftables rule redirects port 80 to the web server port (8080) since captive portal probes always use port 80
3. **Host-based redirect** — Flask checks the `Host` header and redirects foreign hosts (e.g. `captive.apple.com`) to the portal URL

This is all handled automatically when running with WiFi enabled. Use `--no-wifi` to disable both the access point and captive portal.

**Prerequisites:** NetworkManager and nftables must be installed. The service must run as root for nftables and dnsmasq configuration.

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Run without hardware
uv run lichtkrant --no-spi --no-wifi --debug
```
