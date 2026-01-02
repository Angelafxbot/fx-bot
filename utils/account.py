# day_trading_bot/utils/account.py

import MetaTrader5 as mt5
from .logger import print_debug


def get_balance(default: float = 0.0, auto_init: bool = False) -> float:
    """
    Return the current account balance.
    - Does NOT call mt5.initialize() by default (avoids side-effects in loops).
    - If MT5 isn't initialized:
        * when auto_init=False -> log a warning and return `default`
        * when auto_init=True  -> try to initialize once, else return `default`

    Args:
        default: value to return if balance can't be retrieved.
        auto_init: attempt mt5.initialize() if terminal isn't running.

    Returns:
        float: balance or `default` on failure.
    """
    try:
        # Check terminal status first (cheap & reliable)
        if mt5.terminal_info() is None:
            if auto_init:
                if not mt5.initialize():
                    code, msg = mt5.last_error()
                    print_debug(f"[ERROR] MT5 init failed in get_balance(). code={code} msg={msg}")
                    return default
            else:
                print_debug("[WARN] get_balance() called before MT5.initialize(); returning default.")
                return default

        info = mt5.account_info()
        if info is None:
            print_debug("[ERROR] account_info() returned None.")
            return default

        return float(info.balance)
    except Exception as e:
        print_debug(f"[ERROR] get_balance() exception: {e}")
        return default
