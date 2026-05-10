"""Tests for the definitions module data structures."""

import copy

import pytest

from proconip.definitions import (
    CATEGORY_ANALOG,
    CATEGORY_CANISTER,
    CATEGORY_CONSUMPTION,
    CATEGORY_DIGITAL_INPUT,
    CATEGORY_ELECTRODE,
    CATEGORY_EXTERNAL_RELAY,
    CATEGORY_RELAY,
    CATEGORY_TEMPERATURE,
    BadRelayException,
    ConfigObject,
    DataObject,
    DmxChannelData,
    GetDmxData,
    GetStateData,
    InvalidPayloadException,
    Relay,
)


def _minimal_state_csv(*, ntp_fault_state: int = 0) -> str:
    """Build a single-column SYSINFO + 5 data-row CSV for targeted parser tests.

    The full fixture in `tests/fixtures/get_state.csv` is the canonical happy-path
    payload; this helper produces a minimal, parameterizable variant for tests
    that exercise specific SYSINFO fields like the NTP fault state.
    """
    return f"SYSINFO,1.7.3,0,0,{ntp_fault_state},0,0,0,0,0\ncol\nunit\n0\n1\n0\n"


# ---------------------------------------------------------------------------
# ConfigObject
# ---------------------------------------------------------------------------


def test_config_initialization(config: ConfigObject) -> None:
    assert config.base_url == "http://127.0.0.1"
    assert config.username == "admin"
    assert config.password == "admin"


def test_config_to_dict(config: ConfigObject) -> None:
    d = config.to_dict()
    assert d == {"base_url": "http://127.0.0.1", "username": "admin", "password": "admin"}


def test_config_from_dict() -> None:
    data = {"base_url": "http://example.com", "username": "u", "password": "p"}
    obj = ConfigObject.from_dict(data)
    assert obj.base_url == "http://example.com"
    assert obj.username == "u"
    assert obj.password == "p"


@pytest.mark.parametrize("missing_key", ["base_url", "username", "password"])
def test_config_from_dict_missing_key(missing_key: str) -> None:
    data = {"base_url": "http://x", "username": "u", "password": "p"}
    del data[missing_key]
    with pytest.raises(ValueError, match=f"{missing_key} is required"):
        ConfigObject.from_dict(data)


# ---------------------------------------------------------------------------
# GetStateData — system info
# ---------------------------------------------------------------------------


def test_get_state_initialization(get_state_data: GetStateData) -> None:
    assert get_state_data is not None


def test_get_state_version(get_state_data: GetStateData) -> None:
    assert get_state_data.version == "1.7.3"


def test_get_state_cpu_time(get_state_data: GetStateData) -> None:
    assert get_state_data.cpu_time == 9559698


def test_get_state_time(get_state_data: GetStateData) -> None:
    assert get_state_data.time == "02:17"


def test_get_state_reset_root_cause(get_state_data: GetStateData) -> None:
    assert get_state_data.reset_root_cause == 1
    assert get_state_data.get_reset_root_cause_as_str() == "External reset"


def test_get_state_ntp_fault_state(get_state_data: GetStateData) -> None:
    assert get_state_data.ntp_fault_state == 3
    # value 3 = bits 1+2 → highest active bit is 2 → "Warning"
    assert get_state_data.get_ntp_fault_state_as_str() == "Warning (GUI warning, yellow)"


@pytest.mark.parametrize(
    "ntp_value,expected",
    [
        (0, "n.a."),
        (1, "Logfile (GUI warning, green)"),
        (2, "Warning (GUI warning, yellow)"),
        (4, "Error (GUI warning, red)"),
        (65536, "NTP available"),
        # composite: bits 1+2 → highest = 2
        (3, "Warning (GUI warning, yellow)"),
        # composite: bits 1+4 → highest = 4
        (5, "Error (GUI warning, red)"),
        # composite: bits 2+4 → highest = 4
        (6, "Error (GUI warning, red)"),
        # unknown high value, no known bits → n.a.
        (131072, "n.a."),
    ],
)
def test_get_ntp_fault_state_as_str_parametrized(ntp_value: int, expected: str) -> None:
    """Test NTP fault state string for various bit combinations."""
    data = GetStateData(_minimal_state_csv(ntp_fault_state=ntp_value))
    assert data.get_ntp_fault_state_as_str() == expected


