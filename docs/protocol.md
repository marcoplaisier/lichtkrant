# Display Protocol

Binary protocol between the Pi (SPI master) and the PIC18F27K40 display controller (SPI slave). The builder is `src/lichtkrant/protocol/builder.py`; the decoder used by `--dry-run` is `src/lichtkrant/protocol/decoder.py`.

## Message Format

| Section | Bytes | Content |
|---------|-------|---------|
| Header | 6 | `0xFE`, background, speed, font, brightness, `0x00` |
| Text | 2 per char | ASCII byte (0x00-0x7F), color byte |
| Terminator | 2 | `0xAA`, `0xAA` |

## Brightness

The display has no brightness control of its own, so the Pi sends it in the
first spare header byte: `0x01` (dimmest) to `0x04` (brightest). It is a global
setting stored in the database and set on the Configuration page. Default is 1,
because full brightness is very bright.

## Color Codes

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

## Control Sequences

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

## Fonts

- 0x01: Kongtext
- 0x02: Custom
- 0x03: Munro Small

## Constraints

- ASCII only: 0x00-0x7F (no extended characters)
- Speed: 0x01-0xFF. It is a delay between scroll steps in units of ~50ms, so higher is slower; PIC rendering time adds to it
- Display update takes ~25ms for 3 matrices on PIC side
- Pi must wait for REQUEST signal before sending

