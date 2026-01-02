# performance_panel.py

import pandas as pd
import os
import streamlit as st
from day_trading_bot.config import TRADE_LOG_FILE

def load_trade_log():
    if os.path.exists(TRADE_LOG_FILE):
        return pd.read_csv(TRADE_LOG_FILE, on_bad_lines='skip')
    else:
        return pd.DataFrame(columns=["symbol", "direction", "volume", "price_open", "price_close", "profit", "timestamp"])

def calculate_performance(df):
    """
    Summarize trading performance from the trade log DataFrame.
    """
    if df.empty:
        return {
            "Total Trades": 0,
            "Net Profit": 0.0,
            "Win Rate (%)": 0.0,
            "Average Profit per Trade": 0.0,
            "Max Drawdown": 0.0
        }

    wins = df[df['profit'] > 0]
    losses = df[df['profit'] <= 0]

    total_trades = len(df)
    net_profit = round(df['profit'].sum(), 2)
    win_rate = round((len(wins) / total_trades) * 100, 2) if total_trades else 0.0
    avg_profit = round(df['profit'].mean(), 2) if total_trades else 0.0
    max_drawdown = round(losses['profit'].min(), 2) if not losses.empty else 0.0

    return {
        "Total Trades": total_trades,
        "Net Profit": net_profit,
        "Win Rate (%)": win_rate,
        "Average Profit per Trade": avg_profit,
        "Max Drawdown": max_drawdown
    }

def performance_summary(df):
    """
    Display trading performance summary inside Streamlit dashboard.
    """
    summary = calculate_performance(df)

    st.subheader("Performance Summary")
    st.metric("Total Trades", summary["Total Trades"])
    st.metric("Net Profit", f"${summary['Net Profit']}")
    st.metric("Win Rate", f"{summary['Win Rate (%)']}%")
    st.metric("Average Profit per Trade", f"${summary['Average Profit per Trade']}")
    st.metric("Max Drawdown", f"${summary['Max Drawdown']}")
