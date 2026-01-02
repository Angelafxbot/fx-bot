import pandas as pd

# --- Single-candle patterns ---

def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    return (
        prev['close'] < prev['open'] and
        curr['close'] > curr['open'] and
        curr['open'] < prev['close'] and
        curr['close'] > prev['open']
    )

def is_bearish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    return (
        prev['close'] > prev['open'] and
        curr['close'] < curr['open'] and
        curr['open'] > prev['close'] and
        curr['close'] < prev['open']
    )

def is_hammer(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    c = df.iloc[-1]
    body = abs(c['close'] - c['open'])
    lower_wick = min(c['close'], c['open']) - c['low']
    return lower_wick > 2 * body

def is_shooting_star(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    c = df.iloc[-1]
    body = abs(c['close'] - c['open'])
    upper_wick = c['high'] - max(c['close'], c['open'])
    return upper_wick > 2 * body

def is_doji(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    c = df.iloc[-1]
    return abs(c['close'] - c['open']) < 0.1 * (c['high'] - c['low'])

# --- Multi-candle patterns ---

def is_morning_star(df: pd.DataFrame) -> bool:
    if len(df) < 3:
        return False
    a, b, c = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        a['close'] < a['open'] and
        abs(b['close'] - b['open']) < 0.2 * (b['high'] - b['low']) and
        c['close'] > c['open'] and
        c['close'] > (a['open'] + a['close']) / 2
    )

def is_evening_star(df: pd.DataFrame) -> bool:
    if len(df) < 3:
        return False
    a, b, c = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        a['close'] > a['open'] and
        abs(b['close'] - b['open']) < 0.2 * (b['high'] - b['low']) and
        c['close'] < c['open'] and
        c['close'] < (a['open'] + a['close']) / 2
    )

def is_gravestone_doji(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    c = df.iloc[-1]
    body = abs(c['open'] - c['close'])
    return (
        body < 0.1 * (c['high'] - c['low']) and
        (c['high'] - max(c['open'], c['close'])) > 2 * body
    )

def is_dragonfly_doji(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    c = df.iloc[-1]
    body = abs(c['open'] - c['close'])
    return (
        body < 0.1 * (c['high'] - c['low']) and
        (min(c['open'], c['close']) - c['low']) > 2 * body
    )

def is_tweezer_top(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    a, b = df.iloc[-2], df.iloc[-1]
    return (
        abs(a['high'] - b['high']) < 1e-5 and
        a['close'] > a['open'] and
        b['close'] < b['open']
    )

def is_tweezer_bottom(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    a, b = df.iloc[-2], df.iloc[-1]
    return (
        abs(a['low'] - b['low']) < 1e-5 and
        a['close'] < a['open'] and
        b['close'] > b['open']
    )

def is_bullish_harami(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    a, b = df.iloc[-2], df.iloc[-1]
    return (
        a['close'] < a['open'] and
        b['close'] > b['open'] and
        b['open'] > a['close'] and
        b['close'] < a['open']
    )

def is_bearish_harami(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    a, b = df.iloc[-2], df.iloc[-1]
    return (
        a['close'] > a['open'] and
        b['close'] < b['open'] and
        b['open'] < a['close'] and
        b['close'] > a['open']
    )

# ------------------------------------------------------------------
# Centralized pattern lists
# ------------------------------------------------------------------

# Patterns to use for BUY confirmations
BUY_PATTERNS = [
    is_bullish_engulfing,
    is_hammer,
    is_dragonfly_doji,
    is_tweezer_bottom,
    is_bullish_harami,
    is_morning_star,
]

# Patterns to use for SELL confirmations
SELL_PATTERNS = [
    is_bearish_engulfing,
    is_shooting_star,
    is_gravestone_doji,
    is_tweezer_top,
    is_bearish_harami,
    is_evening_star,
]

# Neutral/indecision patterns (not counted toward BUY/SELL)
NEUTRAL_PATTERNS = [
    is_doji,
]

# All patterns (for reversal_signal or other bulk checks)
ALL_PATTERNS = BUY_PATTERNS + SELL_PATTERNS + NEUTRAL_PATTERNS
