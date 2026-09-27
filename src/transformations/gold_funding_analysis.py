"""
Gold-layer funding-rate analysis.

Transforms Silver funding-rate observations into analytical features
for cross-exchange funding-rate analysis.

Input grain:
    (exchange, symbol, fetched_at)

Derived features:
    - funding_change: poll-to-poll change in normalized funding rate
    - is_large_move: whether funding_change exceeds the configured threshold
    - is_frozen: whether funding rate has remained unchanged across
      consecutive observations
    - oi_change: poll-to-poll change in open interest
    - price_change: poll-to-poll change in mark price
"""

from typing import Optional


LARGE_MOVE_THRESHOLD = 0.00008  # 99th percentile of absolute poll-to-poll funding change


def calculate_funding_change(
    current_rate: Optional[float],
    previous_rate: Optional[float],
) -> Optional[float]:
    """Calculate poll-to-poll funding-rate change."""
    if current_rate is None or previous_rate is None:
        return None

    return current_rate - previous_rate


def is_large_move(
    funding_change: Optional[float],
    threshold: float = LARGE_MOVE_THRESHOLD,
) -> Optional[bool]:
    """Flag funding changes that exceed the configured absolute threshold."""
    if funding_change is None:
        return None

    return abs(funding_change) >= threshold


def is_frozen(
    current_rate: Optional[float],
    previous_rates: list[Optional[float]],
) -> Optional[bool]:
    """
    Determine whether the funding rate has remained unchanged
    across the provided consecutive observations.
    """
    if current_rate is None or not previous_rates:
        return None

    if any(rate is None for rate in previous_rates):
        return None

    return all(rate == current_rate for rate in previous_rates)


def calculate_oi_change(
    current_oi: Optional[float],
    previous_oi: Optional[float],
) -> Optional[float]:
    """Calculate poll-to-poll change in open interest."""
    if current_oi is None or previous_oi is None:
        return None

    return current_oi - previous_oi


def calculate_price_change(
    current_price: Optional[float],
    previous_price: Optional[float],
) -> Optional[float]:
    """Calculate poll-to-poll change in mark price."""
    if current_price is None or previous_price is None:
        return None

    return current_price - previous_price
