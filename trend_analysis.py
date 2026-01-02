# trend_analysis.py

import pandas as pd


def detect_trend(df, short_window=14, long_window=50):
    """
    Detects major trend direction based on EMA crossover.

    Args:
        df (pd.DataFrame): DataFrame with 'close' prices.
        short_window (int): Short-term EMA window (default 14).
        long_window (int): Long-term EMA window (default 50).

    Returns:
        str: 'uptrend', 'downtrend', or 'sideways'
    """
    if df is None or df.empty or 'close' not in df.columns:
        return "sideways"

    ema_short = df['close'].ewm(span=short_window, adjust=False).mean()
    ema_long = df['close'].ewm(span=long_window, adjust=False).mean()

    if ema_short.iloc[-1] > ema_long.iloc[-1]:
        return "uptrend"
    elif ema_short.iloc[-1] < ema_long.iloc[-1]:
        return "downtrend"
    else:
        return "sideways"
