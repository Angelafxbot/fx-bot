import pandas as pd
from .indicators import calculate_indicators
from .pattern_detector import detect_pattern
from .reversal_signal import detect_reversal_signal
from .utils.logger import print_debug

# ─── Zone-detection switches and parameters ───
ENABLE_ATR_FILTER = False  # if False, skip ATR-based consolidation filter
ENABLE_BREAKOUT_FILTER = False  # if False, skip breakout-size filter
DEFAULT_WINDOW = 20  # lookback candles for consolidation
DEFAULT_RANGE_FACTOR = 1.0  # max spread = range_factor * ATR
DEFAULT_BREAKOUT = 0.1  # min move = breakout_mult * ATR
DEFAULT_MAX_ZONES = 3  # how many merged zones to keep per TF

# Padding & reaction settings
M15_PAD_FACTOR = 0.5  # fraction of M15 ATR to use as pip-gap padding
JPY_ABS_PAD = 0.01  # absolute pad for JPY pairs if no M15 data
PATTERN_LOOKBACK = 3  # number of M15 bars to confirm reversal pattern


def get_zone_tolerance(symbol: str) -> float:
    s = symbol.upper()
    if "XAU" in s:
        return 1.0
    if "JPY" in s:
        return 0.03
    return 0.0003


def _merge_zones(zones, max_zones):
    merged = []
    for low, high in zones:
        if low == high:
            continue
        for i, (ex_low, ex_high) in enumerate(merged):
            if not (high < ex_low or low > ex_high):
                merged[i] = (min(low, ex_low), max(high, ex_high))
                break
        else:
            merged.append((low, high))
    return merged[-max_zones:]


def find_zones(df: pd.DataFrame,
               window: int = DEFAULT_WINDOW,
               range_factor: float = DEFAULT_RANGE_FACTOR,
               breakout_mult: float = DEFAULT_BREAKOUT,
               max_zones: int = DEFAULT_MAX_ZONES):
    df = df.copy()
    df.columns = df.columns.str.lower()

    if "atr_14" not in df.columns:
        df = calculate_indicators(df)
        df.columns = df.columns.str.lower()

    atr = df["atr_14"].iat[-1]
    demand, supply = [], []

    # debug: show tightest spread vs threshold
    roll_spread = df["high"].rolling(window).max() - df["low"].rolling(window).min()
    if not roll_spread.dropna().empty:
        print_debug(
            f"[DEBUG] ATR={atr:.5f}, spread_thresh={range_factor * atr:.5f}, tightest_spread={roll_spread.dropna().min():.5f}")

    for start in range(len(df) - window):
        w = df.iloc[start:start + window]
        spread = w["high"].max() - w["low"].min()
        ok_spread = (not ENABLE_ATR_FILTER) or (spread < range_factor * atr)
        fc = w["close"].iat[0]
        lc = w["close"].iat[-1]
        move = abs(lc - fc)
        ok_break = (not ENABLE_BREAKOUT_FILTER) or (move > breakout_mult * atr)

        if ok_spread and ok_break:
            low, high = w["low"].min(), w["high"].max()
            if low == high:
                continue
            if lc > fc:
                demand.append((low, high))
            else:
                supply.append((low, high))

    return _merge_zones(demand, max_zones), _merge_zones(supply, max_zones)


# ─── TF wrappers ───
def find_m30_zones(df): return find_zones(df, window=20, range_factor=1.0, breakout_mult=0.1, max_zones=3)


def find_h1_zones(df):  return find_zones(df, window=20, range_factor=1.0, breakout_mult=0.1, max_zones=3)


def find_h2_zones(df):  return find_zones(df, window=25, range_factor=1.0, breakout_mult=0.1, max_zones=3)


def find_h4_zones(df):  return find_zones(df, window=30, range_factor=1.0, breakout_mult=0.1, max_zones=3)


