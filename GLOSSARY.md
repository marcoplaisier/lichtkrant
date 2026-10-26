# Lichtkrant

A scrolling LED matrix display driven by a Raspberry Pi. People compose texts on their phone and the display cycles through them.

## Content

**Text**:
A stored piece of content for the display: one or more segments, plus background, font and speed.
_Avoid_: Message, item, slide

**Segment**:
One part of a text: either scrolling characters in a single color, or an effect.
_Avoid_: Part, chunk, span

**Effect**:
A segment that does something other than scroll characters: a pause, a fast or slow blink, or a flash.
_Avoid_: Control sequence (that is how an effect is encoded, not what it is)

**Flash**:
An effect that shows its own short content instantly, holds it, then clears it or scrolls it off.

**Template variable**:
A placeholder in segment text, such as `{{time}}`, that is replaced with a current value each time the text is sent.
_Avoid_: Macro, tag

## Playback

**Queue**:
The ordered list of texts the display cycles through. The same text can appear more than once.
_Avoid_: Playlist, active texts

**Direct send**:
Sending one text to the display immediately, outside the queue.
_Avoid_: Broadcast, announcement

**Message**:
The encoded bytes for one text, as the display controller receives them.
_Avoid_: Frame, packet

**REQUEST**:
The handshake signal the display controller raises when it is ready for the next message.
_Avoid_: Ready line, interrupt

**Unconfirmed clock**:
The state of the Pi's clock after a boot, before anyone has set it or it has synced over the internet. Its time is probably wrong.
_Avoid_: Unsynced clock, clock drift

## Appearance

**Speed**:
The delay between two scroll steps of a text. A higher speed value scrolls slower.
_Avoid_: Scroll rate

**Speed preset**:
A named speed, from Very slow to Very fast, that stands for one fixed speed value.
_Avoid_: Speed level

**Brightness**:
The light level of the whole display, from 1 (dimmest) to 4 (brightest). It applies to every text, not to one.
_Avoid_: Intensity, dimming level
