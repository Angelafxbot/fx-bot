# day_trading_bot/indicators.py

import pandas as pd

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute and append all common indicators:
      - SMA20, SMA50
      - RSI (14)
      - ATR (14)
    """
    df = df.copy()
    # Simple Moving Averages
    df["SMA20"] = df["close"].rolling(window=20).mean()
    df["SMA50"] = df["close"].rolling(window=50).mean()

    # RSI (14)
    df["RSI"] = _rsi(df["close"], period=14)

    # ATR (14)
    df["ATR_14"] = _atr(df, period=14)

    return df


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range: rolling mean of True Range over `period` bars.
    """
    high = df["high"]
    low  = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low  - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def rsi_signal(df: pd.DataFrame, lower: float = 30, upper: float = 70) -> str | None:
    """
    Simple RSI‐based overbought/oversold signal.
    Returns "BUY" if oversold, "SELL" if overbought, else None.
    """
    if df["RSI"].iloc[-1] < lower:
        return "BUY"
    if df["RSI"].iloc[-1] > upper:
        return "SELL"
    return None
