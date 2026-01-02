import requests
import threading
from datetime import datetime, timedelta
import pytz
import tkinter as tk
from tkinter import messagebox

# --- Config ---
TARGET_CURRENCIES = ["USD", "GBP", "EUR"]
REMINDER_INTERVAL_HOURS = 3
TIMEZONE = pytz.timezone("Africa/Lagos")  # GMT+1

# Placeholder for real API
def fetch_daily_news():
    # Simulate with dummy data
    return [
        {"currency": "USD", "title": "Core CPI m/m", "impact": "High",
         "time": "14:30", "actual": "0.5", "forecast": "0.3"},
        {"currency": "GBP", "title": "CPI y/y", "impact": "High",
         "time": "08:00", "actual": "6.1", "forecast": "6.3"}
    ]

# --- Popup Alert ---
def show_popup(title, message):
    def popup():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    threading.Thread(target=popup).start()

# --- Estimate Direction ---
def infer_direction(event):
    try:
        actual = float(str(event["actual"]).replace("%", ""))
        forecast = float(str(event["forecast"]).replace("%", ""))
        currency = event["currency"]
        if actual > forecast:
            return f"{currency} → BUY"
        elif actual < forecast:
            return f"{currency} → SELL"
    except:
        return None
    return None

# --- Pairs Affected ---
def get_affected_pairs(currency):
    pairs_map = {
        "USD": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        "GBP": ["GBPUSD", "EURGBP", "GBPJPY"],
        "EUR": ["EURUSD", "EURGBP", "EURJPY"]
    }
    return pairs_map.get(currency.upper(), [])

# --- Schedule Alerts ---
def schedule_alerts(news_events):
    now = datetime.now(TIMEZONE)
    for event in news_events:
        hour, minute = map(int, event["time"].split(":"))
        event_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if event_time < now:
            continue

        currency = event["currency"]
        impact = event["impact"]
        direction = infer_direction(event) or "?"
        pairs = ", ".join(get_affected_pairs(currency))

        def alert_template(minutes_before):
            def alert():
                show_popup("Upcoming News Alert",
                           f"{minutes_before} min to {currency} news:\n\n{event['title']}\nImpact: {impact}\nAffected: {pairs}\nExpected: {direction}")
            delay = (event_time - timedelta(minutes=minutes_before) - now).total_seconds()
            threading.Timer(delay, alert).start()

        alert_template(30)
        alert_template(2)

        def post_news_direction():
            show_popup("News Released",
                       f"{currency} News Released:\n\n{event['title']}\nActual: {event['actual']} | Forecast: {event['forecast']}\nLikely Direction: {direction}\nAffected: {pairs}")

        threading.Timer((event_time - now).total_seconds() + 60, post_news_direction).start()

# --- 3-hour Summary ---
def periodic_summary():
    news = fetch_daily_news()
    lines = []
    for e in news:
        d = infer_direction(e) or "?"
        p = ", ".join(get_affected_pairs(e["currency"]))
        lines.append(f"{e['time']} | {e['currency']} | {e['title']} | {e['impact']}\nAffected: {p}\nExpected: {d}\n")
    show_popup("3-Hour News Summary", "\n".join(lines))
    threading.Timer(REMINDER_INTERVAL_HOURS * 3600, periodic_summary).start()

# --- Entry Point ---
def start_news_monitor():
    news = fetch_daily_news()
    schedule_alerts(news)
    periodic_summary()

if __name__ == '__main__':
    start_news_monitor()