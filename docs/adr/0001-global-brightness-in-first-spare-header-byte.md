# Brightness is one global setting, sent in the first spare header byte

The display controller has no brightness input of its own, so every message carries the level in header byte 4, the first of the two spare bytes. Byte 5 stays `0x00`, free for a later protocol addition. Brightness is a single display-wide setting rather than a property of each text: it describes where the display stands (a bright shop window versus a dark room), not what a text says, and a per-text level would make the display flicker between texts. The default is 1, because level 4 proved uncomfortably bright on the real display.

## Consequences

- The byte allocation is shared with the PIC firmware, so moving brightness to another byte needs a firmware change too.
- Changing the level takes effect from the next message the controller requests, not mid-scroll.
