from src.transformations.gold_funding_analysis import (
    LARGE_MOVE_THRESHOLD,
    calculate_funding_change,
    calculate_oi_change,
    calculate_price_change,
    is_frozen,
    is_large_move,
)


# calculate_funding_change
def test_calculate_funding_change():
    assert calculate_funding_change(0.00018, 0.00010) == 0.00008


def test_calculate_funding_change_negative():
    assert calculate_funding_change(0.00005, 0.00010) == -0.00005


def test_calculate_funding_change_none():
    assert calculate_funding_change(None, 0.00010) is None
    assert calculate_funding_change(0.00010, None) is None


# is_large_move
def test_is_large_move_above_threshold():
    assert is_large_move(LARGE_MOVE_THRESHOLD * 2) is True


def test_is_large_move_below_threshold():
    assert is_large_move(LARGE_MOVE_THRESHOLD / 2) is False


def test_is_large_move_at_threshold():
    assert is_large_move(LARGE_MOVE_THRESHOLD) is True


def test_is_large_move_negative():
    assert is_large_move(-LARGE_MOVE_THRESHOLD * 2) is True


def test_is_large_move_none():
    assert is_large_move(None) is None


def test_is_large_move_custom_threshold():
    assert is_large_move(0.00005, threshold=0.00010) is False
    assert is_large_move(0.00015, threshold=0.00010) is True


# is_frozen
def test_is_frozen():
    assert is_frozen(
        0.00010,
        [0.00010, 0.00010, 0.00010],
    ) is True


def test_is_not_frozen():
    assert is_frozen(
        0.00010,
        [0.00010, 0.00009, 0.00010],
    ) is False


def test_is_frozen_requires_previous_rates():
    assert is_frozen(0.00010, []) is None


def test_is_frozen_none_current_rate():
    assert is_frozen(
        None,
        [0.00010, 0.00010],
    ) is None


def test_is_frozen_with_missing_previous_rate():
    assert is_frozen(
        0.00010,
        [0.00010, None, 0.00010],
    ) is None


# calculate_oi_change
def test_calculate_oi_change():
    assert calculate_oi_change(1200.0, 1000.0) == 200.0


def test_calculate_oi_change_negative():
    assert calculate_oi_change(800.0, 1000.0) == -200.0


def test_calculate_oi_change_none():
    assert calculate_oi_change(None, 1000.0) is None
    assert calculate_oi_change(1000.0, None) is None


# calculate_price_change
def test_calculate_price_change():
    assert calculate_price_change(105000.0, 100000.0) == 5000.0


def test_calculate_price_change_negative():
    assert calculate_price_change(95000.0, 100000.0) == -5000.0


def test_calculate_price_change_none():
    assert calculate_price_change(None, 100000.0) is None
    assert calculate_price_change(100000.0, None) is None
