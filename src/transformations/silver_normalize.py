"""
Silver-layer rate normalization.

Converts a per-interval funding rate to a common per-8h basis so rates
are comparable across venues with different interval_hours (1, 4, 8, ...).
"""

from typing import Optional

HOURS_PER_YEAR = 24.0 * 365.0

def normalize_rate(rate: Optional[float], interval_hours: Optional[int]) -> Optional[float]:
    """
    Convert a per-interval funding rate to its per-8h equivalent.

    rate_per_8h = rate * 8 / interval_hours

    Returns None (not 0.0) when the input is missing or business-invalid
    (interval_hours <= 0) — "unknown" and "zero" are different claims.
    """
    if rate is None or interval_hours is None:
        return None
    if interval_hours <= 0:
        return None

    return rate * 8.0 / interval_hours


def annualize_rate(rate: Optional[float], interval_hours: Optional[int]) -> Optional[float]:
    """
    Convert a per-interval funding rate to an annualized rate, assuming
    the rate held constant across all periods in a year.
 
    rate_annualized = rate * (periods per year) = rate * (8760 / interval_hours)
 
    Same null/invalid rules as normalize_rate.
    """
    if rate is None or interval_hours is None:
        return None
    if interval_hours <= 0:
        return None
 
    return rate * (HOURS_PER_YEAR / interval_hours)
 