def test_get_state_config_other_enable(get_state_data: GetStateData) -> None:
    assert get_state_data.config_other_enable == 0
    assert not get_state_data.is_tcpip_boost_enabled()
    assert not get_state_data.is_sd_card_enabled()
    assert not get_state_data.is_dmx_enabled()
    assert not get_state_data.is_avatar_enabled()
    assert not get_state_data.is_relay_extension_enabled()
    assert not get_state_data.is_high_bus_load_enabled()
    assert not get_state_data.is_flow_sensor_enabled()
    assert not get_state_data.is_repeated_mails_enabled()
    assert not get_state_data.is_dmx_extension_enabled()


def test_get_state_dosage_control(get_state_data: GetStateData) -> None:
    assert get_state_data.dosage_control == 257  # bits 0 + 8
    assert get_state_data.ph_plus_dosage_relay_id == 4
    assert get_state_data.ph_minus_dosage_relay_id == 4
    assert get_state_data.chlorine_dosage_relay_id == 5

    assert get_state_data.is_chlorine_dosage_enabled()
    assert not get_state_data.is_electrolysis_enabled()
    assert get_state_data.is_ph_minus_dosage_enabled()
    assert not get_state_data.is_ph_plus_dosage_enabled()


# ---------------------------------------------------------------------------
# GetStateData — category lists
# ---------------------------------------------------------------------------


def test_analog_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.analog_objects
    assert len(objs) == 5
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_ANALOG
        assert obj.category_id == idx
        assert obj.column == idx + 1


def test_electrode_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.electrode_objects
    assert len(objs) == 2
    assert get_state_data.redox_electrode in objs
    assert get_state_data.ph_electrode in objs
    assert get_state_data.redox_electrode.name == "Redox"
    assert get_state_data.ph_electrode.name == "pH"
    for obj in objs:
        assert obj.category == CATEGORY_ELECTRODE


def test_temperature_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.temperature_objects
    assert len(objs) == 8
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_TEMPERATURE
        assert obj.category_id == idx
        assert obj.column == idx + 8


def test_relay_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.relay_objects
    assert len(objs) == 8
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_RELAY
        assert obj.category_id == idx
        assert obj.column == idx + 16


def test_digital_input_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.digital_input_objects
    assert len(objs) == 4
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_DIGITAL_INPUT
        assert obj.category_id == idx
        assert obj.column == idx + 24


def test_external_relay_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.external_relay_objects
    assert len(objs) == 8
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_EXTERNAL_RELAY
        assert obj.category_id == idx
        assert obj.column == idx + 28


def test_canister_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.canister_objects
    assert len(objs) == 3
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_CANISTER
        assert obj.category_id == idx
        assert obj.column == idx + 36


def test_consumption_objects(get_state_data: GetStateData) -> None:
    objs = get_state_data.consumption_objects
    assert len(objs) == 3
    for idx, obj in enumerate(objs):
        assert obj.category == CATEGORY_CONSUMPTION
        assert obj.category_id == idx
        assert obj.column == idx + 39


def test_aggregated_relay_objects(get_state_data: GetStateData) -> None:
    assert len(get_state_data.aggregated_relay_objects) == 16


# ---------------------------------------------------------------------------
# GetStateData — dosage helpers
# ---------------------------------------------------------------------------


def test_is_dosage_enabled(get_state_data: GetStateData) -> None:
    canisters = get_state_data.canister_objects
    assert get_state_data.is_dosage_enabled(canisters[0])  # chlorine
    assert get_state_data.is_dosage_enabled(canisters[1])  # pH-
    assert not get_state_data.is_dosage_enabled(canisters[2])  # pH+ disabled

    consumptions = get_state_data.consumption_objects
    assert get_state_data.is_dosage_enabled(consumptions[0])
    assert get_state_data.is_dosage_enabled(consumptions[1])
    assert not get_state_data.is_dosage_enabled(consumptions[2])


