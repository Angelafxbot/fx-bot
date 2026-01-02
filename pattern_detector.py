# day_trading_bot/pattern_detector.py
import pandas as pd
import numpy as np
from typing import Optional

# --- SciPy optional (fallback to simple local-extrema) ---
try:
    from scipy.signal import argrelextrema
    def _extrema(prices: pd.Series, order: int = 5):
        local_min = argrelextrema(prices.values, np.less_equal, order=order)[0]
        local_max = argrelextrema(prices.values, np.greater_equal, order=order)[0]
        return local_min, local_max
except Exception:
    def _extrema(prices: pd.Series, order: int = 5):
        vals = prices.values
        mins, maxs = [], []
        n = len(vals)
        for i in range(order, n - order):
            left  = vals[i - order:i]
            right = vals[i + 1:i + 1 + order]
            if (vals[i] <= left).all() and (vals[i] <= right).all():
                mins.append(i)
            if (vals[i] >= left).all() and (vals[i] >= right).all():
                maxs.append(i)
        return np.array(mins, dtype=int), np.array(maxs, dtype=int)

def find_local_extrema(prices: pd.Series, order: int = 5):
    return _extrema(prices, order=order)

def detect_double_bottom(df: pd.DataFrame) -> bool:
    local_min, _ = find_local_extrema(df['low'], order=5)
    if len(local_min) < 2: return False
    b = df.iloc[local_min]
    return abs(b['low'].iloc[-1] - b['low'].iloc[-2]) < 1e-3

def detect_double_top(df: pd.DataFrame) -> bool:
    _, local_max = find_local_extrema(df['high'], order=5)
    if len(local_max) < 2: return False
    t = df.iloc[local_max]
    return abs(t['high'].iloc[-1] - t['high'].iloc[-2]) < 1e-3

def detect_rectangle(df: pd.DataFrame, tolerance: float = 0.002) -> bool:
    spread = df['high'].max() - df['low'].min()
    avg_close = df['close'].mean()
    return spread <= tolerance * avg_close

def detect_head_and_shoulders(df: pd.DataFrame) -> bool:
    low_mins, high_maxs = find_local_extrema(df['low'], order=5)
    if len(high_maxs) < 3 or len(low_mins) < 2: return False
    peaks = df['high'].iloc[high_maxs][-3:]
    troughs = df['low'].iloc[low_mins][-2:]
    left, head, right = peaks.values
    valley1, valley2 = troughs.values
    cond_head = head > left and head > right
    cond_shoulders = abs(left - right) / max(left, right) < 0.03
    cond_valleys = valley1 < left and valley2 < right
    return cond_head and cond_shoulders and cond_valleys

def detect_inverse_head_and_shoulders(df: pd.DataFrame) -> bool:
    low_mins, high_maxs = find_local_extrema(df['low'], order=5)
    if len(low_mins) < 3 or len(high_maxs) < 2: return False
    troughs = df['low'].iloc[low_mins][-3:]
    peaks = df['high'].iloc[high_maxs][-2:]
    left, head, right = troughs.values
    peak1, peak2 = peaks.values
    cond_head = head < left and head < right
    cond_shoulders = abs(left - right) / max(left, right) < 0.03
    cond_peaks = peak1 > head and peak2 > head
    return cond_head and cond_shoulders and cond_peaks

def detect_ascending_triangle(df: pd.DataFrame, tol: float = 0.005) -> bool:
    low_idxs, _ = find_local_extrema(df['low'], order=5)
    _, high_idxs = find_local_extrema(df['high'], order=5)
    if len(low_idxs) < 2 or len(high_idxs) < 2: return False
    low_vals = df['low'].iloc[low_idxs[-2:]].values
    high_vals = df['high'].iloc[high_idxs[-2:]].values
    cond_lows = low_vals[1] > low_vals[0]
    cond_highs = abs(high_vals[1] - high_vals[0]) / np.mean(high_vals) < tol
    return cond_lows and cond_highs

