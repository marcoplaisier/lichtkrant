# Pre-Mortem: Lichtkrant Field Deployment

**Timeframe:** 6 months running on a Pi, unattended, connected to the LED display.

## Failure Narratives

### 1. SQLite Database Corruption on Power Loss — Likelihood: High | Impact: High

It's 2 months from now. The Pi is running at a craft fair, powered by an extension cord. Someone trips on the cable. The Pi loses power mid-write — the dispatcher was reading from SQLite while the web UI was simultaneously writing a new queue entry. Despite WAL mode, the `-wal` and `-shm` files are left in an inconsistent state. On reboot, SQLite can't open the database. The systemd service restart-loops. The display shows nothing for the rest of the event.

**Root cause:** the Pi has no shutdown procedure, no power-loss resilience beyond WAL, and no database recovery or fallback logic. `_connect()` opens a fresh connection every call but never runs `PRAGMA integrity_check` or handles a corrupted DB.

**Consequence chain:**
- 1st order: Database unreadable, service crashes on startup
- 2nd order: Display is blank — the entire purpose of the device is defeated
- 3rd order: User loses trust in reliability, carries a laptop as backup

### 2. Dispatcher Thread Dies Silently — Likelihood: Medium | Impact: High

It's 3 months in. A text contains `{{symbol:AAPL}}` and the yfinance library raises an unexpected exception type (not caught by `except Exception` in `_fetch_price` but perhaps a `SystemExit` or `KeyboardInterrupt` from a signal). The `_dispatch_loop` method has no top-level exception handler. The daemon thread dies. The `_running` flag stays `True`. The display freezes on the last message. The web UI still works, so the user keeps editing texts, not realizing nothing is being sent. There's no health check, no watchdog, no indicator in the UI that playback has stopped.

**Root cause:** `_dispatch_loop` catches `(KeyError, ValueError)` for invalid texts but has no catch-all. A daemon thread dying produces no visible error — no log, no UI feedback.

**Consequence chain:**
- 1st order: Display freezes on one message
- 2nd order: User edits texts, queues them, thinks they're working — wasted effort
- 3rd order: Problem only discovered when someone physically looks at the sign and sees the same text for hours

### 3. SD Card Fills Up from yfinance/logging — Checked: largely ruled out

The original narrative assumed the app writes log files and that yfinance's cache grows without bound. Checked against the code on 2026-10-26:

- The app logs only to standard error. Under systemd that goes to the journal, which caps its own size. There are no app log files.
- The dry-run history is in memory and capped at 1,000 messages; it is never written to disk.
- yfinance only keeps a small timezone cache file.

**Remaining risk:** the journal's default size cap on a small SD card. That is a system setting, covered as a deployment note.

### 4. Stock Price Fetch Blocks the Display for 5 Seconds — Likelihood: High | Impact: Medium

It's the first week. The user creates a text with `{{symbol:AAPL}}` and `{{symbol:TSLA}}`. The Pi is behind a captive portal with no internet. Each symbol fetch waits the full 5-second timeout in `_fetch_price`. The message has 2 symbols, so `_build_message` blocks for 10 seconds. The display visibly freezes for 10 seconds between messages. The `_FETCH_TIMEOUT` is per-symbol, not per-message, and there's no circuit breaker that says "internet is down, stop trying."

**Root cause:** template rendering is synchronous inside `_build_message`, which runs in the dispatcher's hot loop. The 5-second timeout per symbol is applied independently.

**Consequence chain:**
- 1st order: Display stutters for 10+ seconds per rotation
- 2nd order: User removes the symbols, defeating the feature's purpose
- 3rd order: User never uses templating again

### 5. Captive Portal Creates a DNS Black Hole — Checked: ruled out

The original narrative assumed the catch-all DNS rule also applies to the Pi's own lookups. It does not. The rule is written to `dnsmasq-shared.d`, which only the DNS server NetworkManager starts for the hotspot reads, and that server answers only the WiFi clients. The Pi resolves names through its normal resolver, so stock prices still resolve over ethernet.

### 6. Clock Lost on Every Power Cut — Likelihood: High | Impact: Medium

It's the first event. The Pi has no real-time clock. Someone sets the time on the Configuration page at 10:00, and the display shows `{{time}}` correctly. At 10:40 the plug is pulled to move the stand. Raspberry Pi OS restores the clock at boot from a file it saves hourly and at clean shutdown, so after the restart the clock reads about 09:00. The display now shows a time that is wrong by over an hour, and nobody notices because it looks plausible.

**Root cause:** there is no real-time clock, power cuts are the normal way the device is switched off, and setting the time by hand does not update the restore file.

**Consequence chain:**
- 1st order: `{{date}}` and `{{time}}` show a wrong but plausible value after every power cut
- 2nd order: Visitors read a wrong time off the sign
- 3rd order: Time-based templates get abandoned as unreliable

## Early Warning Signs

| Signal | Failure It Predicts | How to Check |
|--------|---------------------|--------------|
| Log line saying the display has not asked for a message for 5 minutes | Display off, unplugged, or SPI stuck (#2) | `journalctl -u lichtkrant` |
| Dispatcher reported as stopped | Dispatcher thread has died (#2) | Status banner in the web UI |
| `SYMBOL:N/A` on display despite internet | Price fetches failing (#4) | Status endpoint shows when each price was last fetched |
| Database restored or reset | Damage on power loss (#1) | Status banner in the web UI |
| `--:--` on the display | Unconfirmed clock after a boot (#6) | Open the web UI from a phone |

## Mitigations

Decided on 2026-10-26 in a design interview. Power cuts are treated as the normal way the device is switched off.

| # | Failure | Mitigation |
|---|---------|------------|
| 1 | DB damage on power loss | SQLite in full-sync mode. A backup copy is refreshed after each change. At startup an integrity check runs: a damaged database is set aside and restored from the backup, or the app starts empty if the backup is bad too. A banner reports either outcome until dismissed |
| 2 | Silent dispatcher death | On an unexpected error, log, skip the entry, back off up to 30 seconds and continue. A guard restarts the thread if it dies anyway. A status endpoint reports dispatcher state, last send and last error; a banner shows when the dispatcher has stopped. Waiting more than 5 minutes for the display to ask for a message is logged, nothing more, since the Pi cannot push a message the display does not ask for |
| 3 | Disk full | Deployment note in the README: cap the journal size |
| 4 | Symbol fetch blocking display | A background job fetches prices for every symbol in the queue; the dispatcher only reads the cache. `N/A` until the first fetch, then the last known price, however old |
| 5 | DNS black hole | None needed |
| 6 | Clock lost on power cut | After a boot the clock is unconfirmed, and `{{time}}`/`{{date}}` show `--:--` and `-- --- ----`. The first phone opening the web UI sets the clock automatically, with a banner. An internet time sync also confirms it. Every set time is written to the restore file at once |

Out of scope: a read-only root filesystem, the strongest OS-level protection against plug-pull damage. The README recommends it in a "Running unattended" section.

## Inversion Check

**What would guarantee this fails in the field?**
1. Unattended Pi with unreliable power and no recovery logic
2. No monitoring or health indication — failures are invisible until someone looks at the sign
3. Network-dependent features (stock prices) in the hot path with no fallback
4. A clock that silently resets on every power cut

**Do any of these exist now?** Yes, all four, as of 2026-10-26. The mitigations above address each one.
