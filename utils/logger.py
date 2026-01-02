# utils/logger.py

import os
import csv
import io
import sys
import time
import threading
from datetime import datetime
from typing import Optional

# ---------- optional config toggles ----------
try:
    from day_trading_bot.config import ENABLE_DEBUG_LOGGING  # bool
except Exception:
    ENABLE_DEBUG_LOGGING = True  # fallback if config not imported

# You can tune this with an env var, e.g. LOG_DEDUP_WINDOW_SECONDS=2
_DEDUP_WINDOW = float(os.getenv("LOG_DEDUP_WINDOW_SECONDS", "2.0"))  # seconds

# ---------- paths & setup ----------

_LOG_LOCK = threading.Lock()

def _base_dir() -> str:
    """Where the app is running from (EXE dir when frozen; module dir in dev)."""
    if getattr(sys, "frozen", False):  # PyInstaller
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _first_writable_dir(candidates):
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, "._w")
            with open(test, "w", encoding="utf-8") as f:
                f.write("x")
            os.remove(test)
            return d
        except Exception:
            continue
    # last resort: current working directory
    os.makedirs("logs", exist_ok=True)
    return os.path.abspath("logs")

def _log_dir() -> str:
    exe_logs = os.path.join(_base_dir(), "logs")
    alt_root = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    alt_logs = os.path.join(alt_root, "ForexBot", "logs")
    tmp_logs = os.path.join(os.getenv("TMP", os.getenv("TEMP", "/tmp")), "ForexBot", "logs")
    return _first_writable_dir([exe_logs, alt_logs, tmp_logs])

_LOG_DIR = _log_dir()
_TRADE_LOG = os.path.join(_LOG_DIR, "trade_log.csv")
_DEBUG_LOG = os.path.join(_LOG_DIR, "debug_log.log")

_TRADE_HEADERS = ["timestamp", "symbol", "direction", "entry_price", "lot_size", "profit", "comment", "reason"]

# ---------- internal state for de-dup ----------
_LAST_LINE: Optional[str] = None
_LAST_TS: float = 0.0
_LAST_REPEAT: int = 0

def _emit_console(line: str) -> None:
    try:
        print(line, flush=True)
    except Exception:
        pass

def _emit_file(line: str) -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)
    with io.open(_DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

# ---------- public API ----------

def log_trade(symbol: str,
              direction: str,
              result: Optional[object],
              reason: str = "") -> str:
    """
    Append one trade to CSV (thread-safe, no pandas).
    Returns the path to the log file.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "timestamp": ts,
        "symbol": symbol,
        "direction": direction,
        "entry_price": getattr(result, "price_open", 0),
        "lot_size": getattr(result, "volume", 0),
        "profit": getattr(result, "profit", 0) if result is not None else 0,
        "comment": getattr(result, "comment", ""),
        "reason": reason or "",
    }

    with _LOG_LOCK:
        header_needed = not os.path.exists(_TRADE_LOG)
        # newline='' is important on Windows to avoid blank lines
        with open(_TRADE_LOG, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=_TRADE_HEADERS, extrasaction="ignore")
            if header_needed:
                w.writeheader()
            w.writerow(row)
    return _TRADE_LOG

def print_debug(message: str) -> str:
    """
    Print to console and append to debug log (thread-safe) with de-duplication:
      - If the same message repeats within _DEDUP_WINDOW seconds, suppress it.
      - When the next different message arrives, write a summary line indicating
        how many repeats were suppressed.
    Returns the path to the debug log file.
    """
    if not ENABLE_DEBUG_LOGGING:
        return _DEBUG_LOG

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    now = time.time()

    with _LOG_LOCK:
        global _LAST_LINE, _LAST_TS, _LAST_REPEAT

        # identical message within window? suppress
        if _LAST_LINE == message and (now - _LAST_TS) < _DEDUP_WINDOW:
            _LAST_REPEAT += 1
            # do not emit anything
            return _DEBUG_LOG

        # before emitting a new (different) message, flush a repeat summary if any
        if _LAST_REPEAT > 0:
            sum_line = f"[{ts}] [LOG] (previous line repeated {_LAST_REPEAT}x)"
            _emit_console(sum_line)
            _emit_file(sum_line)
            _LAST_REPEAT = 0

        # emit current message
        _emit_console(line)
        _emit_file(line)

        # update last-seen state
        _LAST_LINE = message
        _LAST_TS = now

    return _DEBUG_LOG

def get_log_paths() -> dict:
    """Useful for diagnostics or UI."""
    return {"dir": _LOG_DIR, "trade": _TRADE_LOG, "debug": _DEBUG_LOG}
