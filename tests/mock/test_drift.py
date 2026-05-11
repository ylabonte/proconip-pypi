"""Tests for the mock controller's sensor drift functions."""

import math

import pytest

from tools.proconip_mock import drift


class TestPhDrift:
    def test_at_t_zero_is_center(self) -> None:
        assert drift.ph(0.0) == pytest.approx(7.40)

    def test_stays_within_safe_band(self) -> None:
        for t in range(0, 7200, 7):
            assert 7.30 <= drift.ph(float(t)) <= 7.50

    def test_completes_one_cycle_per_period(self) -> None:
        period = drift.PH_PERIOD_SECONDS
        assert drift.ph(period) == pytest.approx(7.40, abs=1e-9)
        assert drift.ph(period / 4) == pytest.approx(7.40 + 0.10, abs=1e-9)


class TestRedoxDrift:
    def test_at_t_zero_is_center(self) -> None:
        assert drift.redox_mv(0.0) == pytest.approx(700.0)

    def test_stays_within_who_band(self) -> None:
        for t in range(0, 7200, 7):
            assert 675 <= drift.redox_mv(float(t)) <= 725


class TestCpuTempDrift:
    def test_at_t_zero_is_center(self) -> None:
        assert drift.cpu_temp_c(0.0) == pytest.approx(30.0)

    def test_stays_within_realistic_range(self) -> None:
        for t in range(0, 36000, 60):
            assert 28.0 <= drift.cpu_temp_c(float(t)) <= 32.0


class TestPumpFlow:
    def test_at_t_zero_is_center(self) -> None:
        assert drift.pump_flow_cm_s(0.0) == pytest.approx(7.0)

    def test_stays_within_band(self) -> None:
        for t in range(0, 600):
            assert 6.7 <= drift.pump_flow_cm_s(float(t)) <= 7.3


class TestPackedTime:
    def test_zero_seconds(self) -> None:
        assert drift.packed_clock_value(hour=0, minute=0) == 0

    def test_morning(self) -> None:
        # 02:17 is the value in the fixture (raw 529 = 2*256 + 17)
        assert drift.packed_clock_value(hour=2, minute=17) == 529

    def test_evening(self) -> None:
        # 23:59 is the maximum daily value the controller emits
        assert drift.packed_clock_value(hour=23, minute=59) == 23 * 256 + 59


class TestSensorsBundle:
    def test_returns_all_sensors(self) -> None:
        sensors = drift.sensors(elapsed_seconds=0.0)
        assert sensors == {
            "ph": pytest.approx(7.40),
            "redox_mv": pytest.approx(700.0),
            "cpu_temp_c": pytest.approx(30.0),
            "pump_flow_cm_s": pytest.approx(7.0),
        }

    def test_advances_with_time(self) -> None:
        # Quarter pH period gives the peak
        s = drift.sensors(elapsed_seconds=drift.PH_PERIOD_SECONDS / 4)
        assert s["ph"] == pytest.approx(7.40 + 0.10, abs=1e-9)

    def test_uses_sin_phase_zero_at_origin(self) -> None:
        # Sanity: every sensor uses sin so at t=0 must equal its center
        s = drift.sensors(elapsed_seconds=0.0)
        # Confirm we're not accidentally using cos
        assert s["ph"] == pytest.approx(7.40)
        assert s["redox_mv"] == pytest.approx(700.0)
        # And a tiny tick later, all values move
        s2 = drift.sensors(elapsed_seconds=1.0)
        assert s2["pump_flow_cm_s"] != pytest.approx(7.0, abs=1e-12)
        # Confirm sin shape: derivative at zero is positive for all (since sin(t/p))
        assert s2["ph"] > 7.40
        assert s2["redox_mv"] > 700.0
        assert s2["cpu_temp_c"] > 30.0
        assert s2["pump_flow_cm_s"] > 7.0
        # Cross-check expected sign with explicit computation
        assert s2["ph"] == pytest.approx(
            7.40 + 0.10 * math.sin(2.0 * math.pi * 1.0 / drift.PH_PERIOD_SECONDS)
        )
