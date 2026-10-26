"""Read and set the system clock.

The Pi usually runs standalone without internet, so NTP cannot set the clock.
This module lets the web UI set it by hand. Setting the clock requires root
(or ``CAP_SYS_TIME``), which the systemd service already has.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_YEAR = 2000
MAX_YEAR = 2099

_RTC_DEVICE = Path("/dev/rtc0")


def parse_time(value: object) -> datetime:
    """Parse an ISO 8601 date-time string, e.g. ``2026-10-01T14:30:00``.

    A value without UTC offset is interpreted as local time of the Pi, so the
    display shows exactly the wall-clock time the user entered.

    Raises:
        ValueError: If the value is not a valid date-time in the accepted range.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("time must be an ISO 8601 date-time string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid date-time: {value}") from None
    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        raise ValueError(f"Year must be between {MIN_YEAR} and {MAX_YEAR}")
    return parsed


def get_time_info() -> dict[str, str]:
    """Return the current local time (ISO 8601, seconds) and timezone name."""
    now = datetime.now().astimezone()
    return {
        "time": now.replace(tzinfo=None).isoformat(timespec="seconds"),
        "timezone": now.tzname() or "",
    }


def _sync_hardware_clock() -> None:
    """Copy the system time to the hardware clock, if the Pi has one."""
    hwclock = shutil.which("hwclock")
    if not hwclock or not _RTC_DEVICE.exists():
        return
    try:
        subprocess.run([hwclock, "--systohc"], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not update hardware clock: %s", exc)


def set_system_time(new_time: datetime) -> None:
    """Set the system clock.

    Raises:
        PermissionError: If the process is not allowed to set the clock.
        OSError: If the clock could not be set for another reason.
    """
    time.clock_settime(time.CLOCK_REALTIME, new_time.timestamp())
    logger.info("System time set to %s", new_time.isoformat(timespec="seconds"))
    _sync_hardware_clock()
