import os
import json
import time
import threading
import requests
import pytz
import tkinter as tk

from tkinter import messagebox
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# ─── CONFIG ────────────────────────────────────────────────────────────────
TIMEZONE              = pytz.timezone("Africa/Lagos")  # GMT+1
TARGET_CURRENCIES     = ["USD", "GBP", "EUR"]
REMINDER_INTERVAL_HOURS = 3

CACHE_DATE_FILE = "last_fetch_date.txt"
CACHE_NEWS_FILE = "news_cache.json"

REQUESTS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}
# ─────────────────────────────────────────────────────────────────────────────

def fetch_daily_news():
    """
    Scrape Investing.com economic calendar page via requests/BS4,
    filter for today’s USD/GBP/EUR events, return list of dicts.
    """
    url = "https://www.investing.com/economic-calendar/"
    resp = requests.get(url, headers=REQUESTS_HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("tr.js-event-item")
    today = datetime.now(TIMEZONE).date()
    out = []

    for row in rows:
        dt = row.get("data-event-datetime", "").strip()
        if not dt:
            continue

        # try both slash & dash formats
        ev_utc = None
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                ev_utc = datetime.strptime(dt, fmt)
                break
            except ValueError:
                pass
        if not ev_utc:
            continue

        ev_local = ev_utc.replace(tzinfo=timezone.utc).astimezone(TIMEZONE)
        if ev_local.date() != today:
            continue

        cur = row.get("data-event-currency", "").strip()
        if cur not in TARGET_CURRENCIES:
            continue

        title_el    = row.select_one(".event")
        forecast_el = row.select_one(".forecast")
        actual_el   = row.select_one(".actual")
        icons       = row.select(".sentiment > i")

        # impact by count of “i” icons
        impact = "Low"
        if icons:
            cnt = min(len(icons), 3)
            impact = ["Low", "Medium", "High"][cnt-1]

        out.append({
            "currency": cur,
            "time":      ev_local.strftime("%H:%M"),
            "title":     (title_el.text.strip()    if title_el    else "?"),
            "impact":    impact,
            "forecast":  (forecast_el.text.strip() if forecast_el else None),
            "actual":    (actual_el.text.strip()   if actual_el   else None),
        })

    return out

def show_popup(title, msg):
    """Fire a tkinter messagebox in its own thread."""
    def _go():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, msg)
        root.destroy()
    threading.Thread(target=_go).start()

def infer_direction(ev):
    """Compare actual vs forecast → BUY/SELL or None."""
    try:
        a = float(str(ev["actual"]).replace("%",""))
        f = float(str(ev["forecast"]).replace("%",""))
        c = ev["currency"]
        if a > f: return f"{c} → BUY"
        if a < f: return f"{c} → SELL"
    except:
        pass
    return None

def get_affected_pairs(c):
    return {
        "USD": ["EURUSD","GBPUSD","USDJPY","XAUUSD"],
        "GBP": ["GBPUSD","EURGBP","GBPJPY"],
        "EUR": ["EURUSD","EURGBP","EURJPY"],
    }.get(c, [])

def schedule_alerts(news):
    now = datetime.now(TIMEZONE)
    for ev in news:
        hh, mm = map(int, ev["time"].split(":"))
        evt   = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if evt < now:
            continue

        curr      = ev["currency"]
        impact    = ev["impact"]
        direction = infer_direction(ev) or "?"
        pairs     = ", ".join(get_affected_pairs(curr))

        def make_alert(mins):
            def _alert():
                show_popup(
                    "Upcoming News Alert",
                    f"{mins} min to {curr} news:\n\n"
                    f"{ev['title']}\nImpact: {impact}\n"
                    f"Affected: {pairs}\nExpected: {direction}"
                )
            delay = (evt - timedelta(minutes=mins) - now).total_seconds()
            threading.Timer(delay, _alert).start()

        make_alert(30)
        make_alert(2)

        def after():
            show_popup(
                "News Released",
                f"{curr} News Released:\n\n"
                f"{ev['title']}\nActual: {ev['actual']} | Forecast: {ev['forecast']}\n"
                f"Direction: {direction}\nAffected: {pairs}"
            )
        post_delay = (evt - now).total_seconds() + 60
        threading.Timer(post_delay, after).start()

def periodic_summary(news):
    lines = []
    for ev in news:
        d = infer_direction(ev) or "?"
        p = ", ".join(get_affected_pairs(ev["currency"]))
        lines.append(
            f"{ev['time']} | {ev['currency']} | {ev['title']} | {ev['impact']}\n"
            f"Affected: {p}\nExpected: {d}\n"
        )
    summary = "\n".join(lines) or "No news for today."
    show_popup("3-Hour News Summary", summary)
    threading.Timer(REMINDER_INTERVAL_HOURS*3600,
                    lambda: periodic_summary(news)
                   ).start()

def start_news_monitor():
    # ─── clear cache on new day ────────────────────────────────────────
    today = datetime.now(TIMEZONE).date().isoformat()
    if not os.path.exists(CACHE_DATE_FILE) or open(CACHE_DATE_FILE).read().strip() != today:
        with open(CACHE_DATE_FILE, "w") as f:
            f.write(today)
        if os.path.exists(CACHE_NEWS_FILE):
            os.remove(CACHE_NEWS_FILE)

    # ─── load or fetch ─────────────────────────────────────────────────
    if os.path.exists(CACHE_NEWS_FILE):
        news = json.load(open(CACHE_NEWS_FILE))
    else:
        news = fetch_daily_news()
        json.dump(news, open(CACHE_NEWS_FILE, "w"), indent=2)

    schedule_alerts(news)
    periodic_summary(news)

if __name__ == "__main__":
    start_news_monitor()
