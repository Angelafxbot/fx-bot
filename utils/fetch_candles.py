# day_trading_bot/utils/fetch_candles.py

import MetaTrader5 as mt5
import pandas as pd
from day_trading_bot.utils.logger import print_debug
from day_trading_bot.config import CANDLE_COUNTS, TIMEFRAMES  # timeframe map and default counts


def _mt5_inited() -> bool:
    try:
        return mt5.terminal_info() is not None
    except Exception:
        return False


def initialize_mt5() -> bool:
    """Initialize MT5 terminal if not already running."""
    if _mt5_inited():
        return True
    if not mt5.initialize():
        error_code, error_msg = mt5.last_error()
        print_debug(f"[ERROR] Could not initialize MT5. code={error_code} msg={error_msg}")
        return False
    return True


def _resolve_symbol(base_symbol: str) -> str | None:
    """
    Ensure a broker-specific symbol is selected in MT5.
    Returns the resolved symbol name or None if not found.
    """
    # Try exact first
    if mt5.symbol_select(base_symbol, True):
        return base_symbol

    # Try broker variants (suffixes like m, .pro, .r)
    try:
        for s in mt5.symbols_get():
            if s.name.upper().startswith(base_symbol.upper()):
                if mt5.symbol_select(s.name, True):
                    return s.name
    except Exception as e:
        print_debug(f"[ERROR] symbols_get failed: {e}")

    print_debug(f"[ERROR] Could not resolve/select symbol {base_symbol}.")
    return None


def fetch_candles(symbol: str, timeframe: int, count: int | None = None) -> pd.DataFrame | None:
    """
    Safely fetch bars for `symbol` at `timeframe`.
    - Uses default bar counts from config when `count` is None.
    - Returns clean DataFrame with datetime index, or None on failure.
    """
    if not initialize_mt5():
        print_debug(f"[ERROR] Failed to initialize MT5 for {symbol}")
        return None

    resolved = _resolve_symbol(symbol)
    if not resolved:
        print_debug(f"[ERROR] Failed to resolve/select symbol {symbol} in Market Watch")
        return None
    symbol = resolved

    tf_label = next((k for k, v in TIMEFRAMES.items() if v == timeframe), None)
    want = count or CANDLE_COUNTS.get(tf_label, 500)

    try:
        print_debug(f"[DEBUG] Fetching {want} candles for {symbol} on TF={tf_label or timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, want)

        if rates is None:
            error_code, error_msg = mt5.last_error()
            print_debug(f"[MT5 ERROR] No data for {symbol}@{tf_label or timeframe} code={error_code} msg={error_msg}")
            return None

        if len(rates) == 0:
            print_debug(f"[MT5 ERROR] Empty data for {symbol}@{tf_label or timeframe}")
            return None

        df = pd.DataFrame(rates)
        # basic schema guard
        need_cols = {"time", "open", "high", "low", "close"}
        if not need_cols.issubset(df.columns):
            print_debug(f"[WARN] Missing OHLC/time columns for {symbol}@{tf_label or timeframe}")
            return None

        df["time"] = pd.to_datetime(df["time"], unit="s")
        if df.isnull().any().any():
            print_debug(f"[WARN] Null values in {symbol}@{tf_label or timeframe}")
            return None

        return df

    except Exception as e:
        print_debug(f"[FETCH EXCEPTION] {symbol}@{tf_label or timeframe}: {e}")
        return None


# Backward-compatible alias
ensure_data = fetch_candles
