# day_trading_bot/telegram_alerts.py

"""
Robust Telegram notifier:
- Reads TELEGRAM_* from config.py, with env-var fallbacks
- Handles DNS failures and queues messages to logs/telegram_queue.jsonl
- Retries on HTTP errors
- No hard dependency on pandas
"""

from __future__ import annotations

import os
import json
import socket
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Load config safely (no crash if names are missing) ---
try:
    from day_trading_bot import config as _cfg
except Exception:
    _cfg = None  # fallback to env only

def _cfg_get(name: str, default: Any = None) -> Any:
    # env wins first (lets you override without editing code)
    env = os.getenv(name)
    if env is not None:
        # cast CHAT_ID to int if possible
        if name == "TELEGRAM_CHAT_ID":
            try:
                return int(env)
            except Exception:
                return env
        return env
    # then from config module (if present)
    if _cfg is not None and hasattr(_cfg, name):
        return getattr(_cfg, name)
    return default

TELEGRAM_ENABLED = bool(_cfg_get("TELEGRAM_ENABLED", True))
TELEGRAM_BOT_TOKEN = (_cfg_get("TELEGRAM_BOT_TOKEN", "") or "").strip()
TELEGRAM_CHAT_ID = _cfg_get("TELEGRAM_CHAT_ID", 0)
TELEGRAM_PROXY = _cfg_get("TELEGRAM_PROXY", None) or None
TELEGRAM_TIMEOUT = int(_cfg_get("TELEGRAM_TIMEOUT", 10) or 10)

QUEUE_FILE = os.path.join("logs", "telegram_queue.jsonl")


# --- Helpers ---
def _ensure_logs_dir():
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)

def _dns_ok(host: str = "api.telegram.org") -> bool:
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError as e:
        print(f"[TELEGRAM] DNS resolve failed for {host}: {e}")
        return False

def _validate_config() -> Optional[str]:
    if not TELEGRAM_ENABLED:
        return "Telegram disabled in config."
    if not TELEGRAM_BOT_TOKEN or "your_token" in TELEGRAM_BOT_TOKEN.lower():
        return "Set TELEGRAM_BOT_TOKEN in config.py or env."
    if not TELEGRAM_CHAT_ID or str(TELEGRAM_CHAT_ID).strip() in {"", "your_chat_id", "0"}:
        return "Set TELEGRAM_CHAT_ID in config.py or env."
    return None

def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    if TELEGRAM_PROXY:
        s.proxies = {"http": TELEGRAM_PROXY, "https": TELEGRAM_PROXY}
    return s

def _enqueue(payload: Dict[str, Any]):
    _ensure_logs_dir()
    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "payload": payload}) + "\n")
    print("[TELEGRAM] Queued message locally (offline).")

def flush_queue():
    """Try to resend any queued messages. Safe to call at startup/shutdown."""
    if not os.path.exists(QUEUE_FILE):
        return
    if _validate_config() or not _dns_ok():
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    s = _session()

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    kept = []
    for line in lines:
        try:
            item = json.loads(line)
            resp = s.post(url, data=item["payload"], timeout=TELEGRAM_TIMEOUT)
            if resp.status_code != 200:
                kept.append(line)
        except Exception:
            kept.append(line)

    if kept:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            f.writelines(kept)
    else:
        try:
            os.remove(QUEUE_FILE)
        except OSError:
            pass


# --- Public API ---
def send_telegram_message(message: str) -> bool:
    """
    Send a plain text Telegram message.
    Returns True if delivered online, False if queued/offline or disabled.
    """
    err = _validate_config()
    if err:
        print(f"[TELEGRAM] {err}")
        return False

    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}

    if not _dns_ok():
        _enqueue(payload)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        s = _session()
        resp = s.post(url, data=payload, timeout=TELEGRAM_TIMEOUT)
        if resp.status_code == 200:
            print("[TELEGRAM] Sent.")
            return True
        print(f"[TELEGRAM] HTTP {resp.status_code}: {resp.text[:200]}")
        _enqueue(payload)
        return False
    except requests.exceptions.RequestException as e:
        print(f"[TELEGRAM] Network error: {e}")
        _enqueue(payload)
        return False


def send_trade_summary_via_telegram(df) -> None:
    """
    Send a session summary. `df` can be a pandas DataFrame or any
    object with dict-like column access.
    Expected columns: symbol, direction and either 'profit' or (take_profit & entry_price).
    """
    try:
        is_empty = getattr(df, "empty", None)
        if is_empty is True:
            send_telegram_message("No trades executed in this session.")
            return
    except Exception:
        pass  # keep going

    # Defensive copies and lookups
    try:
        rows = len(df)
    except Exception:
        rows = 0

    if rows == 0:
        send_telegram_message("No trades executed in this session.")
        return

    # Calculate 'result' column without importing pandas here
    def col(name, default=None):
        try:
            return df[name]
        except Exception:
            return default

    profit_col = col("profit")
    if profit_col is None:
        entry = col("entry_price", [])
        tp    = col("take_profit", [])
        try:
            result = [float(t) - float(e) for t, e in zip(tp, entry)]
        except Exception:
            result = []
    else:
        result = profit_col

    try:
        wins = sum(1 for r in result if r > 0)
        total = rows
        losses = total - wins
        net_profit = float(sum(result))
        avg_profit = float(net_profit / total) if total else 0.0

        # find best/worst by result
        best_idx = max(range(len(result)), key=lambda i: result[i])
        worst_idx = min(range(len(result)), key=lambda i: result[i])

        def at(idx, key, default=""):
            try:
                return df[key][idx]
            except Exception:
                try:
                    return df.iloc[idx][key]  # if it's a DataFrame
                except Exception:
                    return default

        best = {"symbol": at(best_idx, "symbol"),
                "direction": at(best_idx, "direction"),
                "result": float(result[best_idx])}
        worst = {"symbol": at(worst_idx, "symbol"),
                 "direction": at(worst_idx, "direction"),
                 "result": float(result[worst_idx])}

        summary = (
            f"*Session Trade Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})*\n\n"
            f"Total Trades: {total}\n"
            f"Wins: {wins}, Losses: {losses}\n"
            f"Net Profit: {net_profit:.2f}\n"
            f"Average P/L: {avg_profit:.2f}\n\n"
            f"*Best Trade:* {best['symbol']} ({best['direction']}) +{best['result']:.2f}\n"
            f"*Worst Trade:* {worst['symbol']} ({worst['direction']}) {worst['result']:.2f}\n"
        )
        send_telegram_message(summary)
    except Exception as e:
        send_telegram_message(f"*Session Trade Summary*\nError preparing summary: {e}")

def send_test_message():
    send_telegram_message("✅ Test message from your trading bot.")

__all__ = [
    "send_telegram_message",
    "send_trade_summary_via_telegram",
    "send_test_message",
    "flush_queue",
]