def test_get_dosage_relay(get_state_data: GetStateData) -> None:
    assert get_state_data.get_dosage_relay(get_state_data.canister_objects[0]) == 5  # Cl
    assert get_state_data.get_dosage_relay(get_state_data.canister_objects[1]) == 4  # pH-
    assert get_state_data.get_dosage_relay(get_state_data.canister_objects[2]) == 4  # pH+
    # non-dosage object returns None
    assert get_state_data.get_dosage_relay(get_state_data.analog_objects[0]) is None


def test_is_dosage_relay_by_relay_object(get_state_data: GetStateData) -> None:
    dosage_relay = get_state_data.get_relay(5)  # chlorine dosage relay_id
    assert get_state_data.is_dosage_relay(relay_object=dosage_relay)
    non_dosage = get_state_data.get_relay(0)
    assert not get_state_data.is_dosage_relay(relay_object=non_dosage)


def test_is_dosage_relay_by_relay_id(get_state_data: GetStateData) -> None:
    assert get_state_data.is_dosage_relay(relay_id=5)
    assert get_state_data.is_dosage_relay(relay_id=4)
    assert not get_state_data.is_dosage_relay(relay_id=0)


def test_is_dosage_relay_bad_data_object_category(get_state_data: GetStateData) -> None:
    with pytest.raises(BadRelayException, match="not a relay category"):
        get_state_data.is_dosage_relay(data_object=get_state_data.analog_objects[0])


def test_is_dosage_relay_no_args(get_state_data: GetStateData) -> None:
    assert not get_state_data.is_dosage_relay()


# ---------------------------------------------------------------------------
# Relay
# ---------------------------------------------------------------------------


def test_relay_value_not_double_applied() -> None:
    """Relay must apply offset+gain exactly once, not twice.

    Uses non-trivial offset (1) so the buggy double-application would produce a
    different result. Picks raw_value=1 → computed value=2 ('manual off');
    the buggy version would compute 1 + 1*2 = 3 ('manual on'), exposing the bug.
    """
    obj = DataObject(column=16, name="test", unit="--", offset=1.0, gain=1.0, value=1.0)
    # value = offset + gain * raw = 1.0 + 1.0 * 1.0 = 2.0
    assert obj.value == pytest.approx(2.0)
    assert obj.display_value == "Off"

    relay = Relay(obj)
    # Relay must share the same computed value, NOT 1 + 1*2 = 3.
    assert relay.value == pytest.approx(2.0)
    assert relay.raw_value == pytest.approx(1.0)
    assert relay.display_value == "Off"
    assert relay.is_off()
    assert relay.is_manual_mode()


def test_relay_relay_id_internal(get_state_data: GetStateData) -> None:
    relay = get_state_data.get_relay(0)
    assert relay.relay_id == 0


def test_relay_relay_id_external(get_state_data: GetStateData) -> None:
    relay = get_state_data.get_relay(8)  # first external relay
    assert relay.relay_id == 8


def test_relay_is_off(get_state_data: GetStateData) -> None:
    # First relay raw value is 2 (manual off per fixture)
    relay = get_state_data.get_relay(0)
    assert relay.is_manual_mode()
    assert relay.is_off()
    assert not relay.is_on()
    assert not relay.is_auto_mode()


def test_relay_str(get_state_data: GetStateData) -> None:
    relay = get_state_data.get_relay(0)
    assert "Terassenlicht" in str(relay)


# ---------------------------------------------------------------------------
# DmxChannelData
# ---------------------------------------------------------------------------


def test_dmx_channel_name_leading_zero() -> None:
    ch = DmxChannelData(0, 0)
    assert ch.name == "CH01"


def test_dmx_channel_name_no_leading_zero() -> None:
    ch = DmxChannelData(9, 100)
    assert ch.name == "CH10"


def test_dmx_channel_str() -> None:
    ch = DmxChannelData(0, 42)
    assert str(ch) == "42"


