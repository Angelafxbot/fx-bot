# day_trading_bot/trade_manager.py
import MetaTrader5 as mt5

def _price_digits(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    return getattr(info, "digits", 5) or 5

def manage_open_trades():
    positions = mt5.positions_get()
    if not positions:
        return

    for position in positions:
        symbol      = position.symbol
        entry_price = float(position.price_open)
        current_sl  = float(position.sl) if position.sl else None
        tp          = float(position.tp) if position.tp else None
        direction   = "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL"

        if not tp or tp == 0:
            continue

        tp_dist = abs(tp - entry_price)
        if tp_dist <= 0:
            continue

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        current_price = float(tick.bid if direction == "BUY" else tick.ask)

        # Progress toward TP: 0.0 → 1.0
        profit_ratio = (
            (current_price - entry_price) / tp_dist
            if direction == "BUY" else
            (entry_price - current_price) / tp_dist
        )

        # Start locking once ≥30% to TP
        if profit_ratio >= 0.30:
            sl_pct = max(min(profit_ratio - 0.20, profit_ratio), 0.0)

            if direction == "BUY":
                proposed_sl = entry_price + sl_pct * tp_dist
                better = (current_sl is None) or (proposed_sl > current_sl)
            else:
                proposed_sl = entry_price - sl_pct * tp_dist
                better = (current_sl is None) or (proposed_sl < current_sl)

            if better:
                digits = _price_digits(symbol)
                req = {
                    "action":       mt5.TRADE_ACTION_SLTP,
                    "position":     position.ticket,
                    "symbol":       symbol,
                    "sl":           round(proposed_sl, digits),
                    "tp":           round(tp, digits),
                    "type_time":    mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                res = mt5.order_send(req)
                if res is None or getattr(res, "retcode", None) != mt5.TRADE_RETCODE_DONE:
                    # non-fatal; we keep managing on next loop
                    continue
