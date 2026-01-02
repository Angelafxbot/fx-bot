import re
import pandas as pd
import MetaTrader5 as mt5
from day_trading_bot.risk import calculate_risk_lot_size
from day_trading_bot.utils.account import get_balance as _acct_balance


def _base_symbol(sym: str) -> str:
    s = sym.upper()
    s = re.sub(r'[\.\-_].*$', '', s)   # cut at first ., -, _
    s = re.sub(r'\d+$', '', s)         # remove trailing digits
    if s.endswith('M'): s = s[:-1]     # common suffix
    return ''.join(ch for ch in s if ch.isalpha())


def _digits(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    return int(getattr(info, "digits", 5) or 5)


def _pip_size(symbol: str) -> float:
    info = mt5.symbol_info(symbol)
    if info and getattr(info, "point", 0) > 0:
        return float(info.point) * 10.0
    s = symbol.upper()
    if "XAU" in s: return 0.1
    if "JPY" in s: return 0.01
    return 0.0001


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1])


def _round_volume_to_broker(symbol: str, vol: float) -> float:
    info = mt5.symbol_info(symbol)
    if not info:
        return round(max(vol, 0.01), 2)
    step = float(getattr(info, "volume_step", 0.01) or 0.01)
    vmin = max(float(getattr(info, "volume_min", 0.01) or 0.01), 0.01)
    vmax = float(getattr(info, "volume_max", 100.0) or 100.0)
    vol = round(round(vol / step) * step, 2)
    return max(vmin, min(vol, vmax))


def _monetary_risk_for_lot(symbol: str, entry: float, sl: float, lot: float) -> float:
    """
    Compute $ risk for a given lot using MT5 tick value/size:
      money = lot * (|entry - sl| / tick_size) * tick_value
    """
    info = mt5.symbol_info(symbol)
    if not info or not getattr(info, "tick_value", 0) or not getattr(info, "tick_size", 0):
        # Fallback approximate using "pip" concept (per-lot pip value not exact without info)
        pip = _pip_size(symbol)
        sl_pips = abs(entry - sl) / pip if pip > 0 else 0.0
        approx_pip_value = 10.0 if "XAU" not in symbol.upper() else 1.0
        return lot * sl_pips * approx_pip_value

    price_delta_ticks = abs(entry - sl) / float(info.tick_size)
    return float(lot) * float(price_delta_ticks) * float(info.tick_value)


def place_trade(
    symbol: str,
    direction: str,
    lot_size: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
    comment: str | None = "Structure-based reversal bot",
    *,
    balance: float | None = None,
    risk_percent: float = 1.0,
) -> bool:
    """
    Enforce MAX 1% risk:
      - If lot_size is provided, scale it down if its monetary risk > 1% of balance.
      - If not provided, compute lot for 1% risk via calculate_risk_lot_size.
      - Fallback to 0.01 (or broker min) when we can't compute.
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
    if rates is None or len(rates) == 0:
        print(f"[ERROR] No data for {symbol}")
        return False

    df = pd.DataFrame(rates)
    entry = float(df["close"].iloc[-1])
    digits = _digits(symbol)

    # --- SL/TP (keep ATR-buffered defaults if not provided) ---
    if sl is None or tp is None:
        atr = _atr(df)
        buf = atr * 0.5
        if direction == "BUY":
            sl = float(df["low"].tail(30).min() - buf)
            tp = entry + (entry - sl) * 2.5
        else:
            sl = float(df["high"].tail(30).max() + buf)
            tp = entry - (sl - entry) * 2.5

    if sl <= 0 or tp <= 0 or sl == entry or tp == entry:
        print(f"[SKIP] {symbol} invalid SL/TP | entry={entry} sl={sl} tp={tp}")
        return False

    # --- Determine balance & risk budget ---
    if balance is None:
        try:
            balance = float(_acct_balance())
        except Exception:
            balance = 0.0
    risk_budget = balance * (risk_percent / 100.0)

    # --- Lot sizing ---
    if lot_size is None:
        # compute lot to target ≤ 1% risk
        pip = _pip_size(symbol)
        sl_pips = abs(entry - sl) / pip if pip > 0 else 0.0
        lot_size = calculate_risk_lot_size(balance, risk_percent, sl_pips, symbol)

    lot_size = _round_volume_to_broker(symbol, float(lot_size or 0.01))

    # If caller's lot would risk > 1%, scale DOWN to fit risk budget
    actual_risk = _monetary_risk_for_lot(symbol, entry, sl, lot_size)
    if actual_risk > risk_budget > 0:
        # proportional downscale
        scale = risk_budget / actual_risk
        lot_size = _round_volume_to_broker(symbol, lot_size * scale)

    # --- Broker min-distance guard (keep your table, optional) ---
    base = _base_symbol(symbol)
    min_stop_distances = {
        "XAUUSD": 0.10, "GBPUSD": 0.0012, "EURUSD": 0.0010, "AUDUSD": 0.0008,
        "USDJPY": 0.01, "GBPJPY": 0.01, "EURJPY": 0.01, "CADJPY": 0.01,
        "AUDJPY": 0.01, "CHFJPY": 0.01, "NZDJPY": 0.01, "EURAUD": 0.0010,
        "GBPAUD": 0.0010, "EURCAD": 0.0010, "GBPCHF": 0.0010, "EURNZD": 0.0010,
        "AUDCAD": 0.0010, "AUDNZD": 0.0010,
    }
    min_gap = float(min_stop_distances.get(base, 0.0010))
    if abs(entry - sl) < min_gap or abs(entry - tp) < min_gap:
        print(f"[SKIP] {symbol} SL/TP too close (min {min_gap})")
        return False

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": entry,
        "sl": round(sl, digits),
        "tp": round(tp, digits),
        "deviation": 20,
        "magic": 123456,
        "comment": comment or "",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None or getattr(res, "retcode", None) != mt5.TRADE_RETCODE_DONE:
        print(f"[FAILED] Trade failed: {getattr(res, 'retcode', 'None')} | {getattr(res, 'comment', '')}")
        return False

    print(f"[OK] {direction} {symbol} lot={lot_size} sl={round(sl, digits)} tp={round(tp, digits)} (risk ≤ {risk_percent}%)")
    return True
