"""Tests for the mock controller's CSV rendering layer.

The renderer produces bytes that real `proconip` clients parse via
`GetStateData` and `GetDmxData`. The strongest assertion in here is therefore
"the parser accepts what we render and recovers what we put in" — anything
shorter than that is not really a contract test.
"""

from datetime import time as dt_time

import pytest

from proconip.definitions import GetDmxData, GetStateData
from tools.proconip_mock import drift
from tools.proconip_mock.csv_renderer import render_get_dmx, render_get_state
from tools.proconip_mock.state import MockState


def _state_at_t0() -> MockState:
    """A MockState whose elapsed time is exactly 0 — sensors at their centers."""
    clock = iter([100.0, 100.0])
    return MockState(monotonic=lambda: next(clock))


class TestGetStateRendering:
    def test_output_parses_back_to_get_state_data(self) -> None:
        s = _state_at_t0()
        csv = render_get_state(s)
        parsed = GetStateData(csv)  # no exception → schema is valid
        assert parsed.version  # SYSINFO row preserved

    def test_sensor_values_round_trip_through_parser(self) -> None:
        s = _state_at_t0()
        parsed = GetStateData(render_get_state(s))
        # At t=0 (sin = 0), centers are returned in natural units
        assert parsed.ph_electrode.value == pytest.approx(drift.PH_CENTER, abs=0.01)
        assert parsed.redox_electrode.value == pytest.approx(drift.REDOX_CENTER_MV, abs=1.0)

    def test_relay_state_round_trips(self) -> None:
        s = _state_at_t0()
        s.apply_ena(enable_mask=1, on_mask=1)  # internal relay 0 manual ON
        parsed = GetStateData(render_get_state(s))
        relay_0 = parsed.get_relay(0)
        assert relay_0.is_on()
        assert relay_0.is_manual_mode()
        # Untouched relays remain Auto (off)
        relay_1 = parsed.get_relay(1)
        assert relay_1.is_off()
        assert relay_1.is_auto_mode()

    def test_clock_value_is_packed_format(self) -> None:
        s = _state_at_t0()
        parsed = GetStateData(render_get_state(s, wall_clock=dt_time(2, 17)))
        assert parsed.time == "02:17"

    def test_drift_changes_emitted_value(self) -> None:
        # Two states with different elapsed times → different sensor values
        clock1 = iter([100.0, 100.0])
        s1 = MockState(monotonic=lambda: next(clock1))
        clock2 = iter([100.0, 100.0 + drift.PH_PERIOD_SECONDS / 4])
        s2 = MockState(monotonic=lambda: next(clock2))
        ph1 = GetStateData(render_get_state(s1)).ph_electrode.value
        ph2 = GetStateData(render_get_state(s2)).ph_electrode.value
        assert ph1 != ph2
        assert ph2 == pytest.approx(drift.PH_CENTER + drift.PH_AMPLITUDE, abs=0.005)


class TestGetDmxRendering:
    def test_zero_state(self) -> None:
        s = _state_at_t0()
        csv = render_get_dmx(s)
        assert csv.strip() == ",".join(["0"] * 16)

    def test_round_trips_through_parser(self) -> None:
        s = _state_at_t0()
        s.apply_dmx(
            channels_1_8=[0, 10, 20, 30, 40, 50, 60, 70],
            channels_9_16=[80, 90, 100, 110, 120, 130, 140, 150],
        )
        parsed = GetDmxData(render_get_dmx(s))
        assert [parsed.get_value(i) for i in range(16)] == [
            0,
            10,
            20,
            30,
            40,
            50,
            60,
            70,
            80,
            90,
            100,
            110,
            120,
            130,
            140,
            150,
        ]
