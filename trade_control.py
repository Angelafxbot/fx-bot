import MetaTrader5 as mt5
from datetime import datetime

# Optional in-memory trade log (can be expanded for logging to file/db if needed)
open_trades = {}

def is_trade_active(symbol: str) -> bool:
    """
    Check if a trade is already active for the given symbol.
    Uses MT5's position info.
    """
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0

def register_trade(symbol: str):
    """
    Optionally register/log trade.
    This is a placeholder function.
    """
    open_trades[symbol] = datetime.now()
    print(f"[TRADE REGISTERED] {symbol} @ {open_trades[symbol]}")
