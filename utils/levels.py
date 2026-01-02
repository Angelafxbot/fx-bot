# utils/levels.py

from __future__ import annotations

def is_near_psychological_level(price: float,
                                sensitivity: int = 100,
                                digits: int | None = None) -> bool:
    """
    Check if `price` is near a round-1000-point level (psych level).
    - `sensitivity` is measured in *points* (e.g., 100 points ≈ 10 pips on 5-digit pairs).
    - `digits` optionally specifies the price precision (None = infer: >=100 -> 2, else 4).
      This keeps compatibility for JPY/XAU without changing the default behavior.
    """
    if digits is None:
        digits = 2 if price >= 100 else 4  # heuristic: JPY/XAU vs majors

    factor = 10 ** int(digits)
    price_points = int(round(price * factor))
    remainder = price_points % 1000

    return remainder <= sensitivity or remainder >= (1000 - sensitivity)
