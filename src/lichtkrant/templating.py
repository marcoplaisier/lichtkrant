"""Template engine for resolving variables in display text.

Supported templates:
    {{date}}            — current local date (e.g. "25 Mar 2026")
    {{time}}            — current local time (e.g. "14:30")
    {{symbol:AAPL}}     — stock price from Yahoo Finance
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime

logger = logging.getLogger(__name__)

TEMPLATE_RE = re.compile(r"\{\{(\w+(?::\w+)?)\}\}")

# Cache stock prices to avoid hammering Yahoo Finance on every display cycle
_symbol_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300.0  # 5 minutes
_NEGATIVE_CACHE_TTL = 60.0  # 1 minute for failed fetches

_executor = ThreadPoolExecutor(max_workers=1)
_FETCH_TIMEOUT = 5.0  # seconds


def _do_fetch(symbol: str) -> str | None:
    """Fetch the current price for a stock symbol via yfinance."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.get_fast_info()
        price = info.get("lastPrice") or info.get("last_price")
        if price is not None:
            return f"{price:.2f}"
    except Exception:
        logger.warning("Failed to fetch price for %s", symbol, exc_info=True)
    return None


def _fetch_price(symbol: str) -> str | None:
    """Fetch price with a timeout to avoid blocking the dispatcher."""
    try:
        future = _executor.submit(_do_fetch, symbol)
        return future.result(timeout=_FETCH_TIMEOUT)
    except TimeoutError:
        logger.warning("Timeout fetching price for %s", symbol)
        return None
    except Exception:
        logger.warning("Error fetching price for %s", symbol, exc_info=True)
        return None


def _get_symbol_value(symbol: str) -> str:
    """Get a cached or fresh stock price for a symbol."""
    now = time.monotonic()
    with _cache_lock:
        if symbol in _symbol_cache:
            value, fetched_at = _symbol_cache[symbol]
            if now - fetched_at < _CACHE_TTL:
                return value

    price = _fetch_price(symbol)
    if price is None:
        result = f"{symbol}:N/A"
        with _cache_lock:
            _symbol_cache[symbol] = (result, now)
        return result

    result = f"{symbol} {price}"
    with _cache_lock:
        _symbol_cache[symbol] = (result, now)
    return result


def _resolve_var(name: str) -> str:
    """Resolve a single template variable."""
    if name == "date":
        return datetime.now().strftime("%d %b %Y")
    if name == "time":
        return datetime.now().strftime("%H:%M")
    if name.startswith("symbol:"):
        symbol = name[7:].upper()
        if symbol:
            return _get_symbol_value(symbol)
    # Unknown variable — pass through unchanged
    return "{{" + name + "}}"


def render(text: str) -> str:
    """Replace all {{var}} placeholders in text with their values."""
    if "{{" not in text:
        return text
    return TEMPLATE_RE.sub(lambda m: _resolve_var(m.group(1)), text)


def has_templates(text: str) -> bool:
    """Check if text contains any template variables."""
    return bool(TEMPLATE_RE.search(text))
