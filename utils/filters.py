# filters.py

from __future__ import annotations

def passes_all_filters(trade_signal: dict) -> bool:
    """
    Decide if a trade passes core strategy filters.
    Required keys in trade_signal (same as before):
      - direction: "BUY"/"SELL"/"unclear"
      - pattern_valid: bool
      - confirmations: int
      - total_strategies: int
      - confidence: int/float

    Optional overrides (keep defaults if missing):
      - min_confidence: int/float (default 70)
      - min_confirmation_ratio: float in [0,1] (default 0.7)
    """
    direction = trade_signal.get("direction", "unclear")
    pattern_valid = bool(trade_signal.get("pattern_valid", False))
    confirmations = max(0, int(trade_signal.get("confirmations", 0)))
    total = max(0, int(trade_signal.get("total_strategies", 7)))
    confidence = float(trade_signal.get("confidence", 0.0))

    # Defaults preserved; can be overridden per-call without changing callers.
    min_conf = float(trade_signal.get("min_confidence", 70))
    min_ratio = float(trade_signal.get("min_confirmation_ratio", 0.7))

    ratio = (confirmations / total) if total > 0 else 0.0

    return (
        direction in ("BUY", "SELL")
        and pattern_valid
        and confidence >= min_conf
        and ratio >= min_ratio
    )
