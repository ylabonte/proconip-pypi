"""Tests for the mock controller's mutable in-memory state model."""

import pytest

from tools.proconip_mock.state import MockState


class TestRelayInit:
    def test_starts_with_combined_16_bit_relay_state(self) -> None:
        s = MockState()
        # Bits 0–7 are the internal relays, 8–15 are the external relay
        # extension. The mock tracks them in one 16-element list each.
        assert len(s.relay_enabled) == 16
        assert len(s.relay_on) == 16
        assert all(not e for e in s.relay_enabled)
        assert all(not o for o in s.relay_on)


class TestApplyEnaPayload:
    def test_switching_relay_3_on(self) -> None:
        s = MockState()
        # Internal relay 3 → bit 3. ENA = "8,8" means manual+on for relay 3.
        s.apply_ena(enable_mask=8, on_mask=8)
        assert s.relay_enabled[3] is True
        assert s.relay_on[3] is True
        # Other relays untouched
        assert all(not s.relay_enabled[i] for i in range(16) if i != 3)

    def test_switching_relay_3_off_manual(self) -> None:
        s = MockState()
        s.apply_ena(enable_mask=8, on_mask=0)  # manual off
        assert s.relay_enabled[3] is True
        assert s.relay_on[3] is False

    def test_setting_relay_3_to_auto(self) -> None:
        s = MockState()
        s.apply_ena(enable_mask=8, on_mask=8)  # first manually on
        s.apply_ena(enable_mask=0, on_mask=0)  # then auto
        assert s.relay_enabled[3] is False
        assert s.relay_on[3] is False

    def test_external_relays_use_high_bits(self) -> None:
        s = MockState()
        # External relay 0 = aggregated 8 → bit 8 → mask 256
        s.apply_ena(enable_mask=256, on_mask=256)
        assert s.relay_enabled[8] is True
        assert s.relay_on[8] is True


class TestRelayValueForCsv:
    """The CSV row encodes per-relay state as 0=Auto-off, 1=Auto-on, 2=Off, 3=On.

    All four are reachable depending on the incoming ENA payload.
    """

    def test_auto_off_is_default(self) -> None:
        s = MockState()
        assert s.csv_relay_value(0) == 0

    def test_auto_on_when_only_on_bit_is_set(self) -> None:
        # Clients preserving an Auto-on relay via determine_overall_relay_bit_state()
        # can POST `ENA=0,<bit>` — the mock must round-trip this back as 1.
        s = MockState()
        s.apply_ena(enable_mask=0, on_mask=1)
        assert s.csv_relay_value(0) == 1

    def test_manual_off(self) -> None:
        s = MockState()
        s.apply_ena(enable_mask=1, on_mask=0)
        assert s.csv_relay_value(0) == 2

    def test_manual_on(self) -> None:
        s = MockState()
        s.apply_ena(enable_mask=1, on_mask=1)
        assert s.csv_relay_value(0) == 3


class TestDmxState:
    def test_starts_at_zero(self) -> None:
        s = MockState()
        assert s.dmx == [0] * 16

    def test_apply_dmx_payload_updates_channels(self) -> None:
        s = MockState()
        s.apply_dmx(channels_1_8=[10, 20, 30, 40, 50, 60, 70, 80], channels_9_16=[0] * 8)
        assert s.dmx[:8] == [10, 20, 30, 40, 50, 60, 70, 80]
        assert s.dmx[8:] == [0] * 8

    def test_apply_dmx_clamps_out_of_range(self) -> None:
        s = MockState()
        s.apply_dmx(channels_1_8=[-5, 999, 0, 0, 0, 0, 0, 0], channels_9_16=[0] * 8)
        assert s.dmx[0] == 0  # clamped from -5
        assert s.dmx[1] == 255  # clamped from 999

    def test_apply_dmx_rejects_wrong_length(self) -> None:
        s = MockState()
        with pytest.raises(ValueError):
            s.apply_dmx(channels_1_8=[1, 2, 3], channels_9_16=[0] * 8)


class TestElapsedSeconds:
    def test_returns_seconds_since_creation(self) -> None:
        # Inject a fake clock so the test is deterministic
        clock = iter([1000.0, 1003.5])
        s = MockState(monotonic=lambda: next(clock))
        # Constructor consumes 1000.0 as t0, next call yields elapsed
        assert s.elapsed_seconds() == pytest.approx(3.5)
