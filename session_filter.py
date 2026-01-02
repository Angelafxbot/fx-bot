from datetime import datetime

def is_active_trading_hours():
    now = datetime.now()
    hour = now.hour
    return not (hour >= 21 or hour < 6)

def is_active_session(symbol):
    # Extendable: Define specific sessions per symbol or use general logic
    return is_active_trading_hours()
