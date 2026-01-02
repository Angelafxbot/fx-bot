import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

from day_trading_bot.indicators import calculate_indicators
from day_trading_bot.support_resistance import is_near_support_resistance
from day_trading_bot.utils.account import get_balance
from day_trading_bot.utils.risk import calculate_lot_size

from day_trading_bot.config import SYMBOLS, TIMEFRAME, SL_BUFFER_PIPS, TP_MULTIPLIER, RISK_PERCENT
from day_trading_bot.execution import open_trade
from day_trading_bot.utils.logger import log_trade, print_debug

SLEEP_INTERVAL = 60  # Run every 60 seconds

def strategy_fusion(df):
    signals = []

    # Strategy 1: Trend - EMA crossover + ADX
    ema_short = df['ema_20'].iloc[-1]
    ema_long = df['ema_50'].iloc[-1]
    adx = df['adx'].iloc[-1]

    if adx > 25:
        if ema_short > ema_long:
            signals.append("BUY")
        elif ema_short < ema_long:
            signals.append("SELL")

    # Strategy 2: Breakout - Recent high/low
    high = df['high'].iloc[-20:].max()
    low = df['low'].iloc[-20:].min()
    close = df['close'].iloc[-1]
    if close > high:
        signals.append("BUY")
    elif close < low:
        signals.append("SELL")

    # Strategy 3: Support/Resistance
    sr_zone = is_near_support_resistance(df)
    if sr_zone == "support":
        signals.append("BUY")
    elif sr_zone == "resistance":
        signals.append("SELL")

    return signals

def run_bot():
    if not mt5.initialize():
        print_debug(" MT5 initialization failed.")
        return

    print_debug(" MT5 successfully initialized.")

    while True:
        for symbol in SYMBOLS:
            try:
                df = calculate_indicators(symbol, TIMEFRAME)
                if df is None or df.empty:
                    print_debug(f"⚠️ No data for {symbol}")
                    continue

                signals = strategy_fusion(df)
                signal_count = {"BUY": signals.count("BUY"), "SELL": signals.count("SELL")}
                print_debug(f"{symbol} | Signals: {signal_count}")

                if signal_count["BUY"] >= 2 or signal_count["SELL"] >= 2:
                    balance = get_balance()
                    lot_size = calculate_lot_size(balance, RISK_PERCENT, symbol)

                    direction = "BUY" if signal_count["BUY"] >= 2 else "SELL"
                    open_trade(
                        symbol=symbol,
                        direction=direction,
                        balance=balance,
                        stop_loss=None,
                        take_profit=None,
                        lot_size=lot_size
                    )

            except Exception as e:
                print_debug(f"❗ Error analyzing {symbol}: {e}")

        time.sleep(SLEEP_INTERVAL)
