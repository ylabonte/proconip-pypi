"""Data structures for the ProCon.IP CSV and form-encoded HTTP APIs.

This module contains everything that's needed to describe the controller's
data shape without making any network calls — typed wrappers around the CSV
responses, helpers for the bit-field flags they encode, and a few small
exceptions that get raised when something is malformed.

Path constants (`API_PATH_*`) and category strings (`CATEGORY_*`) are exposed
because the rest of the library and downstream callers (notably a Home
Assistant integration) build on them.

The classes you will most often work with are:

- `ConfigObject` — base URL plus credentials.
- `GetStateData` — parsed `/GetState.csv` response. Exposes individual sensors,
  relays, dosage flags, and a few derived helpers.
- `Relay` — convenience wrapper around a relay `DataObject` with on/off and
  manual/auto interrogation methods.
- `GetDmxData` / `DmxChannelData` — parsed and mutable representation of the
  16 DMX channels.
"""

from collections.abc import Iterator
from enum import IntEnum

API_PATH_GET_STATE = "/GetState.csv"
API_PATH_USRCFG = "/usrcfg.cgi"
API_PATH_COMMAND = "/Command.htm"
API_PATH_GET_DMX = "/GetDmx.csv"

EXTERNAL_RELAY_ID_OFFSET = 8
"""Offset added to a relay's `category_id` to form its aggregated relay ID
when it lives on the optional external relay extension. Internal relays
occupy aggregated IDs 0–7, external relays 8–15."""

CATEGORY_TIME = "time"
CATEGORY_ANALOG = "analog"
CATEGORY_ELECTRODE = "electrode"
CATEGORY_TEMPERATURE = "temperature"
CATEGORY_RELAY = "relay"
CATEGORY_DIGITAL_INPUT = "digital_input"
CATEGORY_EXTERNAL_RELAY = "external_relay"
CATEGORY_CANISTER = "canister"
CATEGORY_CONSUMPTION = "consumption"

RESET_ROOT_CAUSE = {
    0: "n.a.",
    1: "External reset",
    2: "PowerUp reset",
    4: "Brown out reset",
    8: "Watchdog reset",
    16: "SW reset",
}
"""Lookup table mapping the controller's reset-root-cause code to a human
label. The codes are exact values, not bit flags."""

NTP_FAULT_STATE = {
    0: "n.a.",
    1: "Logfile (GUI warning, green)",
    2: "Warning (GUI warning, yellow)",
    4: "Error (GUI warning, red)",
    65536: "NTP available",
}
"""Lookup table mapping NTP fault state codes to human labels. Values 1, 2
and 4 are severity bit flags that may also appear in combination; the bit
65536 indicates "NTP synchronisation reached" and is set independently."""


class DosageTarget(IntEnum):
    """Identifies which dosing pump a manual dosage command should engage.

    The numeric values match the controller's `MAN_DOSAGE` query parameter,
    so this enum can be used directly in URL building.
    """

    CHLORINE = 0
    PH_MINUS = 1
    PH_PLUS = 2


