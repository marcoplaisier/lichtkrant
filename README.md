# Lichtkrant

Raspberry Pi controller for a "Lichtkrant" (Dutch: light newspaper) — a scrolling LED matrix display. The display hardware (PIC18F27K40 + NeoRGB LED matrices) communicates over SPI with the Pi, which provides a web interface for managing messages.

## Features

- **Multi-page web UI** — Dashboard, Text management, and Queue management on separate pages
- **Display queue** — Drag-and-drop ordering of texts for playback; a text can appear multiple times
- **Per-segment styling** — Multiple colors, pause, blink, and flash effects within a single message
- **Template variables** — `{{date}}`, `{{time}}`, and `{{symbol:AAPL}}` resolved at display time
- **WiFi access point** with captive portal for standalone operation
- **Dry-run mode** — Decode and log SPI messages without hardware (`--dry-run`)
- SPI communication with REQUEST line handshake

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  Web UI     │────▶│  Flask App   │────▶│  SQLite DB │
│  (Browser)  │◀────│  (REST API)  │◀────│  (texts +  │
└─────────────┘     └──────┬───────┘     │   queue)   │
                           │             └─────┬──────┘
                           │                   │
                    ┌──────▼───────┐     ┌─────▼──────┐
                    │  Dispatcher  │────▶│ SPI Driver │──▶ LED Display
                    │  (thread)    │     │ (or Spy)   │
                    └──────┬───────┘     └────────────┘
                           │
                    ┌──────▼───────┐
                    │  Templating  │──▶ yfinance (stock prices)
                    └──────────────┘
```

**Data flow:** User creates texts via the web UI and arranges them in a queue. The dispatcher thread continuously cycles through the queue, resolves any template variables, builds the binary protocol message, and sends it over SPI when the display signals ready via the REQUEST line.

### Key modules

| Module | Purpose |
|--------|---------|
| `web/app.py` | Flask app — page routes, REST API, captive portal |
| `db/repository.py` | SQLite storage for texts and queue (WAL mode) |
| `db/models.py` | `Text`, `TextSegment`, `QueueEntry` dataclasses |
| `dispatcher.py` | Background thread: queue → template render → SPI send |
| `templating.py` | `{{date}}`, `{{time}}`, `{{symbol:AAPL}}` resolution |
| `protocol/builder.py` | Builds binary messages for the LED display protocol |
| `protocol/decoder.py` | Decodes binary messages back to human-readable form |
| `spi/driver.py` | Real SPI + GPIO communication (requires hardware) |
| `spi/spy.py` | Spy driver for `--dry-run` mode (logs decoded messages) |
| `config.py` | YAML configuration loading |
| `wifi/access_point.py` | WiFi AP via NetworkManager + captive portal setup |

## REST API

Full OpenAPI 3.1 spec: [`docs/openapi.yaml`](docs/openapi.yaml)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/texts` | GET | List all texts |
| `/api/texts` | POST | Create a text |
| `/api/texts/<id>` | GET | Get a text |
| `/api/texts/<id>` | PUT | Update a text |
| `/api/texts/<id>` | DELETE | Delete a text (cascades to queue) |
| `/api/queue` | GET | Get queue with embedded text data |
| `/api/queue` | POST | Add text to queue (`{text_id}`) |
| `/api/queue` | PUT | Bulk reorder (`{entries: [{id, position}]}`) |
| `/api/queue/<id>` | DELETE | Remove a queue entry |
| `/api/send` | POST | Send a message directly to display |
| `/colors` | GET | List available colors |
| `/fonts` | GET | List available fonts |

## Template Variables

Use these placeholders in text segments — they're resolved each time the dispatcher sends the message:

| Template | Output | Example |
|----------|--------|---------|
| `{{date}}` | Local date | `26 Mar 2026` |
| `{{time}}` | Local time | `14:30` |
| `{{symbol:AAPL}}` | Stock price via Yahoo Finance | `AAPL 198.50` |

Stock prices are cached for 5 minutes. Failed lookups show `SYMBOL:N/A` and are cached for 1 minute.

## Installation

### Prerequisites

- Raspberry Pi 3B or Pi 5 running Raspberry Pi OS (Bookworm)
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

**Raspberry Pi 3B:**

```bash
sudo apt update
sudo apt install -y python3-dev git
```

**Raspberry Pi 5:**

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
```

**Raspberry Pi 3B:**

```bash
uv sync --extra hw-pi3
```

**Raspberry Pi 5:**

```bash
uv sync --extra hw-pi5
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

# Dry-run mode (log decoded SPI messages without hardware)
uv run lichtkrant --dry-run --no-wifi

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

The SPI and GPIO pin layout is identical for Pi 3B and Pi 5 (BCM numbering):

| BCM Pin | PIC18F27K40 | Function |
|---------|-------------|----------|
| GPIO 10 (MOSI) | SDI | SPI data |
| GPIO 11 (SCLK) | SCK | SPI clock |
| GPIO 8 (CE0) | SS | SPI chip select |
| GPIO 17 | REQUEST pin | Handshake (PIC signals ready) |
| GND | GND | Common ground |

The REQUEST pin is active-high by default (configurable in `config.yaml`).

## Captive Portal

When the WiFi access point is active, a captive portal is set up automatically so that connecting devices see a "Sign in to network" popup. The popup shows a minimal welcome page; tapping "Open Lichtkrant" opens the full UI in the device's browser.

How it works:

1. **DNS interception** — a dnsmasq config resolves all DNS queries to the Pi's gateway IP
2. **Port 80 redirect** — an nftables rule redirects port 80 to the web server port (8080)
3. **Host-based redirect** — Flask checks the `Host` header and redirects foreign hosts to `/welcome`
4. **Welcome page** — a minimal landing page designed for the small captive portal sheet, with a link to open the full dashboard in the real browser

Use `--no-wifi` to disable both the access point and captive portal.

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

# Run with SPI message logging (no hardware needed)
uv run lichtkrant --dry-run --no-wifi --debug
```
