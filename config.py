# config.py
import os

# ─────────────────────────────────────────────────────────────────────────────
# General Settings
# ─────────────────────────────────────────────────────────────────────────────
TRADING_SYMBOLS = [
    "GBPJPY", "EURJPY", "USDJPY",
    "GBPUSD", "EURAUD", "XAUUSD", "EURUSD"
]

# ✅ Supported MT5 timeframes
from MetaTrader5 import (
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15,
    TIMEFRAME_M30, TIMEFRAME_H1, TIMEFRAME_H2, TIMEFRAME_H4, TIMEFRAME_D1
)

TIMEFRAMES = {
    "M1":  TIMEFRAME_M1,
    "M5":  TIMEFRAME_M5,
    "M15": TIMEFRAME_M15,
    "M30": TIMEFRAME_M30,
    "H1":  TIMEFRAME_H1,
    "H2":  TIMEFRAME_H2,
    "H4":  TIMEFRAME_H4,
    "D1":  TIMEFRAME_D1
}

# bars to fetch per TF
CANDLE_COUNTS = {
    "M1":  5000,
    "M5":  4000,
    "M15": 3000,
    "M30": 3000,
    "H1":  1500,
    "H2":  1500,
    "H4":  2000,
    "D1":  2000
}

CANDLE_COUNT = 500   # fallback if not found in CANDLE_COUNTS
MAX_SPREAD   = 30    # in points

# ─────────────────────────────────────────────────────────────────────────────
# Strategy Thresholds
# ─────────────────────────────────────────────────────────────────────────────
REVERSAL_REQUIRED_CONFIDENCE = 0.7
MOMENTUM_REQUIRED_STRENGTH   = 0.6
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30

# Reversal Confirmation Settings
REVERSAL_REQUIRED_TFS = ["M1", "M5", "M15", "M30", "H1", "H2", "H4", "D1"]

# ─────────────────────────────────────────────────────────────────────────────
# News / Session Filters
# ─────────────────────────────────────────────────────────────────────────────
ENABLE_NEWS_FILTER    = False
NEWS_IMPACT_THRESHOLD = "medium"  # or "high"

ENABLE_SESSION_FILTER = False
USE_SESSION_FILTER    = ENABLE_SESSION_FILTER

# ─────────────────────────────────────────────────────────────────────────────
# Telegram Alerts
# ─────────────────────────────────────────────────────────────────────────────
TELEGRAM_ENABLED         = True
ENABLE_TELEGRAM_ALERTS   = True
TELEGRAM_BOT_TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN", "8283395407:AAF6D0n7iroYpXYuUqMdSn9tBtqaXCov3ZM")
TELEGRAM_CHAT_ID         = os.getenv("TELEGRAM_CHAT_ID", "@angelafxbot")

# ─────────────────────────────────────────────────────────────────────────────
# Updater / Versioning (silent by default)
# ─────────────────────────────────────────────────────────────────────────────
BOT_VERSION          = "1.0.0"
UPDATE_JSON_URL      = "https://your-server.com/update.json"
UPDATE_CHECK_ENABLED = False
UPDATE_CHECK_URL     = ""                     # set real URL when ready
UPDATE_POLL_SECONDS  = 6 * 3600
EXE_NAME             = "ForexBotLauncher.exe"

# ─────────────────────────────────────────────────────────────────────────────
# Trade Log / Risk / Loop
# ─────────────────────────────────────────────────────────────────────────────
TRADE_LOG_FILE   = "trade_log.csv"
RISK_PERCENT     = 1            # max 1% risk per trade
CHECK_INTERVAL   = 60           # in seconds
ENABLE_DEBUG_LOGGING = True

# Mode Toggles
AUTO_MODE             = False
FURY_MODE             = False
FURY_TRADE_HOUR_START = 9   # UTC
FURY_TRADE_HOUR_END   = 15  # UTC

# Aliases for consistency
USE_REVERSAL_FILTER  = True
CONFIDENCE_THRESHOLD = REVERSAL_REQUIRED_CONFIDENCE

# ─────────────────────────────────────────────────────────────────────────────
# Platform routing
# ─────────────────────────────────────────────────────────────────────────────
# Choose: "MT5" (default) or "MT4"
TRADING_PLATFORM = "MT5"
# MT4_COMMON_FILES_DIR = r"C:\Users\YOU\AppData\Roaming\MetaQuotes\Terminal\Common\Files"

# ─────────────────────────────────────────────────────────────────────────────
# Router (Regime + Breakout) tuning  — BEST SETUP
# Regime on H1, breakout on M5. Breakout enforced only in trend.
# Plus M15 follow-through confirmation (within a short window).
# ─────────────────────────────────────────────────────────────────────────────
ROUTER_REGIME_TF      = "H1"    # stable regime detection
ROUTER_BREAKOUT_TF    = "M5"    # breakout detection (fast but reliable with buffer)
ROUTER_DONCHIAN_N     = 14
ROUTER_ATR_K_DEFAULT  = 0.06    # majors buffer
ROUTER_ATR_K_VOLATILE = 0.12    # GBPJPY, XAUUSD, indices
ROUTER_REQUIRE_CLOSE  = True    # use previous candle close for confirmation
ROUTER_HYSTERESIS_N   = 2
VOLATILE_SYMBOLS      = {"GBPJPY", "XAUUSD", "US30", "NAS100"}

# Compulsory breakout only when trading WITH the trend (BUY in uptrend / SELL in downtrend).
REQUIRE_BREAKOUT_IN_TREND = True

# Follow-through confirmation (after M5 breakout, look for holding on M15)
BREAKOUT_CONFIRM_ENABLED = True
BREAKOUT_CONFIRM_TF      = "M15"
BREAKOUT_CONFIRM_BARS    = 3      # confirm within last N closed bars
BREAKOUT_CONFIRM_K_MULT  = 0.5    # allow half the buffer on confirm TF
