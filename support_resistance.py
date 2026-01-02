import pandas as pd
from typing import List, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Existing APIs (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def find_nearest_levels(
    df: pd.DataFrame,
    window: int = 20,
    lookback: int = 1000,
    max_levels: int = 3
) -> Tuple[List[float], List[float]]:
    """
    Detects the top N nearest support and resistance levels over a deep lookback window.
    Returns the closest `max_levels` levels above and below current price.
    """
    supports: List[float] = []
    resistances: List[float] = []

    highs = df['high']
    lows = df['low']
    recent_close = float(df['close'].iloc[-1])

    max_index = min(max(len(df) - window, 0), lookback)

    for i in range(window, max_index):
        high = highs[i]
        low = lows[i]

        # local swing high / swing low
        if all(high > highs[i - window:i]) and all(high > highs[i + 1:i + 1 + window]):
            resistances.append(float(high))
        if all(low < lows[i - window:i]) and all(low < lows[i + 1:i + 1 + window]):
            supports.append(float(low))

    # Pick top nearest N above and below price
    support_levels = sorted([s for s in supports if s < recent_close], reverse=True)[:max_levels]
    resistance_levels = sorted([r for r in resistances if r > recent_close])[:max_levels]
    return support_levels, resistance_levels


def find_recent_support_resistance(df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
    """
    Fast recent S/R scan using min/max from recent bars.
    """
    recent_data = df.tail(window)
    support = float(recent_data['low'].min())
    resistance = float(recent_data['high'].max())
    return support, resistance


def get_support_resistance_levels(df: pd.DataFrame) -> Tuple[float, float]:
    """
    Legacy interface — returns S/R from last 10 bars.
    """
    support = float(df['low'].tail(10).min())
    resistance = float(df['high'].tail(10).max())
    return round(support, 3), round(resistance, 3)


def is_near_support_or_resistance(
    price: float,
    support_levels: List[float],
    resistance_levels: List[float],
    threshold: float = 0.002
) -> bool:
    """
    Checks if the price is near ANY of the given support or resistance levels
    by an absolute threshold (in price units).
    """
    all_levels = support_levels + resistance_levels
    return any(abs(price - lvl) <= threshold for lvl in all_levels)

# ─────────────────────────────────────────────────────────────────────────────
# New ATR-aware helpers (optional; used by the regime router)
# ─────────────────────────────────────────────────────────────────────────────

def nearest_sr_distance(
    price: float,
    support_levels: List[float],
    resistance_levels: List[float]
) -> Optional[float]:
    """
    Returns the absolute distance (in price) to the nearest S/R level,
    or None if there are no levels.
    """
    levels = support_levels + resistance_levels
    if not levels:
        return None
    return min(abs(price - lvl) for lvl in levels)


def is_near_sr_atr(
    price: float,
    support_levels: List[float],
    resistance_levels: List[float],
    atr: float,
    k: float = 0.35,
    fallback_abs: float = 0.002
) -> bool:
    """
    ATR-aware proximity: TRUE if price is within k*ATR of ANY S/R level.
    If ATR is not positive, falls back to an absolute threshold.
    """
    if atr is None or atr <= 0:
        return is_near_support_or_resistance(price, support_levels, resistance_levels, threshold=fallback_abs)
    thr = k * float(atr)
    return any(abs(price - lvl) <= thr for lvl in (support_levels + resistance_levels))


def is_breakout_atr(
    price: float,
    support_levels: List[float],
    resistance_levels: List[float],
    atr: float,
    direction: str,
    k: float = 0.20,
    fallback_eps: float = 1e-6
) -> bool:
    """
    ATR-aware breakout check used by the trend playbook.
    - BUY: price must be > (max resistance + k*ATR)
    - SELL: price must be < (min support    - k*ATR)
    If levels are missing or ATR <= 0, falls back to a tiny epsilon check.
    """
    direction = (direction or "").upper()
    if direction not in ("BUY", "SELL"):
        return False

    if atr is None or atr <= 0:
        if direction == "BUY":
            return bool(resistance_levels) and price > max(resistance_levels) + fallback_eps
        else:
            return bool(support_levels) and price < min(support_levels) - fallback_eps

    if direction == "BUY":
        if not resistance_levels:
            return False
        return price > max(resistance_levels) + k * float(atr)
    else:
        if not support_levels:
            return False
        return price < min(support_levels) - k * float(atr)


def sr_summary(
    price: float,
    support_levels: List[float],
    resistance_levels: List[float],
    atr: Optional[float] = None
) -> str:
    """
    Human-readable summary for logs/telemetry.
    """
    near = nearest_sr_distance(price, support_levels, resistance_levels)
    parts = []
    if support_levels:
        parts.append(f"S={', '.join(f'{s:.5f}' for s in support_levels)}")
    if resistance_levels:
        parts.append(f"R={', '.join(f'{r:.5f}' for r in resistance_levels)}")
    if near is not None:
        parts.append(f"nearest={near:.5f}")
    if atr is not None and atr > 0:
        parts.append(f"ATR={atr:.5f}")
    return " | ".join(parts) if parts else "no levels"