# ---------------------------------------------------------------------------
# GetDmxData
# ---------------------------------------------------------------------------


def test_get_dmx_initialization(get_dmx_data: GetDmxData) -> None:
    assert get_dmx_data is not None


def test_get_dmx_post_data(get_dmx_data: GetDmxData) -> None:
    pd = get_dmx_data.post_data
    assert pd["TYPE"] == "0"
    assert pd["LEN"] == "16"
    assert pd["CH1_8"] == "0,10,20,30,40,50,60,70"
    assert pd["CH9_16"] == "80,90,100,110,120,130,140,150"
    assert pd["DMX512"] == "1"

    payload = "&".join(f"{k}={v}" for k, v in pd.items())
    assert payload == (
        "TYPE=0&LEN=16&CH1_8=0,10,20,30,40,50,60,70&CH9_16=80,90,100,110,120,130,140,150&DMX512=1"
    )


def test_get_dmx_str(get_dmx_data: GetDmxData, get_dmx_csv: str) -> None:
    assert str(get_dmx_data) == get_dmx_csv


def test_get_dmx_set_and_get(get_dmx_data: GetDmxData) -> None:
    data = copy.deepcopy(get_dmx_data)
    data.set(0, 123)
    assert data.get_value(0) == 123
    data.set(15, 200)
    assert data.get_value(15) == 200


def test_get_dmx_set_clamps_high(get_dmx_data: GetDmxData) -> None:
    data = copy.deepcopy(get_dmx_data)
    data.set(0, 1000)
    assert data.get_value(0) == 255


def test_get_dmx_set_clamps_low(get_dmx_data: GetDmxData) -> None:
    data = copy.deepcopy(get_dmx_data)
    data.set(0, -1000)
    assert data.get_value(0) == 0


def test_get_dmx_set_index_error(get_dmx_data: GetDmxData) -> None:
    with pytest.raises(IndexError):
        get_dmx_data.set(16, 0)
    with pytest.raises(IndexError):
        get_dmx_data.set(-1, 0)


def test_get_dmx_getitem(get_dmx_data: GetDmxData) -> None:
    data = copy.deepcopy(get_dmx_data)
    data.set(0, 77)
    assert data[0].value == 77


def test_get_dmx_iter(get_dmx_data: GetDmxData) -> None:
    channels = list(get_dmx_data)
    assert len(channels) == 16
    assert channels[0].value == 0
    assert channels[15].value == 150


def test_get_dmx_leading_blank_lines(get_dmx_csv: str) -> None:
    padded = "\n\n" + get_dmx_csv
    data = GetDmxData(padded)
    assert data.get_value(0) == 0
    assert data.get_value(15) == 150


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", ["", "\n", "   \n\n  "])
def test_get_dmx_empty_payload_raises(payload: str) -> None:
    with pytest.raises(InvalidPayloadException, match="DMX payload"):
        GetDmxData(payload)


@pytest.mark.parametrize("payload", ["", "\n", "SYSINFO,1.7.3,0,0,0,0,0,0,0,0\nonly_one_line"])
def test_get_state_truncated_payload_raises(payload: str) -> None:
    with pytest.raises(InvalidPayloadException, match="incomplete"):
        GetStateData(payload)


def test_get_state_mismatched_column_counts_raises() -> None:
    """Names/units/offsets/gains/values rows must all have the same column count."""
    payload = (
        "SYSINFO,1.7.3,0,0,0,0,0,0,0,0\n"
        "name1,name2\n"  # 2 columns
        "unit1,unit2,unit3\n"  # 3 columns — mismatch
        "0,0\n"
        "1,1\n"
        "10,20\n"
    )
    with pytest.raises(InvalidPayloadException, match="column counts don't line up"):
        GetStateData(payload)


@pytest.mark.parametrize("count", [0, 1, 15, 17, 32])
def test_get_dmx_wrong_channel_count_raises(count: int) -> None:
    """GetDmx.csv must contain exactly 16 comma-separated channels."""
    payload = ",".join(["0"] * count) if count else ""
    with pytest.raises(InvalidPayloadException):
        GetDmxData(payload)
