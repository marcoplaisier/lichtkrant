# Lichtkrant - LED Scrolling Display Controller

## Project Overview

Raspberry Pi software to control a "Lichtkrant" (Dutch: light newspaper) - a scrolling LED matrix display. The display hardware (PIC18F27K40 + NeoRGB LED matrices) is already built; this project implements the Pi-side controller.

## Architecture

```
[Web Interface] → [Message Builder] → [SPI Layer] → [PIC Controller] → [LED Matrices]
     ↑                                      ↑
[Captive Portal]                    [config.yaml]
```

- **Standalone operation**: Pi runs as WiFi access point with captive portal
- **User access**: Scan QR code → connect to "Lichtkrant" WiFi → portal auto-opens
- **Communication**: SPI master (Pi) to SPI slave (PIC) with REQUEST handshake line

## Protocol Specification

### Message Format

| Section | Bytes | Content |
|---------|-------|---------|
| Header | 6 | `0xFE`, background, speed, font, `0x00`, `0x00` |
| Text | 2 per char | ASCII byte (0x00-0x7F), color byte |
| Terminator | 2 | `0xAA`, `0xAA` |

### Color Codes

| Color | Background | Text |
|-------|------------|------|
| None/Black | 0x00 | 0x00 |
| Green | 0x84 | 0x10 |
| Red | 0x88 | 0x20 |
| Blue | 0x8C | 0x30 |
| Yellow | 0x90 | 0x40 |
| Cyan | 0x94 | 0x50 |
| Magenta | 0x98 | 0x60 |
| White | 0x9C | 0x70 |

### Control Sequences

4-byte sequences starting with `#` (0x23):

| Sequence | Effect |
|----------|--------|
| `#`, 0x01, XX, 0x00 | Pause XX seconds |
| `#`, 0x02, XX, 0x00 | Fast blink XX times |
| `#`, 0x03, XX, 0x00 | Slow blink XX times |
| `#`, 0x04, XX, 0x00 | Flash instant on, hold XX sec, scroll off |
| `#`, 0x05, XX, 0x00 | Flash instant on, hold XX sec, instant off |
| `#`, 0x06, `#`, color | Literal '#' character |

Flash sequences (#4, #5): text until `0xFD`, `0xFD` marker is flash content.

### Fonts

- 0x01: Kongtext
- 0x02: Custom
- 0x03: Munro Small

## Configuration

All settings in `/etc/lichtkrant/config.yaml`:

```yaml
spi:
  device: "/dev/spidev0.0"
  speed_hz: 125000
  mode: 0

gpio:
  request_pin: 17
  request_active_high: false

wifi:
  ssid: "Lichtkrant"
  password: "lichtkrant"

web:
  host: "0.0.0.0"
  port: 8080
```

## Text Segments API

Texts support per-segment colors. The API accepts a `segments` array:

```json
{
  "segments": [
    {"text": "Hello ", "color": "RED"},
    {"text": "World", "color": "BLUE"}
  ],
  "background": "NONE",
  "font": "KONGTEXT",
  "speed": 32
}
```

Legacy format (`content` + `color` fields) is still accepted for backward compatibility.

## Constraints

- ASCII only: 0x00-0x7F (no extended characters)
- Speed: 0x01-0xFF (units of ~50ms, affected by PIC rendering time)
- Display update takes ~25ms for 3 matrices on PIC side
- Pi must wait for REQUEST signal before sending

## Tech Stack

- Python 3
- spidev (SPI communication)
- RPi.GPIO (handshake line)
- Flask (web interface)
- NetworkManager/nmcli (access point)
- qrcode (QR generation)
- uv for package management
