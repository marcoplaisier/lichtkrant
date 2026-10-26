# Lichtkrant

Raspberry Pi controller for a scrolling LED matrix display ("lichtkrant"). The display hardware (PIC18F27K40 + NeoRGB matrices) is already built; this repo is the Pi side: web UI, queue, and SPI sender.

- **Protocol**: the binary message format, colors, control sequences and timing constraints are in `docs/protocol.md`. Read it before touching `protocol/`, `dispatcher.py` or anything that changes the bytes sent.
- **REST API**: `docs/openapi.yaml` is the source of truth for endpoints and the text segment format.
- **Configuration**: `config/config.yaml.example` holds the settings and their deployed values.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for marcoplaisier/lichtkrant, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
