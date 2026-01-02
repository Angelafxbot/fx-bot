from datetime import datetime, timedelta

def is_news_nearby(symbol="USD"):
    """
    Simulates high-impact news proximity (within ±30 minutes of a fixed time).
    Returns True if nearby, otherwise False.
    """
    now = datetime.utcnow()

    # Simulated high-impact news event at 13:00 UTC
    simulated_news_time = datetime(now.year, now.month, now.day, 13, 0)
    news_window = timedelta(minutes=30)

    # Check if we're within ±30 minutes of the news
    if abs(now - simulated_news_time) < news_window:
        return True

    return False