class ConfigObject:
    """Base URL and credentials for talking to a single ProCon.IP controller.

    Instances are plain holders — no network connection is opened until they
    are passed into one of the API helpers in `proconip.api`.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        """Build a config from explicit values.

        Args:
            base_url: Root URL of the controller, e.g. ``http://192.168.1.50``.
                The library appends the API paths itself; do not include them
                here. Plain HTTP is normal — these controllers are LAN-only.
            username: HTTP Basic auth username (controller default: ``admin``).
            password: HTTP Basic auth password (controller default: ``admin``).
        """
        self.base_url = base_url
        self.username = username
        self.password = password

    @staticmethod
    def from_dict(data: dict[str, str]) -> "ConfigObject":
        """Build a `ConfigObject` from a serialized dictionary.

        Useful for restoring a config that was previously written out via
        `to_dict` (e.g. into a Home Assistant config entry).

        Args:
            data: A dict containing the keys ``base_url``, ``username``, and
                ``password``. All three are required.

        Returns:
            A new `ConfigObject` populated from the dict.

        Raises:
            ValueError: If any of the required keys is missing. The exception
                message names the missing key.
        """
        if "base_url" not in data:
            raise ValueError("base_url is required")
        if "username" not in data:
            raise ValueError("username is required")
        if "password" not in data:
            raise ValueError("password is required")
        return ConfigObject(data["base_url"], data["username"], data["password"])

    def to_dict(self) -> dict[str, str]:
        """Return a plain dict copy of the config, suitable for serialization.

        The password is stored in the clear — encrypt the dict yourself if it
        will be persisted somewhere readable.
        """
        return {
            "base_url": self.base_url,
            "username": self.username,
            "password": self.password,
        }


class DataObject:
    """A single sensor, relay, canister, or consumption channel from `/GetState.csv`.

    Each `DataObject` represents one column of the CSV response, combining the
    name, unit, offset, gain, and raw value rows that the controller sends. The
    column index alone determines which category the object falls into (analog,
    relay, temperature, …) — see the constructor for the exact ranges.

    The actual physical reading is computed once at construction via
    ``offset + gain * raw_value`` and exposed as `value`. A pre-formatted
    `display_value` string is also produced; for relay columns it is one of
    "Auto (off)", "Auto (on)", "Off", or "On".
    """

    _column: int
    _category: str
    _category_id: int
    _name: str
    _unit: str
    _offset: float
    _gain: float
    _raw_value: float
    _value: float
    _display_value: str

    def __init__(
        self,
        column: int,
        name: str,
        unit: str,
        offset: float,
        gain: float,
        value: float,
    ):
        """Build a `DataObject` from one column's worth of CSV data.

        Args:
            column: Zero-based column index in the CSV. Determines the category:
                ``0`` → time, ``1–5`` → analog, ``6–7`` → electrode, ``8–15`` →
                temperature, ``16–23`` → relay, ``24–27`` → digital input,
                ``28–35`` → external relay, ``36–38`` → canister, ``39–41`` →
                consumption. Anything outside this range falls into a sentinel
                "uncategorized" bucket.
            name: Sensor name as reported by the controller (e.g. ``"Redox"``).
            unit: Unit string (``"mV"``, ``"°C"``, ``"%"``, ``"--"``, …).
            offset: Calibration offset applied to ``value``.
            gain: Calibration gain applied to ``value``.
            value: Raw sensor value before calibration. Stored verbatim as
                `raw_value`; the physical `value` is computed as
                ``offset + gain * raw_value``.
        """
        self._column = column
        self._name = name
        self._unit = unit
        self._offset = offset
        self._gain = gain
        self._raw_value = value
        self._value = self._offset + (self._gain * self._raw_value)

        if column == 0:
            self._category = CATEGORY_TIME
            self._category_id = 0
            self._display_value = f"{int(self._value / 256):02d}:{int(self._value) % 256:02d}"
        elif 1 <= column <= 5:
            self._category = CATEGORY_ANALOG
            self._category_id = column - 1
            self._display_value = f"{self._value:.2f} {self._unit}"
        elif 6 <= column <= 7:
            self._category = CATEGORY_ELECTRODE
            self._category_id = column - 6
            self._display_value = f"{self._value:.2f} {self._unit}"
        elif 8 <= column <= 15:
            self._category = CATEGORY_TEMPERATURE
            self._category_id = column - 8
            self._display_value = f"{self._value:.2f} °{self._unit}"
        elif 16 <= column <= 23:
            self._category = CATEGORY_RELAY
            self._category_id = column - 16
            self._display_value = self._relay_state()
        elif 24 <= column <= 27:
            self._category = CATEGORY_DIGITAL_INPUT
            self._category_id = column - 24
            self._display_value = f"{self._value}"
        elif 28 <= column <= 35:
            self._category = CATEGORY_EXTERNAL_RELAY
            self._category_id = column - 28
            self._display_value = self._relay_state()
        elif 36 <= column <= 38:
            self._category = CATEGORY_CANISTER
            self._category_id = column - 36
            self._display_value = f"{self._value:.2f} {self._unit}"
        elif 39 <= column <= 41:
            self._category = CATEGORY_CONSUMPTION
            self._category_id = column - 39
            self._display_value = f"{self._value:.2f} {self._unit}"
        else:
            self._category = ""
            self._category_id = -1
            self._display_value = f"{self._value}"

    def __str__(self) -> str:
        """Return a short ``"name (unit): value"`` representation."""
        return f"{self._name} ({self._unit}): {self._value}"

    def _relay_state(self) -> str:
        """Render the current relay value as one of the four state strings.

        Raises:
            ValueError: If `self._value` is not one of the four valid relay
                states (0, 1, 2, 3). Indicates a malformed CSV payload.
        """
        match self._value:
            case 0:
                return "Auto (off)"
            case 1:
                return "Auto (on)"
            case 2:
                return "Off"
            case 3:
                return "On"
            case _:
                raise ValueError(f"Unexpected relay value {self._value}")

    @property
    def name(self) -> str:
        """Sensor name as reported by the controller."""
        return self._name

    @property
    def unit(self) -> str:
        """Unit string (e.g. ``"mV"``, ``"°C"``, ``"%"``)."""
        return self._unit

    @property
    def offset(self) -> float:
        """Calibration offset applied when computing `value` from `raw_value`."""
        return self._offset

    @property
    def gain(self) -> float:
        """Calibration gain applied when computing `value` from `raw_value`."""
        return self._gain

    @property
    def raw_value(self) -> float:
        """Raw value as received from the controller, before calibration."""
        return self._raw_value

    @property
    def value(self) -> float:
        """Physical value: ``offset + gain * raw_value``."""
        return self._value

    @property
    def display_value(self) -> str:
        """Pre-formatted human-readable string for display.

        For sensors this is ``value`` rendered with its unit and two decimal
        places. For relay columns it is one of "Auto (off)", "Auto (on)",
        "Off", or "On". For column 0 (the system time field) it is "HH:MM".
        """
        return self._display_value

    @property
    def column(self) -> int:
        """Zero-based column index this object came from in the raw CSV."""
        return self._column

    @property
    def category(self) -> str:
        """One of the `CATEGORY_*` constants identifying the entity type."""
        return self._category

    @property
    def category_id(self) -> int:
        """Zero-based index of this object within its category.

        For example, the third temperature sensor has ``category_id == 2``.
        Use `Relay.relay_id` instead if you need the aggregated relay ID
        across both the internal and external relay banks.
        """
        return self._category_id


class Relay(DataObject):
    """A `DataObject` with extra methods for interrogating a relay's state.

    Relay state is encoded in two bits of the underlying `value`:

    - bit 0 — output level (0 = off, 1 = on)
    - bit 1 — control mode (0 = auto, 1 = manual)

    The four valid combinations correspond to the four `display_value`
    strings from `DataObject._relay_state`.

    Construct one by passing the `DataObject` you got from
    `GetStateData.relay_objects` (or `external_relay_objects`); the relay's
    column, name, calibration, and raw value are copied across so the
    physical value is computed exactly once. ``GetStateData.get_relay()`` is
    a shorthand that does this for you.
    """

    def __init__(self, data_object: DataObject):
        """Wrap an existing relay `DataObject`.

        Args:
            data_object: A `DataObject` produced by parsing a `/GetState.csv`
                response. It should be in the relay or external_relay
                category, but no check is enforced — passing a non-relay
                object yields a `Relay` whose interrogation methods will
                still run but produce meaningless results.
        """
        super().__init__(
            data_object.column,
            data_object.name,
            data_object.unit,
            data_object.offset,
            data_object.gain,
            data_object.raw_value,  # pass raw value so offset+gain are applied exactly once
        )

    def __str__(self) -> str:
        """Return ``"name: state"`` (e.g. ``"Pumpe: Auto (off)"``)."""
        return f"{self._name}: {self._display_value}"

    @property
    def relay_id(self) -> int:
        """Aggregated relay ID across internal and external banks.

        Internal relays return ``category_id`` directly (0–7); external
        relays return ``category_id + EXTERNAL_RELAY_ID_OFFSET`` (8–15). This
        ID matches the index used by `GetStateData.aggregated_relay_objects`
        and `RelaySwitch.async_switch_*`.
        """
        offset = EXTERNAL_RELAY_ID_OFFSET if self.category == CATEGORY_EXTERNAL_RELAY else 0
        return self.category_id + offset

    def is_on(self) -> bool:
        """True if bit 0 of the relay value is set (output enabled)."""
        return int(self._value) & 1 == 1

    def is_off(self) -> bool:
        """True if bit 0 of the relay value is clear (output disabled)."""
        return not self.is_on()

    def is_manual_mode(self) -> bool:
        """True if bit 1 of the relay value is set (overridden by manual ENA)."""
        return int(self._value) & 2 == 2

    def is_auto_mode(self) -> bool:
        """True if bit 1 of the relay value is clear (controller-driven)."""
        return not self.is_manual_mode()

    def get_bit_mask(self) -> int:
        """Bit mask for this relay in the 16-bit ENA / state field.

        Internal relays occupy bits 0–7, external relays 8–15. The mask
        returned here is suitable for OR-ing into the
        `determine_overall_relay_bit_state` output before sending an ENA
        update.
        """
        if self._category == CATEGORY_EXTERNAL_RELAY:
            return 1 << (self._category_id + EXTERNAL_RELAY_ID_OFFSET)
        return 1 << self._category_id


class GetStateData:
    """Parsed representation of a single `/GetState.csv` response.

    The CSV the controller returns has six lines: SYSINFO, names, units,
    offsets, gains, and raw values. The constructor parses all six and
    builds a list of `DataObject` instances, then groups them by category
    for easy lookup.

    Once constructed, an instance is read-only — it represents a snapshot.
    Re-fetch and reconstruct the object whenever you need fresh data.

    All public properties on this class are populated eagerly at construction
    time, so accessing them is cheap.
    """

    _time: str
    _version: str
    _cpu_time: int
    _reset_root_cause: int
    _ntp_fault_state: int
    _config_other_enable: int
    _dosage_control: int
    _ph_plus_dosage_relay_id: int
    _ph_minus_dosage_relay_id: int
    _chlorine_dosage_relay_id: int
    _data_objects: list[DataObject]
    _analog_objects: list[DataObject]
    _electrode_objects: list[DataObject]
    _temperature_objects: list[DataObject]
    _relay_objects: list[DataObject]
    _digital_input_objects: list[DataObject]
    _external_relay_objects: list[DataObject]
    _canister_objects: list[DataObject]
    _consumption_objects: list[DataObject]

    def __init__(self, raw_data: str):
        """Parse a `/GetState.csv` body into structured data.

        Args:
            raw_data: The raw multi-line CSV string returned by the
                controller. Leading blank lines are tolerated.

        Raises:
            InvalidPayloadException: If the payload is empty or has fewer
                than six non-blank lines (which means it cannot contain the
                full SYSINFO + names + units + offsets + gains + values
                rows).
            ValueError: If any of the numeric rows contains a value that is
                not parseable as a float.
        """
        self._raw_data = raw_data

        line = 0
        lines = raw_data.splitlines()
        while line < len(lines) and len(lines[line].strip()) < 1:
            line += 1
        if len(lines) < line + 6:
            raise InvalidPayloadException(
                f"GetState.csv payload is incomplete: expected at least 6 non-blank lines, "
                f"got {len(lines) - line}"
            )
        self._system_info = lines[line].split(",")
        self._data_names = lines[line + 1].split(",")
        self._data_units = lines[line + 2].split(",")
        self._data_offsets = [float(v) for v in lines[line + 3].split(",")]
        self._data_gain = [float(v) for v in lines[line + 4].split(",")]
        self._data_raw_values = [float(v) for v in lines[line + 5].split(",")]

        self._parse_system_info()
        self._parse()
        self._time = self._data_objects[0].display_value

    def __str__(self) -> str:
        """Return the original raw CSV as it was received."""
        return self._raw_data

    def _parse_system_info(self) -> None:
        """Populate the system-level attributes from the SYSINFO line."""
        self._version = self._system_info[1]
        self._cpu_time = int(self._system_info[2])
        self._reset_root_cause = int(self._system_info[3])
        self._ntp_fault_state = int(self._system_info[4])
        self._config_other_enable = int(self._system_info[5])
        self._dosage_control = int(self._system_info[6])
        self._ph_plus_dosage_relay_id = int(self._system_info[7])
        self._ph_minus_dosage_relay_id = int(self._system_info[8])
        self._chlorine_dosage_relay_id = int(self._system_info[9])

    @property
    def time(self) -> str:
        """Controller's current local time as ``"HH:MM"``."""
        return self._time

    @property
    def version(self) -> str:
        """Firmware version string reported by the controller."""
        return self._version

    @property
    def cpu_time(self) -> int:
        """Controller CPU uptime in seconds since the last reset."""
        return self._cpu_time

    @property
    def reset_root_cause(self) -> int:
        """Numeric reset-root-cause code. Decode with `RESET_ROOT_CAUSE` or
        `get_reset_root_cause_as_str`."""
        return self._reset_root_cause

    @property
    def ntp_fault_state(self) -> int:
        """Numeric NTP fault state. Decode with `NTP_FAULT_STATE` or
        `get_ntp_fault_state_as_str`. Bits 0/1/2 indicate severity (logfile,
        warning, error); bit 16 indicates "NTP available"."""
        return self._ntp_fault_state

    @property
    def config_other_enable(self) -> int:
        """Misc configuration flags. Use the `is_*_enabled` methods to query
        individual bits (TCP/IP boost, SD card, DMX, …)."""
        return self._config_other_enable

    @property
    def dosage_control(self) -> int:
        """Dosage configuration flags. Use the `is_*_dosage_enabled` and
        `is_electrolysis_enabled` methods to query individual bits."""
        return self._dosage_control

    @property
    def ph_plus_dosage_relay_id(self) -> int:
        """Aggregated relay ID configured to act as the pH+ dosing pump."""
        return self._ph_plus_dosage_relay_id

    @property
    def ph_minus_dosage_relay_id(self) -> int:
        """Aggregated relay ID configured to act as the pH- dosing pump."""
        return self._ph_minus_dosage_relay_id

    @property
    def chlorine_dosage_relay_id(self) -> int:
        """Aggregated relay ID configured to act as the chlorine dosing pump."""
        return self._chlorine_dosage_relay_id

    def is_chlorine_dosage_enabled(self) -> bool:
        """True if chlorine dosage control is enabled in the controller config (bit 0)."""
        return self._dosage_control & 1 == 1

    def is_electrolysis_enabled(self) -> bool:
        """True if electrolysis (saltwater) chlorination is enabled (bit 4)."""
        return self._dosage_control & 16 == 16

    def is_ph_minus_dosage_enabled(self) -> bool:
        """True if pH- dosage control is enabled in the controller config (bit 8)."""
        return self._dosage_control & 256 == 256

    def is_ph_plus_dosage_enabled(self) -> bool:
        """True if pH+ dosage control is enabled in the controller config (bit 12)."""
        return self._dosage_control & 4096 == 4096

    def is_dosage_enabled(self, data_entity: DataObject) -> bool:
        """Convenience: is the dosage chemical for this canister/consumption entity enabled?

        Args:
            data_entity: A canister (column 36–38) or consumption (column 39–41)
                `DataObject`. The chemical is inferred from the column index.

        Returns:
            True if the corresponding ``is_*_dosage_enabled`` flag is set.
            False for any other column (or if the chemical is disabled).
        """
        col = data_entity.column
        if col in (36, 39):
            return self.is_chlorine_dosage_enabled()
        if col in (37, 40):
            return self.is_ph_minus_dosage_enabled()
        if col in (38, 41):
            return self.is_ph_plus_dosage_enabled()
        return False

    def get_dosage_relay(self, data_entity: DataObject) -> int | None:
        """Aggregated relay ID that handles the dosing for this canister/consumption entity.

        Args:
            data_entity: A canister (column 36–38) or consumption (column 39–41)
                `DataObject`.

        Returns:
            The aggregated relay ID (chlorine, pH-, or pH+) corresponding to
            the entity's chemical, or ``None`` if the entity is not a
            canister/consumption object.
        """
        col = data_entity.column
        if col in (36, 39):
            return self._chlorine_dosage_relay_id
        if col in (37, 40):
            return self._ph_minus_dosage_relay_id
        if col in (38, 41):
            return self._ph_plus_dosage_relay_id
        return None

    def is_dosage_relay(
        self,
        relay_object: Relay | None = None,
        data_object: DataObject | None = None,
        relay_id: int | None = None,
    ) -> bool:
        """Check whether a relay is one of the configured dosage control relays.

        Provide one of `relay_object`, `data_object`, or `relay_id`. If more
        than one is supplied, the first non-None argument in that precedence
        order wins and the others are ignored. If none are provided the
        method returns False.

        Args:
            relay_object: A `Relay` instance. Highest-precedence argument.
            data_object: A `DataObject` of category `relay` or
                `external_relay`. Considered only when `relay_object` is None.
            relay_id: An aggregated relay ID (0–15). Considered only when
                both `relay_object` and `data_object` are None.

        Returns:
            True if the resolved argument identifies a dosage relay; False
            otherwise (including when no argument is provided).

        Raises:
            BadRelayException: If ``data_object`` is the resolved argument
                but is not a relay-category `DataObject`.

        Example:
            ```python
            # Three equivalent ways to ask "is relay 5 a dosage relay?",
            # assuming the chlorine pump is configured there.
            state.is_dosage_relay(relay_id=5)
            state.is_dosage_relay(relay_object=state.get_relay(5))
            state.is_dosage_relay(data_object=state.aggregated_relay_objects[5])
            ```
        """
        dosage_control_relays = [
            self._chlorine_dosage_relay_id,
            self._ph_minus_dosage_relay_id,
            self._ph_plus_dosage_relay_id,
        ]
        if relay_object is not None:
            return relay_object.relay_id in dosage_control_relays
        if data_object is not None:
            if data_object.category not in (CATEGORY_RELAY, CATEGORY_EXTERNAL_RELAY):
                raise BadRelayException(
                    f"DataObject category '{data_object.category}' is not a relay category"
                )
            offset = (
                EXTERNAL_RELAY_ID_OFFSET if data_object.category == CATEGORY_EXTERNAL_RELAY else 0
            )
            return data_object.category_id + offset in dosage_control_relays
        if relay_id is not None:
            return relay_id in dosage_control_relays
        return False

    def get_reset_root_cause_as_str(self) -> str:
        """Decode `reset_root_cause` to its `RESET_ROOT_CAUSE` label.

        Falls back to the "n.a." label for any value not in the lookup table.
        """
        if self._reset_root_cause not in RESET_ROOT_CAUSE:
            return RESET_ROOT_CAUSE[0]
        return RESET_ROOT_CAUSE[self._reset_root_cause]

    def get_ntp_fault_state_as_str(self) -> str:
        """Decode `ntp_fault_state` to a human-readable label from `NTP_FAULT_STATE`.

        For exact matches in the lookup table (``0``, ``1``, ``2``, ``4``,
        ``65536``) the corresponding label is returned. Composite states are
        approximated by returning the highest-severity active bit (4 → 2 →
        1), since the controller's CSV has no fixed combinations beyond the
        listed ones. Falls back to "n.a." if no severity bit is set.
        """
        if self._ntp_fault_state in NTP_FAULT_STATE:
            return NTP_FAULT_STATE[self._ntp_fault_state]
        for bit in (4, 2, 1):
            if self._ntp_fault_state & bit:
                return NTP_FAULT_STATE[bit]
        return NTP_FAULT_STATE[0]

    def is_tcpip_boost_enabled(self) -> bool:
        """True if TCP/IP boost is enabled in the controller config (bit 0)."""
        return self._config_other_enable & 1 == 1

    def is_sd_card_enabled(self) -> bool:
        """True if SD card logging is enabled in the controller config (bit 1)."""
        return self._config_other_enable & 2 == 2

    def is_dmx_enabled(self) -> bool:
        """True if DMX output is enabled in the controller config (bit 2)."""
        return self._config_other_enable & 4 == 4

    def is_avatar_enabled(self) -> bool:
        """True if the avatar feature is enabled in the controller config (bit 3)."""
        return self._config_other_enable & 8 == 8

    def is_relay_extension_enabled(self) -> bool:
        """True if the external relay extension module is connected and active (bit 4).

        Affects how `determine_overall_relay_bit_state` builds the ENA mask:
        with the extension active, the mask covers all 16 bits instead of
        just the internal 8.
        """
        return self._config_other_enable & 16 == 16

    def is_high_bus_load_enabled(self) -> bool:
        """True if high bus load mode is enabled in the controller config (bit 5)."""
        return self._config_other_enable & 32 == 32

    def is_flow_sensor_enabled(self) -> bool:
        """True if the flow sensor is enabled in the controller config (bit 6)."""
        return self._config_other_enable & 64 == 64

    def is_repeated_mails_enabled(self) -> bool:
        """True if repeated email notifications are enabled (bit 7)."""
        return self._config_other_enable & 128 == 128

    def is_dmx_extension_enabled(self) -> bool:
        """True if the DMX extension module is enabled in the controller config (bit 8)."""
        return self._config_other_enable & 256 == 256

    def _parse(self) -> None:
        """Build per-column `DataObject` instances and group them by category."""
        self._data_objects = []
        for column, name in enumerate(self._data_names):
            self._data_objects.append(
                DataObject(
                    column,
                    name,
                    self._data_units[column],
                    self._data_offsets[column],
                    self._data_gain[column],
                    self._data_raw_values[column],
                )
            )

        self._analog_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_ANALOG
        ]
        self._electrode_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_ELECTRODE
        ]
        self._temperature_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_TEMPERATURE
        ]
        self._relay_objects = [obj for obj in self._data_objects if obj.category == CATEGORY_RELAY]
        self._digital_input_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_DIGITAL_INPUT
        ]
        self._external_relay_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_EXTERNAL_RELAY
        ]
        self._canister_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_CANISTER
        ]
        self._consumption_objects = [
            obj for obj in self._data_objects if obj.category == CATEGORY_CONSUMPTION
        ]

    @property
    def analog_objects(self) -> list[DataObject]:
        """The five analog inputs (columns 1–5), in column order."""
        return self._analog_objects

    @property
    def electrode_objects(self) -> list[DataObject]:
        """The two electrode readings — redox at index 0, pH at index 1."""
        return self._electrode_objects

    @property
    def temperature_objects(self) -> list[DataObject]:
        """The eight temperature sensors (columns 8–15), in column order."""
        return self._temperature_objects

    @property
    def relay_objects(self) -> list[DataObject]:
        """The eight built-in relays (columns 16–23), in column order.

        These are still untyped `DataObject` instances. Use `relays()` for
        `Relay` instances with on/off and manual/auto helpers, or
        `aggregated_relay_objects` to also include the external relays.
        """
        return self._relay_objects

    def relays(self) -> list[Relay]:
        """The eight built-in relays as `Relay` instances.

        Equivalent to wrapping each entry in `relay_objects` with `Relay(...)`.
        """
        return [Relay(obj) for obj in self._relay_objects]

    @property
    def digital_input_objects(self) -> list[DataObject]:
        """The four digital inputs (columns 24–27), in column order."""
        return self._digital_input_objects

    @property
    def external_relay_objects(self) -> list[DataObject]:
        """The eight external relays (columns 28–35), in column order.

        Will be present in the parsed data even when the relay extension is
        not enabled in the controller config — check
        `is_relay_extension_enabled` before treating them as live.
        """
        return self._external_relay_objects

    def external_relays(self) -> list[Relay]:
        """The eight external relays as `Relay` instances."""
        return [Relay(obj) for obj in self._external_relay_objects]

    @property
    def canister_objects(self) -> list[DataObject]:
        """The three canister fill-level readings (columns 36–38).

        Order: chlorine, pH-, pH+. Convenience properties `chlorine_canister`,
        `ph_minus_canister`, and `ph_plus_canister` return individual entries.
        """
        return self._canister_objects

    @property
    def consumption_objects(self) -> list[DataObject]:
        """The three dosage consumption counters (columns 39–41).

        Order: chlorine, pH-, pH+. Convenience properties
        `chlorine_consumption`, `ph_minus_consumption`, and
        `ph_plus_consumption` return individual entries.
        """
        return self._consumption_objects

    @property
    def redox_electrode(self) -> DataObject:
        """The redox electrode reading (column 6)."""
        return self._electrode_objects[0]

    @property
    def ph_electrode(self) -> DataObject:
        """The pH electrode reading (column 7)."""
        return self._electrode_objects[1]

    @property
    def chlorine_canister(self) -> DataObject:
        """Chlorine canister fill level (column 36)."""
        return self._canister_objects[0]

    @property
    def ph_minus_canister(self) -> DataObject:
        """pH- canister fill level (column 37)."""
        return self._canister_objects[1]

    @property
    def ph_plus_canister(self) -> DataObject:
        """pH+ canister fill level (column 38)."""
        return self._canister_objects[2]

    @property
    def chlorine_consumption(self) -> DataObject:
        """Cumulative chlorine consumption counter (column 39)."""
        return self._consumption_objects[0]

    @property
    def ph_minus_consumption(self) -> DataObject:
        """Cumulative pH- consumption counter (column 40)."""
        return self._consumption_objects[1]

    @property
    def ph_plus_consumption(self) -> DataObject:
        """Cumulative pH+ consumption counter (column 41)."""
        return self._consumption_objects[2]

    @property
    def aggregated_relay_objects(self) -> list[DataObject]:
        """All 16 relay `DataObject`s — internal first, then external.

        Index in this list is the aggregated relay ID used by `Relay.relay_id`,
        `get_relay`, and the `RelaySwitch` API.
        """
        return self._relay_objects + self._external_relay_objects

    @property
    def chlorine_dosage_relay(self) -> DataObject:
        """The relay configured as the chlorine dosing pump."""
        return self.aggregated_relay_objects[self._chlorine_dosage_relay_id]

    @property
    def ph_minus_dosage_relay(self) -> DataObject:
        """The relay configured as the pH- dosing pump."""
        return self.aggregated_relay_objects[self._ph_minus_dosage_relay_id]

    @property
    def ph_plus_dosage_relay(self) -> DataObject:
        """The relay configured as the pH+ dosing pump."""
        return self.aggregated_relay_objects[self._ph_plus_dosage_relay_id]

    def get_relay(self, relay_id: int) -> Relay:
        """Return the `Relay` for the given aggregated relay ID (0–15).

        Args:
            relay_id: 0–7 for internal relays, 8–15 for external relays.

        Returns:
            A new `Relay` wrapping the underlying `DataObject`.

        Raises:
            IndexError: If ``relay_id`` is outside the 0–15 range.
        """
        return Relay(self.aggregated_relay_objects[relay_id])

    def get_relays(self) -> list[Relay]:
        """All 16 relays as `Relay` instances, in aggregated-ID order."""
        return [Relay(obj) for obj in self.aggregated_relay_objects]

    def determine_overall_relay_bit_state(self) -> list[int]:
        """Build the two-element ENA bit field that represents the current relay state.

        The controller's `/usrcfg.cgi` payload uses an ``ENA=enable_mask,on_mask``
        pair to set relay state. ``enable_mask`` selects which relays are in
        manual mode (bit set = manual, bit clear = auto), and ``on_mask``
        selects the manual-on relays among them.

        Returns:
            A two-element list ``[enable_mask, on_mask]``. Both masks cover
            bits 0–7 (internal relays) by default, or bits 0–15 if the
            external relay extension is enabled (`is_relay_extension_enabled`).

            The masks reflect the *current* state, so callers can flip a
            single relay's bit and POST the result to switch only that
            relay without touching the others.
        """
        relay_list: list[Relay] = [Relay(obj) for obj in self._relay_objects]
        bit_state = [255, 0]
        if self.is_relay_extension_enabled():
            relay_list.extend(Relay(obj) for obj in self._external_relay_objects)
            bit_state[0] = 65535
        for relay in relay_list:
            relay_bit_mask = relay.get_bit_mask()
            if relay.is_auto_mode():
                bit_state[0] &= ~relay_bit_mask
            if relay.is_on():
                bit_state[1] |= relay_bit_mask
        return bit_state


