# day_trading_bot/reversal_signal.py

import numpy as np
import pandas as pd

from day_trading_bot.candle_patterns import (
    is_hammer,
    is_shooting_star,
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_doji,
    is_morning_star,
    is_evening_star,
    is_gravestone_doji,
    is_dragonfly_doji,
    is_tweezer_top,
    is_tweezer_bottom,
    is_bullish_harami,
    is_bearish_harami,
)
from day_trading_bot.utils.logger import print_debug
from day_trading_bot.utils.fetch_candles import fetch_candles
from day_trading_bot.support_resistance import find_nearest_levels, is_near_support_or_resistance

from MetaTrader5 import (
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_M30,
    TIMEFRAME_H1, TIMEFRAME_H2, TIMEFRAME_H4, TIMEFRAME_D1
)

# --- Reversal Patterns ---
patterns = [
    is_bullish_engulfing, is_bearish_engulfing, is_hammer, is_shooting_star,
    is_morning_star, is_evening_star, is_doji, is_gravestone_doji,
    is_dragonfly_doji, is_tweezer_top, is_tweezer_bottom,
    is_bullish_harami, is_bearish_harami,
]

TIMEFRAMES = {
    "M1":  TIMEFRAME_M1,
    "M5":  TIMEFRAME_M5,
    "M15": TIMEFRAME_M15,
    "M30": TIMEFRAME_M30,
    "H1":  TIMEFRAME_H1,
    "H2":  TIMEFRAME_H2,   # supported in recent MT5 builds; skip at runtime if broker lacks H2 data
    "H4":  TIMEFRAME_H4,
    "D1":  TIMEFRAME_D1,
}

TF_CANDLE_COUNTS = {
    "M1": 5000, "M5": 5000, "M15": 3000, "M30": 1500,
    "H1": 1500, "H2": 1500, "H4": 2000, "D1": 2000
}

REQUIRED_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H2", "H4", "D1"]

def _pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "XAU" in s:   return 0.1   # many brokers: 0.1 price units per pip
    if "JPY" in s:   return 0.01  # JPY pairs
    return 0.0001                 # majors/most FX

def recent_momentum_slope(df, window=200):
    if len(df) < window:
        return 0
    return df["close"].iloc[-1] - df["close"].iloc[-window]

def detect_reversal_signal(symbol, direction, fetch_candles_fn=fetch_candles):
    confirmed_timeframes = []
    pip = _pip_size(symbol)

    for label, tf in TIMEFRAMES.items():
        count = TF_CANDLE_COUNTS.get(label, 300)
        df_full = fetch_candles_fn(symbol, tf, count=count)
        if df_full is None or len(df_full) < TF_CANDLE_COUNTS[label]:
            print_debug(f"[{label}] {symbol}: insufficient data.")
            continue

        current_price = float(df_full["close"].iloc[-1])
        print_debug(f"[{label}] {symbol}: {len(df_full)} candles, price: {current_price:.5f}")

        df_recent = df_full.tail(TF_CANDLE_COUNTS[label])
        if df_recent.empty or len(df_recent) < 5:
            continue

        # Basic chop/vol filters
        directions = np.sign(df_recent["close"] - df_recent["open"])
        body_sizes = (df_recent["close"] - df_recent["open"]).abs()
        avg_body = float(body_sizes.mean())
        if np.sum(directions) <= 2 and body_sizes.std() < avg_body * 0.5:
            print_debug(f"[{label}] {symbol}: choppy market, skipping")
            continue

        # Pattern + zone context
        pattern_match = any(bool(p(df_recent)) for p in patterns)

        supports, resistances = find_nearest_levels(df_full, window=20, lookback=500, max_levels=3)

        # Use a symbol-aware proximity threshold (≈20 pips for FX, ≈2.0 for XAU, ≈20 pips JPY=0.20)
        sr_threshold = 20 * pip
        near_zone = is_near_support_or_resistance(current_price, supports, resistances, threshold=sr_threshold)

        # Breakout must clear S/R by a small buffer
        breakout_buffer = max(10 * pip, 0.001 * current_price)  # safe min for high-priced symbols
        broke_level = False
        if direction == "BUY" and resistances and current_price > max(resistances) + breakout_buffer:
            broke_level = True
        if direction == "SELL" and supports and current_price < min(supports) - breakout_buffer:
            broke_level = True

        if near_zone and not broke_level:
            print_debug(f"[{label}] {symbol} near S/R but not broken for {direction}. Skipping.")
            continue

        # Momentum fade + candle bias
        slope_recent = df_full["close"].iloc[-1] - df_full["close"].iloc[-5]
        slope_previous = df_full["close"].iloc[-5] - df_full["close"].iloc[-10]
        momentum_fading = abs(slope_recent) < abs(slope_previous)
        reversing_candles = np.sum(directions == (-1 if direction == "BUY" else 1))

        if pattern_match or (momentum_fading and reversing_candles >= 2):
            confirmed_timeframes.append(label)
            print_debug(f"[{label}] {symbol} reversal CONFIRMED")
        else:
            print_debug(f"[{label}] {symbol} reversal REJECTED")

    if len(confirmed_timeframes) >= 4:
        print_debug(f"[FINAL] {symbol} reversal {direction} CONFIRMED with {len(confirmed_timeframes)} TFs")
        return True
    print_debug(f"[FINAL] {symbol} reversal {direction} REJECTED – only {len(confirmed_timeframes)} TFs")
    return False
