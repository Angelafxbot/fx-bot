# day_trading_bot/main.py

import sys, os, time
from datetime import datetime
import signal
import traceback

# ── Windows console UTF-8 safeguard (prevents charmap encode errors) ─────────
try:
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ─── Paths & crash logging ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
LOG_FILE = os.path.join(BASE_DIR, "forex_bot_log.txt")
STOP_FLAG = os.path.join(BASE_DIR, "BOT_STOP.flag")


def _log_unhandled(exc_type, exc, tb):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {exc_type.__name__}: {exc}\n")
            traceback.print_tb(tb, file=f)
    except Exception:
        pass
    try:
        traceback.print_exception(exc_type, exc, tb)
    except Exception:
        pass


sys.excepthook = _log_unhandled

# Log boot only if executed directly
if __name__ == "__main__":
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Booting main.py\n")
    except Exception:
        pass

# ─── Project path ────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ─── Dev-only site-packages (so local venv works in PyCharm) ─────────────────
if not getattr(sys, "frozen", False):
    try:
        import site
        venv_sp = os.path.join(os.path.dirname(__file__), '..', 'venv_clean', 'Lib', 'site-packages')
        if os.path.isdir(venv_sp):
            site.addsitedir(venv_sp)
    except Exception:
        pass

# ─── Third-party imports ─────────────────────────────────────────────────────
import MetaTrader5 as mt5
import pandas as pd

# ─── Internal imports ────────────────────────────────────────────────────────
from day_trading_bot.utils.logger import print_debug
from day_trading_bot.config import (
    TRADING_SYMBOLS, TIMEFRAMES, CANDLE_COUNT, CHECK_INTERVAL,
    USE_REVERSAL_FILTER, CONFIDENCE_THRESHOLD, AUTO_MODE,
    FURY_MODE, FURY_TRADE_HOUR_START, FURY_TRADE_HOUR_END,
    RISK_PERCENT, CANDLE_COUNTS
)
from day_trading_bot.execution import place_trade
from day_trading_bot.utils.account import get_balance
from day_trading_bot.risk import calculate_risk_lot_size
from day_trading_bot.reversal_signal import detect_reversal_signal
from day_trading_bot.indicators import calculate_indicators, rsi_signal
from day_trading_bot.momentum_strategy import momentum_signal
from day_trading_bot.bollinger_strategy import bollinger_signal
from day_trading_bot.support_resistance import find_recent_support_resistance
from day_trading_bot.utils.fetch_candles import ensure_data
from day_trading_bot.trend_analysis import detect_trend
from day_trading_bot.candle_patterns import BUY_PATTERNS, SELL_PATTERNS
from day_trading_bot.pattern_detector import detect_pattern
from day_trading_bot.telegram_alerts import send_telegram_message
from day_trading_bot.trade_manager import manage_open_trades
from day_trading_bot.supply_demand import find_zones_fallback
# --- Auto update checker (notify channel + optional replace) ---
import threading, random

def _periodic_update_checker():
    try:
        from day_trading_bot import updater
    except Exception:
        return  # skip silently if updater not bundled in exe

    while True:
        try:
            updater.main()  # broadcasts + (optionally) replaces exe per your updater.py
        except Exception as e:
            print(f"[UPDATER] error: {e}")
        # jittered 6h to avoid all users hitting at once
        time.sleep(6*3600 + random.randint(0, 900))

threading.Thread(target=_periodic_update_checker, daemon=True).start()

# Helpful breadcrumb so we can confirm both processes look at the same flag
print_debug(f"[DEBUG] main STOP_FLAG path: {STOP_FLAG}")

# ─── Graceful shutdown ───────────────────────────────────────────────────────
def handle_exit(sig, frame):
    try:
        print_debug("[EXIT] Bot received termination signal.")
    except Exception:
        pass
    try:
        if os.path.exists(STOP_FLAG):
            os.remove(STOP_FLAG)
    except Exception:
        pass
    try:
        mt5.shutdown()
    finally:
        os._exit(0)  # hard exit to ensure EXE stops


signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# ─── CLI args (supports launcher --bot SYMBOLS TF RISK AUTO) ─────────────────
if len(sys.argv) >= 5:
    ACTIVE_SYMBOLS = sys.argv[1].split(",")
    timeframe = sys.argv[2]
    RISK_PERCENT = float(sys.argv[3])
    AUTO_MODE = sys.argv[4] == "1"

    if timeframe not in TIMEFRAMES:
        print_debug(f"[ERROR] Invalid timeframe: {timeframe}")
        sys.exit(1)