class DmxChannelData:
    """A single DMX channel's index, name, and current value."""

    value: int
    """Current channel intensity (0–255)."""

    _index: int
    _name: str

    def __init__(self, index: int, value: int):
        """Build a channel entry.

        Args:
            index: Zero-based channel index (0 = channel 1, 15 = channel 16).
            value: Initial channel intensity. The constructor does not clamp
                values — out-of-range inputs are stored verbatim. Use
                `GetDmxData.set` if you want the [0, 255] clamp.
        """
        self.value = value
        self._index = index
        self._name = f"CH{index + 1:0>2}"

    @property
    def index(self) -> int:
        """Zero-based channel index (0 = channel 1)."""
        return self._index

    @property
    def name(self) -> str:
        """Human-friendly channel name like ``"CH01"`` or ``"CH16"``."""
        return self._name

    def __str__(self) -> str:
        """Render the channel as a bare integer string for payload building."""
        return str(self.value)


class GetDmxData:
    """Mutable representation of all 16 DMX channels.

    Construct from a `/GetDmx.csv` body, then read or modify channels via
    indexing, iteration, `get_value`, or `set`. Pass the (possibly mutated)
    instance to `proconip.api.async_set_dmx` to write the new state back.
    """

    _channels: list[DmxChannelData]

    def __init__(self, raw_data: str):
        """Parse a `/GetDmx.csv` body into 16 channels.

        Args:
            raw_data: The raw CSV string returned by the controller. Leading
                blank lines are tolerated; only the first non-blank line is
                parsed.

        Raises:
            InvalidPayloadException: If the payload is empty or
                whitespace-only.
            ValueError: If a channel value cannot be parsed as an integer.
        """
        self._raw_data = raw_data
        self._channels = []

        line = 0
        lines = raw_data.splitlines()
        while line < len(lines) and len(lines[line].strip()) < 1:
            line += 1

        if line >= len(lines):
            raise InvalidPayloadException("Empty or missing DMX payload")

        for idx, value in enumerate(lines[line].split(",")):
            self._channels.append(DmxChannelData(idx, int(value)))

    def __getitem__(self, index: int) -> DmxChannelData:
        """Return the `DmxChannelData` at the given zero-based index."""
        return self._channels[index]

    def __iter__(self) -> Iterator[DmxChannelData]:
        """Iterate over all channels in index order."""
        return iter(self._channels)

    def __str__(self) -> str:
        """Return the raw CSV body the instance was parsed from."""
        return self._raw_data

    def get_value(self, index: int) -> int:
        """Return the current value of the channel at ``index``.

        Equivalent to ``self[index].value``. Provided for symmetry with
        `set`.
        """
        return self._channels[index].value

    def set(self, index: int, value: int) -> None:
        """Update the value of one channel.

        Values outside the [0, 255] range are silently clamped — the
        controller's DMX hardware only accepts 8-bit values, so callers
        rarely need anything else.

        Args:
            index: Zero-based channel index (0 for channel 1, 15 for
                channel 16).
            value: New intensity. Clamped to [0, 255].

        Raises:
            IndexError: If ``index`` is not in 0–15.
        """
        if index > 15 or index < 0:
            raise IndexError("Index must be between 0 (channel 1) and 15 (channel 16)")
        self._channels[index].value = max(0, min(255, value))

    @property
    def post_data(self) -> dict[str, str]:
        """Form payload that updates the DMX channel state via `/usrcfg.cgi`.

        The dict has five keys, all required by the controller:

        - ``TYPE``: always ``"0"``.
        - ``LEN``: always ``"16"`` (channels per write).
        - ``CH1_8``: comma-separated values for channels 1–8.
        - ``CH9_16``: comma-separated values for channels 9–16.
        - ``DMX512``: always ``"1"``.

        URL-encode and join with ``&`` to produce the actual POST body — see
        `proconip.api.async_set_dmx` for the canonical encoding.
        """
        return {
            "TYPE": "0",
            "LEN": "16",
            "CH1_8": ",".join(map(str, self._channels[:8])),
            "CH9_16": ",".join(map(str, self._channels[8:])),
            "DMX512": "1",
        }


class BadRelayException(Exception):
    """Raised when a relay argument doesn't make sense in context.

    The two main cases are: switching a dosage relay on directly (rejected
    by `proconip.api.async_switch_on`), and passing a non-relay `DataObject`
    to `GetStateData.is_dosage_relay`.
    """


class InvalidPayloadException(Exception):
    """Raised when a CSV response from the controller cannot be parsed.

    Typically this means the response was empty, truncated, or did not
    have the expected number of CSV lines. Catching this lets callers
    distinguish protocol-level breakage from network errors.
    """
