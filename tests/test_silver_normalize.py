"""
Tests for src/transformations/normalize.py.

normalize_rate(rate, interval_hours) -> float | None
annualize_rate(rate, interval_hours) -> float | None

Both convert a per-interval funding rate to a comparable basis. Both
return None when input is missing or business-invalid (e.g., interval_hours <= 0).
"""

import pytest
from src.transformations.silver_normalize import normalize_rate, annualize_rate


class TestNormalizeRateHappyPath:
    def test_8h_interval_is_unchanged(self):
        assert normalize_rate(0.0001, 8) == pytest.approx(0.0001)

    def test_1h_interval_scales_up(self):
        assert normalize_rate(0.0000125, 1) == pytest.approx(0.0001)

    def test_4h_interval_scales_up(self):
        assert normalize_rate(0.00005, 4) == pytest.approx(0.0001)


class TestNormalizeRateValidEdgeValues:
    def test_negative_rate_is_preserved(self):
        assert normalize_rate(-0.00003, 8) == pytest.approx(-0.00003)

    def test_zero_rate_returns_zero_not_none(self):
        assert normalize_rate(0.0, 8) == pytest.approx(0.0)


class TestNormalizeRateMissingOrInvalidInputs:
    def test_none_rate_returns_none(self):
        assert normalize_rate(None, 8) is None

    def test_none_interval_returns_none(self):
        assert normalize_rate(0.0001, None) is None

    def test_zero_interval_returns_none(self):
        assert normalize_rate(0.0001, 0) is None

    def test_negative_interval_returns_none(self):
        assert normalize_rate(0.0001, -8) is None

    def test_both_none_returns_none(self):
        assert normalize_rate(None, None) is None


class TestAnnualizeRateHappyPath:
    def test_8h_interval_baseline(self):
        # 0.0001 per 8h * 1095 periods/yr (8760/8) = 0.10950
        assert annualize_rate(0.0001, 8) == pytest.approx(0.1095, rel=1e-4)

    def test_1h_interval_matches_equivalent_8h_rate(self):
        # 0.0000125 per 1h should annualize the same as 0.0001 per 8h
        assert annualize_rate(0.0000125, 1) == pytest.approx(
            annualize_rate(0.0001, 8), rel=1e-6
        )

    def test_4h_interval_matches_equivalent_8h_rate(self):
        assert annualize_rate(0.00005, 4) == pytest.approx(
            annualize_rate(0.0001, 8), rel=1e-6
        )


class TestAnnualizeRateValidEdgeValues:
    def test_negative_rate_is_preserved(self):
        assert annualize_rate(-0.00003, 8) < 0

    def test_zero_rate_returns_zero_not_none(self):
        assert annualize_rate(0.0, 8) == pytest.approx(0.0)


class TestAnnualizeRateMissingOrInvalidInputs:
    def test_none_rate_returns_none(self):
        assert annualize_rate(None, 8) is None

    def test_none_interval_returns_none(self):
        assert annualize_rate(0.0001, None) is None

    def test_zero_interval_returns_none(self):
        assert annualize_rate(0.0001, 0) is None

    def test_negative_interval_returns_none(self):
        assert annualize_rate(0.0001, -8) is None

    def test_both_none_returns_none(self):
        assert annualize_rate(None, None) is None
