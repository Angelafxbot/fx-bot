# risk.py
from __future__ import annotations

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


def _get_symbol_info(symbol):
    if not mt5:
        return None
    try:
        return mt5.symbol_info(symbol)
    except Exception:
        return None


def _pip_size(info, symbol: str) -> float:
    """
    Generic pip size: 10 * point works for majors, JPY and XAU on most brokers.
    Falls back to heuristics if info is missing.
    """
    if info and getattr(info, "point", 0) > 0:
        return float(info.point) * 10.0
    s = symbol.upper()
    if "XAU" in s:
        return 0.1
    if "JPY" in s:
        return 0.01
    return 0.0001


def calculate_risk_lot_size(balance, risk_percent, stop_loss_pips, symbol):
    """
    Compute lot so that monetary risk <= balance * (risk_percent / 100).
    - Uses MT5 symbol info when available (tick_value/tick_size).
    - Rounds to broker volume_step; clamps to volume_min/volume_max.
    - Fallback = 0.01 when inputs invalid or info unavailable.
    """
    try:
        balance = float(balance or 0)
        risk_percent = float(risk_percent or 0)
        sl_pips = float(stop_loss_pips or 0)
        if balance <= 0 or risk_percent <= 0 or sl_pips <= 0:
            # fallback min lot
            info = _get_symbol_info(symbol)
            if info:
                return round(max(float(info.volume_min), 0.01), 2)
            return 0.01

        risk_amount = balance * (risk_percent / 100.0)

        info = _get_symbol_info(symbol)
        if info and getattr(info, "tick_value", 0) and getattr(info, "tick_size", 0):
            pip_sz = _pip_size(info, symbol)
            # $ per pip per 1 lot:
            pip_value_per_lot = (pip_sz / float(info.tick_size)) * float(info.tick_value)
            lot = risk_amount / (sl_pips * pip_value_per_lot)

            step = float(getattr(info, "volume_step", 0.01) or 0.01)
            vmin = max(float(getattr(info, "volume_min", 0.01) or 0.01), 0.01)
            vmax = float(getattr(info, "volume_max", 100.0) or 100.0)

            # round to step and clamp
            lot = round(round(lot / step) * step, 2)
            lot = max(vmin, min(lot, vmax))
            return lot

        # Fallback when symbol_info is unavailable: simple pip-value map
        pip_values = {
            'XAUUSD': 1.0, 'XAUUSDm': 1.0,
            'GBPJPY': 10.0, 'GBPJPYm': 10.0,
            'EURJPY': 10.0, 'EURJPYm': 10.0,
            'USDJPY': 10.0, 'USDJPYm': 10.0,
            'GBPUSD': 10.0, 'GBPUSDm': 10.0,
            'EURAUD': 10.0, 'EURAUDm': 10.0,
            'EURUSD': 10.0, 'EURUSDm': 10.0
        }
        pip_value = float(pip_values.get(symbol.upper(), 10.0))
        lot = risk_amount / (sl_pips * pip_value)
        return max(0.01, round(lot, 2))

    except Exception:
        return 0.01