else:
    ACTIVE_SYMBOLS = list(TRADING_SYMBOLS)  # default: use ALL configured symbols
    timeframe = "M15"

# ─── Lookbacks ───────────────────────────────────────────────────────────────
CANDLE_PATTERN_LOOKBACK = 3
CHART_PATTERN_LOOKBACK = 40


def detect_candlestick_pattern(df: pd.DataFrame, direction: str) -> bool:
    if direction == "BUY":
        return any(p(df) for p in BUY_PATTERNS)
    if direction == "SELL":
        return any(p(df) for p in SELL_PATTERNS)
    return False


def has_open_position(symbol: str) -> bool:
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0


def is_within_fury_window() -> bool:
    now_hour = datetime.utcnow().hour
    return not FURY_MODE or FURY_TRADE_HOUR_START <= now_hour < FURY_TRADE_HOUR_END


def is_respecting_trendline(df: pd.DataFrame, direction: str) -> bool:
    if len(df) < 10:
        return False
    lows = df['low'].rolling(window=5).min()
    highs = df['high'].rolling(window=5).max()
    if direction == "BUY":
        return df['close'].iloc[-1] > lows.iloc[-5]
    if direction == "SELL":
        return df['close'].iloc[-1] < highs.iloc[-5]
    return False


def get_trade_decision(symbol: str):
    print_debug(f"[PROCESSING] Checking {symbol}")

    df_m5  = ensure_data(symbol, TIMEFRAMES["M5"],  count=CANDLE_COUNTS.get("M5", CANDLE_COUNT))
    df_m15 = ensure_data(symbol, TIMEFRAMES["M15"], count=CANDLE_COUNTS.get("M15", CANDLE_COUNT))
    df_m30 = ensure_data(symbol, TIMEFRAMES["M30"], count=CANDLE_COUNTS.get("M30", CANDLE_COUNT))
    df_h1  = ensure_data(symbol, TIMEFRAMES["H1"],  count=CANDLE_COUNTS.get("H1", CANDLE_COUNT))
    df_h2  = ensure_data(symbol, TIMEFRAMES["H2"],  count=CANDLE_COUNTS.get("H2", CANDLE_COUNT))
    df_h4  = ensure_data(symbol, TIMEFRAMES["H4"],  count=CANDLE_COUNTS.get("H4", CANDLE_COUNT))
    df_d1  = ensure_data(symbol, TIMEFRAMES["D1"],  count=CANDLE_COUNTS.get("D1", CANDLE_COUNT))

    timeframes = {"M5": df_m5, "M15": df_m15, "M30": df_m30, "H1": df_h1, "H2": df_h2, "H4": df_h4, "D1": df_d1}
    missing = [tf for tf, df in timeframes.items() if df is None]
    if missing:
        print_debug(f"[DATA] Missing candles for {symbol} on: {', '.join(missing)}")
        return None

    df_m5  = calculate_indicators(df_m5)
    df_m15 = calculate_indicators(df_m15)
    df_m30 = calculate_indicators(df_m30)
    df_h1  = calculate_indicators(df_h1)

    trend_dir     = detect_trend(df_m15)
    momentum_dir  = momentum_signal(df_m15)
    bollinger_dir = bollinger_signal(df_m15)

    try:
        rsi_dir = rsi_signal(df_m15)
    except Exception as e:
        print_debug(f"[ERROR] RSI failed for {symbol}: {e}")
        rsi_dir = None

    last_close = df_m5["close"].iloc[-1]
    support, resistance = find_recent_support_resistance(df_m5)
    near_zone = (
        abs(last_close - support) / last_close < 0.002 or
        abs(last_close - resistance) / last_close < 0.002
    )

    directions = [d for d in [momentum_dir, bollinger_dir, rsi_dir] if d]
    if not directions:
        print_debug(f"[REJECTED] {symbol}: No direction from indicators.")
        return None

    direction = max(set(directions), key=directions.count)

    # conflict with chart pattern?
    df_tf_chart = df_m15.tail(CHART_PATTERN_LOOKBACK)
    pat = detect_pattern(df_tf_chart, expected_direction=direction)
    if isinstance(pat, dict) and pat.get("direction") in ("BUY", "SELL") and pat["direction"] != direction:
        print_debug(f"[REJECTED] {symbol}: M15 pattern {pat['pattern']} conflicts with {direction}.")
        return None

    df_candles    = df_m15.tail(CANDLE_PATTERN_LOOKBACK)
    df_chart_m15  = df_m15.tail(CHART_PATTERN_LOOKBACK)

    score = 0.0
    reasons = []
    weights = {
        "trend":               0.2,
        "momentum":            0.2,
        "rsi":                 0.1,
        "bollinger":           0.1,
        "support_resistance":  0.15,
        "candle":              0.15,
        "chart":               0.1,
        "trendline":           0.1,
    }

    if trend_dir == ("uptrend" if direction == "BUY" else "downtrend"):
        score += weights["trend"]; reasons.append(f"Trend={trend_dir}")
    if momentum_dir == direction:
        score += weights["momentum"]; reasons.append(f"Momentum={momentum_dir}")
    if rsi_dir == direction:
        score += weights["rsi"]; reasons.append(f"RSI={rsi_dir}")
    if bollinger_dir == direction:
        score += weights["bollinger"]; reasons.append(f"Bollinger={bollinger_dir}")
    if near_zone:
        score += weights["support_resistance"]; reasons.append("Near support/resistance")
    if is_respecting_trendline(df_m15, direction):
        score += weights["trendline"]; reasons.append("Respecting trendline")

    prev_candles = df_candles.iloc[:-1]
    if detect_candlestick_pattern(prev_candles, direction):
        last = df_candles.iloc[-1]
        if (direction == "BUY" and last['close'] > last['open']) or \
           (direction == "SELL" and last['close'] < last['open']):
            score += weights["candle"]; reasons.append("Candle pattern (confirmed)")

    chart_pattern = detect_pattern(df_chart_m15, expected_direction=direction)
    if isinstance(chart_pattern, dict) and chart_pattern.get("direction") == direction:
        score += weights["chart"]; reasons.append(f"Chart={chart_pattern.get('pattern', 'pattern')}")

    print_debug(f"[SCORE] {symbol} => Dir={direction}, Score={score:.2f}, Reasons={reasons}")

    if score < CONFIDENCE_THRESHOLD:
        print_debug(f"[SKIP] {symbol}: Below confidence threshold.")
        return None

    if USE_REVERSAL_FILTER and not detect_reversal_signal(symbol, direction):
        print_debug(f"[REJECTED] {symbol}: Reversal filter failed.")
        return None

    # Supply/Demand Zone Check — include M15 for dynamic padding
    df_dict = {"M15": df_m15, "M30": df_m30, "H1": df_h1, "H2": df_h2, "H4": df_h4, "D1": df_d1}
    zones_d, zones_s, tf_used = find_zones_fallback(df_dict, direction, last_close, symbol)

    if direction == "BUY" and not zones_d:
        print_debug(f"[REJECTED] {symbol}: Not in demand zone on any TF."); return None
    if direction == "SELL" and not zones_s:
        print_debug(f"[REJECTED] {symbol}: Not in supply zone on any TF."); return None

    # closest zone info (optional)
    all_zones = []
    if direction == "BUY":
        for tf_name, tf_df in df_dict.items():
            if tf_df is not None:
                dz, _, _ = find_zones_fallback({tf_name: tf_df}, direction, last_close, symbol)
                all_zones.extend(dz)
    else:
        for tf_name, tf_df in df_dict.items():
            if tf_df is not None:
                _, sz, _ = find_zones_fallback({tf_name: tf_df}, direction, last_close, symbol)
                all_zones.extend(sz)
    if all_zones:
        closest = min(all_zones, key=lambda z: abs((z[0] + z[1]) / 2 - last_close))
        print_debug(f"[INFO] Closest {direction.lower()} zone: {closest}, Distance: {abs((closest[0] + closest[1]) / 2 - last_close):.1f}")
    else:
        print_debug(f"[INFO] No {direction.lower()} zones found on any TF.")

    # zone reversal confirmation
    if not detect_candlestick_pattern(df_m15.tail(CANDLE_PATTERN_LOOKBACK), direction):
        print_debug(f"[REJECTED] {symbol}: In {direction} zone but no reversal pattern detected.")
        return None

    reasons.append(f"In {tf_used} {direction} zone")
    reasons.append("Reversal pattern confirmed in zone")

    return {
        "symbol":        symbol,
        "direction":     direction,
        "confidence":    round(score * 100, 2),
        "confirmations": int(score * 10),
        "df":            df_m5,
        "reasons":       reasons,
    }


