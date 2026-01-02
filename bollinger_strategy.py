import MetaTrader5 as mt5
import pandas as pd
from day_trading_bot.utils.logger import print_debug
from day_trading_bot.utils.fetch_candles import fetch_candles


def bollinger_signal(df: pd.DataFrame) -> str | None:
    """Simple Bollinger Band strategy."""
    if df is None or len(df) < 20:
        print_debug("Skipping Bollinger: insufficient data.")
        return None

    df = df.copy()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['stddev'] = df['close'].rolling(window=20).std()

    df['upper_band'] = df['ma20'] + (2 * df['stddev'])
    df['lower_band'] = df['ma20'] - (2 * df['stddev'])

    last_close = df['close'].iloc[-1]
    if last_close > df['upper_band'].iloc[-1]:
        return 'SELL'
    elif last_close < df['lower_band'].iloc[-1]:
        return 'BUY'
    else:
        return None


def bollinger_signal_multi(symbol: str, timeframes: list[int]) -> str | None:
    """
    Consensus Bollinger direction across multiple TFs.
    Returns 'BUY'/'SELL' if all non-null signals align, else None.
    """
    directions: list[str] = []

    for tf in timeframes:
        df = fetch_candles(symbol, tf, 100)
        if df is None or df.empty:
            print_debug(f"{symbol} Bollinger: Insufficient data for TF {tf}")
            continue
        sig = bollinger_signal(df)
        if sig:
            directions.append(sig)

    if not directions:
        return None

    # require unanimity across the signals we managed to compute
    return directions[0] if all(d == directions[0] for d in directions) else None
