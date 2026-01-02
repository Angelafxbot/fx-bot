# utils/common.py
from __future__ import annotations

def get_lot_size(balance: float,
                 risk_percent: float,
                 sl_distance_points: float,
                 pip_value: float = 1.0) -> float:
    """
    1% risk per trade by default, with 0.01 minimum lot fallback
    and 1.0 maximum lot cap (to match your risk.py behavior).
    """
    try:
        if balance <= 0 or sl_distance_points is None or sl_distance_points <= 0 or pip_value <= 0:
            return 0.01
        risk_amount = float(balance) * (float(risk_percent) / 100.0)
        lot = risk_amount / (float(sl_distance_points) * float(pip_value))
        # enforce your bounds
        lot = max(0.01, min(lot, 1.0))
        return round(lot, 2)
    except Exception:
        return 0.01