def find_d1_zones(df):  return find_zones(df, window=10, range_factor=1.0, breakout_mult=0.1, max_zones=2)


# ─── Multi-TF match + M15-based padding + combined reversal confirmation ───
def find_zones_fallback(df_dict: dict,
                        direction: str,
                        curr_price: float,
                        symbol: str = ""):
    # 1) determine pip-gap from M15 ATR or fallback
    m15_df = df_dict.get("M15")
    if m15_df is not None and "atr_14" in m15_df.columns:
        m15_atr = m15_df["atr_14"].iat[-1]
        zone_tol = m15_atr * M15_PAD_FACTOR
        print_debug(f"[DEBUG] Using M15 ATR padding: ATR={m15_atr:.5f}, pad={zone_tol:.5f}")
    else:
        zone_tol = JPY_ABS_PAD if "JPY" in symbol.upper() else get_zone_tolerance(symbol)
        print_debug(f"[DEBUG] No M15 data; using static tol={zone_tol:.5f}")

    tf_finders = {
        "M30": find_m30_zones,
        "H1": find_h1_zones,
        "H2": find_h2_zones,
        "H4": find_h4_zones,
        "D1": find_d1_zones
    }

    # 2) scan each TF, print zones, and check for in-zone + reversal
    for tf, fn in tf_finders.items():
        df = df_dict.get(tf)
        if df is None or df.empty:
            continue

        dz, sz = fn(df)
        print_debug(f"[ZONES] {symbol} | {tf} Demand Zones:")
        if dz:
            for low, high in dz:
                print_debug(f"  -> Demand Zone: {low:.5f} -> {high:.5f}")
        else:
            print_debug("  (none)")

        print_debug(f"[ZONES] {symbol} | {tf} Supply Zones:")
        if sz:
            for low, high in sz:
                print_debug(f"  -> Supply Zone: {low:.5f} -> {high:.5f}")
        else:
            print_debug("  (none)")

        print_debug(f"Current Price: {curr_price:.5f}")
        zones = dz if direction == "BUY" else sz

        for low, high in zones:
            if low - zone_tol <= curr_price <= high + zone_tol:
                # check chart patterns first
                if m15_df is not None and len(m15_df) >= PATTERN_LOOKBACK:
                    look_df = m15_df.tail(PATTERN_LOOKBACK)
                    pat = detect_pattern(look_df, expected_direction=direction)
                    if pat and pat.get("direction") == direction:
                        print_debug(
                            f"[MATCH] Chart pattern '{pat['pattern']}' confirmed in zone: {low:.5f}->{high:.5f} on {tf}")
                        return dz, sz, tf
                # fallback to multi-TF candle reversal check
                if detect_reversal_signal(symbol, direction):
                    print_debug(f"[MATCH] Candle reversal confirmed in zone: {low:.5f}->{high:.5f} on {tf}")
                    return dz, sz, tf
                print_debug(f"[REJECT] Zone touched but no pattern reversal confirmed: {low:.5f}->{high:.5f} on {tf}")
                # no break, continue scanning next zone

    # 3) no confirmed match: nearest-zone fallback info
    nearest, nearest_tf, best_dist = None, None, float('inf')
    for tf, fn in tf_finders.items():
        df = df_dict.get(tf)
        if df is None or df.empty:
            continue
        dz, sz = fn(df)
        for low, high in (dz if direction == "BUY" else sz):
            mid = (low + high) / 2
            d = abs(mid - curr_price)
            if d < best_dist:
                best_dist, nearest, nearest_tf = d, (low, high), tf

    if nearest:
        print_debug(f"[INFO] Nearest {direction} Zone: {nearest[0]:.5f} -> {nearest[1]:.5f} on {nearest_tf}")
    else:
        print_debug(f"[INFO] No {direction} zones found on any TF.")

    print_debug(f"[ZONES] {symbol}: No confirmed zone match found.")
    return [], [], None
