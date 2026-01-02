# day_trading_bot/performance_logger.py

import os
import csv
from datetime import datetime
from typing import List, Dict

LOG_FILE = "trade_log.csv"


# ------------------------
# Save trade to log
# ------------------------
def log_trade(trade_data: Dict):
    header = ["timestamp", "symbol", "direction", "lot_size", "entry_price", "tp", "sl", "confidence", "reasons"]

    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": trade_data.get("symbol"),
            "direction": trade_data.get("direction"),
            "lot_size": trade_data.get("lot_size"),
            "entry_price": trade_data.get("entry_price"),
            "tp": trade_data.get("tp"),
            "sl": trade_data.get("sl"),
            "confidence": trade_data.get("confidence"),
            "reasons": "; ".join(trade_data.get("reasons", []))
        })


# ------------------------
# Read trade log
# ------------------------
def read_log() -> List[Dict]:
    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


# ------------------------
# Summarize performance
# ------------------------
def summarize_performance() -> Dict:
    trades = read_log()
    total = len(trades)
    if total == 0:
        return {"total": 0, "buy": 0, "sell": 0}

    buy_count = sum(1 for t in trades if t["direction"] == "BUY")
    sell_count = total - buy_count

    return {
        "total": total,
        "buy": buy_count,
        "sell": sell_count,
        "symbols": list(set(t["symbol"] for t in trades))
    }
