import MetaTrader5 as mt5
import pandas as pd

def momentum_signal(df):
    """Generates momentum-based signal from a single timeframe."""
    if df is None or df.empty:
        return None

    recent_close = df['close'].iloc[-1]
    previous_close = df['close'].iloc[-2]

    if recent_close > previous_close:
        return 'BUY'
    elif recent_close < previous_close:
        return 'SELL'
    else:
        return None

def momentum_signal_multi(symbol, timeframes):
    """
    Confirms momentum direction across all specified timeframes.
    Returns common direction if consistent across all, else None.
    """
    directions = []

    for tf in timeframes:
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, 5)
        if rates is None or len(rates) < 2:
            continue

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        signal = momentum_signal(df)
        if signal:
            directions.append(signal)

    if not directions:
        return None

    if all(d == directions[0] for d in directions):
        return directions[0]
    return None
