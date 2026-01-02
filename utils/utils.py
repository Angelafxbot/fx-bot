# utils/utils.py

from __future__ import annotations
import MetaTrader5 as mt5
from typing import Tuple
import pandas as pd

SYMBOL = "XAUUSDm"  # default symbol if none provided

def find_nearest_levels(df: pd.DataFrame,
                        window: int = 10,
                        tolerance: float = 0.0003) -> Tuple[float | None, float | None]:
    """
    Lightweight S/R scan:
      - detects local swing highs/lows using a rolling window
      - returns closest support < close and resistance > close
    """
    try:
        highs = df["high"]; lows = df["low"]; close = df["close"].iloc[-1]
        supports, resistances = [], []

        for i in range(window, len(df) - window):
            h = highs.iat[i]; l = lows.iat[i]
            if (h > highs.iloc[i - window:i]).all() and (h > highs.iloc[i + 1:i + 1 + window]).all():
                resistances.append(h)
            if (l < lows.iloc[i - window:i]).all() and (l < lows.iloc[i + 1:i + 1 + window]).all():
                supports.append(l)

        support = max((s for s in supports if s < close), default=None)
        resistance = min((r for r in resistances if r > close), default=None)
        return support, resistance
    except Exception:
        return None, None

def get_lot_size(balance: float,
                 risk_percent: float,
                 sl_pips: float,
                 pip_value: float = 1.0) -> float:
    """
    Safe lot sizing compatible with existing callers.
    - Falls back to 0.01 on invalid inputs.
    - Rounds and enforces a lower bound to avoid 0.0 lots on tiny balances.
    """
    try:
        if sl_pips is None or sl_pips <= 0 or pip_value <= 0:
            return 0.01
        risk_amount = max(0.0, float(balance)) * (float(risk_percent) / 100.0)
        lot = risk_amount / (float(sl_pips) * float(pip_value))
        return round(max(lot, 0.01), 2)
    except Exception:
        return 0.01
