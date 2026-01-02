# streamlit_app.py

import os
import sys
import logging
import threading
from datetime import datetime

# ── Path setup for imports ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

BOT_DIR = os.path.join(BASE_DIR, "day_trading_bot")
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

STOP_FLAG = os.path.join(BASE_DIR, "BOT_STOP.flag")  # shared with main/launcher

# ── Streamlit setup ──────────────────────────────────────────────────────────
# Silence missing ScriptRunContext warnings
logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").setLevel(logging.ERROR)

import streamlit as st  # after logging tweak

st.set_page_config(
    page_title="Forex Bot Dashboard",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ── Bot imports (single-pass run) ────────────────────────────────────────────
from day_trading_bot.core_trading_bot import run_bot
from day_trading_bot.config import CHECK_INTERVAL, USE_SESSION_FILTER
from day_trading_bot.session_filter import is_active_trading_hours
from day_trading_bot.performance_panel import load_trade_log, performance_summary
from day_trading_bot.utils.logger import print_debug

# ── Session state init ───────────────────────────────────────────────────────
if "stop_event" not in st.session_state:
    st.session_state["stop_event"] = threading.Event()
if "bot_thread" not in st.session_state:
    st.session_state["bot_thread"] = None
if "last_run" not in st.session_state:
    st.session_state["last_run"] = None
if "session_filter_enabled" not in st.session_state:
    st.session_state["session_filter_enabled"] = USE_SESSION_FILTER

# ── Sidebar controls ─────────────────────────────────────────────────────────
st.sidebar.header("Trading Mode")
st.sidebar.checkbox(
    "Enable Session-Only Trading",
    key="session_filter_enabled"
)

# ── Main UI ──────────────────────────────────────────────────────────────────
st.title("Forex Bot Control Panel")
st.markdown(f"**Last run:** {st.session_state['last_run'] or 'Never'}")

with st.expander("Performance Summary"):
    try:
        df = load_trade_log()
        performance_summary(df)
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"Failed to load trade log: {e}")

# ── Loop (stoppable) ─────────────────────────────────────────────────────────
def loop_bot(stop_event: threading.Event):
    print_debug("[MAIN] Bot loop starting")
    while not stop_event.is_set():
        # Respect launcher stop flag too
        if os.path.exists(STOP_FLAG):
            print_debug("[LOOP] Stop flag detected from launcher. Exiting loop.")
            break

        st.session_state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print_debug("[LOOP] Starting new cycle")

        try:
            if st.session_state.get("session_filter_enabled", USE_SESSION_FILTER):
                if not is_active_trading_hours():
                    print_debug("[SKIP] Outside session hours")
                    # wait but remain responsive to stop
                    if stop_event.wait(CHECK_INTERVAL):
                        break
                    continue

            run_bot()  # single pass
        except Exception as e:
            print_debug(f"[BOT ERROR] {e}")

        # wait until next cycle, but break fast if stopped
        if stop_event.wait(CHECK_INTERVAL):
            break

    print_debug("[MAIN] Bot loop stopped")

# ── Start / Stop buttons ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)

def start_clicked():
    if st.session_state["bot_thread"] is not None:
        st.info("Bot is already running.")
        return
    # clear any leftover stop flag from launcher
    try:
        if os.path.exists(STOP_FLAG):
            os.remove(STOP_FLAG)
    except Exception:
        pass

    st.session_state["stop_event"].clear()
    t = threading.Thread(target=loop_bot, args=(st.session_state["stop_event"],), daemon=True)
    t.start()
    st.session_state["bot_thread"] = t
    print_debug("[MAIN] Bot thread started")

def stop_clicked():
    # signal our loop
    st.session_state["stop_event"].set()
    # drop shared flag so main.exe exits promptly if it’s running
    try:
        with open(STOP_FLAG, "w", encoding="utf-8"):
            pass
    except Exception:
        pass
    st.success("Stop requested.")
    print_debug("[MAIN] Stop requested")

with col1:
    st.button("Start bot", on_click=start_clicked)
with col2:
    st.button("Stop bot", on_click=stop_clicked)

# Status line
running = st.session_state["bot_thread"] is not None and st.session_state["bot_thread"].is_alive()
st.write(f"**Status:** {'Running' if running else 'Stopped'}")