def detect_descending_triangle(df: pd.DataFrame, tol: float = 0.005) -> bool:
    low_idxs, _ = find_local_extrema(df['low'], order=5)
    _, high_idxs = find_local_extrema(df['high'], order=5)
    if len(low_idxs) < 2 or len(high_idxs) < 2: return False
    low_vals = df['low'].iloc[low_idxs[-2:]].values
    high_vals = df['high'].iloc[high_idxs[-2:]].values
    cond_lows = abs(low_vals[1] - low_vals[0]) / np.mean(low_vals) < tol
    cond_highs = high_vals[1] < high_vals[0]
    return cond_lows and cond_highs

def detect_symmetric_triangle(df: pd.DataFrame, tol: float = 0.01) -> bool:
    low_idxs, _ = find_local_extrema(df['low'], order=5)
    _, high_idxs = find_local_extrema(df['high'], order=5)
    if len(low_idxs) < 2 or len(high_idxs) < 2: return False
    low_vals = df['low'].iloc[low_idxs[-2:]].values
    high_vals = df['high'].iloc[high_idxs[-2:]].values
    cond_lows = low_vals[1] > low_vals[0]
    cond_highs = high_vals[1] < high_vals[0]
    gap1 = high_vals[0] - low_vals[0]
    gap2 = high_vals[1] - low_vals[1]
    cond_gap = gap2 < gap1 * (1 - tol)
    return cond_lows and cond_highs and cond_gap

def detect_wedge(df: pd.DataFrame) -> bool:
    low_idxs, _ = find_local_extrema(df['low'], order=5)
    _, high_idxs = find_local_extrema(df['high'], order=5)
    if len(low_idxs) < 2 or len(high_idxs) < 2: return False
    low_vals = df['low'].iloc[low_idxs[-2:]].values
    high_vals = df['high'].iloc[high_idxs[-2:]].values
    delta_low = low_vals[1] - low_vals[0]
    delta_high = high_vals[1] - high_vals[0]
    width1 = high_vals[0] - low_vals[0]
    width2 = high_vals[1] - low_vals[1]
    cond_contract = width2 < width1
    cond_same_dir = (delta_low * delta_high) > 0
    return cond_same_dir and cond_contract

def detect_flag(df: pd.DataFrame, tolerance: float = 0.003) -> bool:
    n = len(df)
    if n < 10: return False
    half = df.iloc[: n//2]
    pole_move = abs(half['close'].iloc[-1] - half['close'].iloc[0]) / half['close'].iloc[0]
    grip = detect_rectangle(df.iloc[n//2 :], tolerance=tolerance)
    return pole_move > 0.02 and grip

def detect_pennant(df: pd.DataFrame) -> bool:
    n = len(df)
    if n < 10: return False
    tail = df.iloc[- n//3 :]
    return detect_wedge(tail)

def detect_cup_and_handle(df: pd.DataFrame) -> bool:
    n = len(df)
    if n < 12: return False
    third = n // 3
    cup = df.iloc[: 2*third]
    handle = df.iloc[2*third :]
    highs = cup['high']
    if abs(highs.iloc[0] - highs.iloc[-1]) / highs.mean() > 0.01:
        return False
    trough = cup['low'].min()
    if trough > highs.mean() * 0.98:
        return False
    return detect_rectangle(handle, tolerance=0.005)

def detect_pattern(df: pd.DataFrame, expected_direction: Optional[str] = None):
    patterns = [
        (detect_double_bottom, "BUY", "Double Bottom"),
        (detect_double_top, "SELL", "Double Top"),
        (detect_head_and_shoulders, "SELL", "Head and Shoulders"),
        (detect_inverse_head_and_shoulders, "BUY", "Inverse Head and Shoulders"),
        (detect_ascending_triangle, "BUY", "Ascending Triangle"),
        (detect_descending_triangle, "SELL", "Descending Triangle"),
        (detect_symmetric_triangle, None, "Symmetric Triangle"),
        (detect_wedge, None, "Wedge"),
        (detect_flag, None, "Flag"),
        (detect_pennant, None, "Pennant"),
        (detect_cup_and_handle, "BUY", "Cup and Handle"),
        (detect_rectangle, None, "Rectangle"),
    ]
    fallback = None
    for func, direction, name in patterns:
        if func(df):
            if expected_direction and direction == expected_direction:
                return {"direction": direction, "pattern": name}
            if fallback is None:
                fallback = {"direction": direction, "pattern": name}
    return fallback