def should_stop() -> bool:
    return os.path.exists(STOP_FLAG)

def resolve_symbol(base_symbol: str) -> str:
    """Finds the correct broker-specific symbol (with or without suffix)."""
    if mt5.symbol_select(base_symbol, True):
        return base_symbol
    for s in mt5.symbols_get():
        if s.name.startswith(base_symbol):
            mt5.symbol_select(s.name, True)
            return s.name
    raise Exception(f"Symbol {base_symbol} not found with any suffix")


def run_bot():
    if not mt5.initialize():
        print_debug(f"MT5 initialization failed: {mt5.last_error()}")
        return

    # Exit immediately if Stop was requested
    if should_stop():
        print_debug("[EXIT] Stop requested before run.")
        mt5.shutdown()
        return

    if not is_within_fury_window():
        print_debug("Outside allowed trading hours.")
        mt5.shutdown()
        return

    best_trade = None

    for sym in ACTIVE_SYMBOLS:
        try:
            # normalize base name and resolve broker-specific symbol
            sym = resolve_symbol(sym.replace("m", ""))
        except Exception as e:
            print_debug(f"[ERROR] Could not resolve symbol {sym}: {e}")
            continue

        # Allow stop mid-loop
        if should_stop():
            print_debug("[EXIT] Stop requested during symbol loop.")
            mt5.shutdown()
            return

        if has_open_position(sym):
            print_debug(f"[SKIP] {sym}: Already in trade.")
            continue

        try:
            decision = get_trade_decision(sym)
            if decision and (not best_trade or decision["confidence"] > best_trade["confidence"]):
                best_trade = decision
        except Exception as e:
            print_debug(f"[ERROR] {sym}: {e}")

    # Another quick stop check before actions
    if should_stop():
        print_debug("[EXIT] Stop requested before trade/management.")
        mt5.shutdown()
        return

    if best_trade:
        if not AUTO_MODE:
            from day_trading_bot.tk_interface import prompt_trade_decision
            approved = prompt_trade_decision(
                best_trade["symbol"], best_trade["direction"],
                best_trade["confidence"], best_trade["reasons"]
            )
            if not approved:
                print_debug("[BLOCKED] Trade not approved.")
                mt5.shutdown()
                return

        balance = get_balance()

        # final stop check before placing
        if should_stop():
            print_debug("[EXIT] Stop requested before placing trade.")
            mt5.shutdown()
            return

        placed = place_trade(best_trade["symbol"], best_trade["direction"], balance)
        if placed:
            send_telegram_message(
                f"✅ {best_trade['symbol']} {best_trade['direction']} @ {best_trade['confidence']}%\n" +
                "\n".join(best_trade["reasons"])
            )
    else:
        print_debug("No valid trade setup found.")

    # final stop check before management
    if should_stop():
        print_debug("[EXIT] Stop requested before manage_open_trades().")
        mt5.shutdown()
        return

    manage_open_trades()
    mt5.shutdown()


def _sleep_checking_stop(seconds: float):
    """Sleep in 1-second slices so GUI close/logout stops the bot promptly."""
    total = max(1, int(round(seconds)))
    for _ in range(total):
        if should_stop():
            break
        time.sleep(1)


def main_entry():
    """
    Bot service loop, callable from the launcher in --bot mode.
    """
    # If someone tries to run this via Streamlit, avoid infinite loop.
    if "streamlit" in os.path.basename(sys.argv[0]).lower():
        print_debug("[INFO] Skipping infinite loop in Streamlit context.")
        return

    while True:
        if os.path.exists(STOP_FLAG):
            print_debug("[EXIT] Stop flag detected. Shutting down.")
            mt5.shutdown()
            try:
                os.remove(STOP_FLAG)
            except Exception:
                pass
            os._exit(0)

        try:
            run_bot()
        except Exception as loop_err:
            print_debug(f"[CRITICAL] {loop_err}")

        # Sleep in short chunks so STOP_FLAG is honored immediately
        _sleep_checking_stop(CHECK_INTERVAL)


if __name__ == "__main__":
    # Running directly (not via launcher) still works
    main_entry()
