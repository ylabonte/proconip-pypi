"""Defines data structures for the GetState.csv, GetDmx.csv, and usrcfg.cgi APIs."""

from collections.abc import Iterator
from enum import IntEnum

API_PATH_GET_STATE = "/GetState.csv"
API_PATH_USRCFG = "/usrcfg.cgi"
API_PATH_COMMAND = "/Command.htm"
API_PATH_GET_DMX = "/GetDmx.csv"

EXTERNAL_RELAY_ID_OFFSET = 8

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

NTP_FAULT_STATE = {
    0: "n.a.",
    1: "Logfile (GUI warning, green)",
    2: "Warning (GUI warning, yellow)",
    4: "Error (GUI warning, red)",
    65536: "NTP available",
}


class DosageTarget(IntEnum):
    """Helper enum for async_start_dosage."""

    CHLORINE = 0
    PH_MINUS = 1
    PH_PLUS = 2


class ConfigObject:
    """Configuration to be used with classes that interact with the pool controller."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url
        self.username = username
        self.password = password

    @staticmethod
    def from_dict(data: dict[str, str]) -> "ConfigObject":
        """Create a ConfigObject from a dictionary."""
        if "base_url" not in data:
            raise ValueError("base_url is required")
        if "username" not in data:
            raise ValueError("username is required")
        if "password" not in data:
            raise ValueError("password is required")
        return ConfigObject(data["base_url"], data["username"], data["password"])

    def to_dict(self) -> dict[str, str]:
        """Return a dictionary representation of the object."""
        return {
            "base_url": self.base_url,
            "username": self.username,
            "password": self.password,
        }


class DataObject:
    """Represents a single data unit combining the name, unit, offset, gain, and value columns."""

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
        return f"{self._name} ({self._unit}): {self._value}"

    def _relay_state(self) -> str:
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
        """Name of the data object."""
        return self._name

    @property
    def unit(self) -> str:
        """Unit of the data object."""
        return self._unit

    @property
    def offset(self) -> float:
        """Offset applied when computing the actual value from raw."""
        return self._offset

    @property
    def gain(self) -> float:
        """Gain applied when computing the actual value from raw."""
        return self._gain

    @property
    def raw_value(self) -> float:
        """Raw value as received from the pool controller (before offset/gain are applied)."""
        return self._raw_value

    @property
    def value(self) -> float:
        """Actual value: offset + gain * raw_value."""
        return self._value

    @property
    def display_value(self) -> str:
        """Value formatted for display (includes unit, precision, or state string)."""
        return self._display_value

    @property
    def column(self) -> int:
        """Column index in the raw CSV data."""
        return self._column

    @property
    def category(self) -> str:
        """Category string (e.g. CATEGORY_RELAY, CATEGORY_TEMPERATURE)."""
        return self._category

    @property
    def category_id(self) -> int:
        """Zero-based index within the category."""
        return self._category_id


class Relay(DataObject):
    """A relay with convenience methods for state interrogation."""

    def __init__(self, data_object: DataObject):
        super().__init__(
            data_object.column,
            data_object.name,
            data_object.unit,
            data_object.offset,
            data_object.gain,
            data_object.raw_value,  # pass raw value so offset+gain are applied exactly once
        )

    def __str__(self) -> str:
        return f"{self._name}: {self._display_value}"

    @property
    def relay_id(self) -> int:
        """Aggregated relay ID: category_id for internal, category_id + 8 for external relays."""
        offset = EXTERNAL_RELAY_ID_OFFSET if self.category == CATEGORY_EXTERNAL_RELAY else 0
        return self.category_id + offset

    def is_on(self) -> bool:
        """Returns True if the relay is currently on."""
        return int(self._value) & 1 == 1

    def is_off(self) -> bool:
        """Returns True if the relay is currently off."""
        return not self.is_on()

    def is_manual_mode(self) -> bool:
        """Returns True if the relay is in manual mode."""
        return int(self._value) & 2 == 2

    def is_auto_mode(self) -> bool:
        """Returns True if the relay is in auto mode."""
        return not self.is_manual_mode()

    def get_bit_mask(self) -> int:
        """Returns the bit mask for this relay in the ENA/state bit field."""
        if self._category == CATEGORY_EXTERNAL_RELAY:
            return 1 << (self._category_id + EXTERNAL_RELAY_ID_OFFSET)
        return 1 << self._category_id


class GetStateData:
    """Structured representation of the data returned by the GetState.csv API."""

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
        self._raw_data = raw_data

        line = 0
        lines = raw_data.splitlines()
        while line < len(lines) and len(lines[line].strip()) < 1:
            line += 1
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
        return self._raw_data

    def _parse_system_info(self) -> None:
        """Parse the first CSV line (SYSINFO) and populate system-level attributes."""
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
        """Current time of the controller (HH:MM)."""
        return self._time

    @property
    def version(self) -> str:
        """Firmware version of the controller."""
        return self._version

    @property
    def cpu_time(self) -> int:
        """CPU uptime in seconds."""
        return self._cpu_time

    @property
    def reset_root_cause(self) -> int:
        """Reason for the last controller reset, encoded as a bit field."""
        return self._reset_root_cause

    @property
    def ntp_fault_state(self) -> int:
        """NTP fault state encoded as a bit field."""
        return self._ntp_fault_state

    @property
    def config_other_enable(self) -> int:
        """Miscellaneous config flags encoded as a bit field."""
        return self._config_other_enable

    @property
    def dosage_control(self) -> int:
        """Dosage control config flags encoded as a bit field."""
        return self._dosage_control

    @property
    def ph_plus_dosage_relay_id(self) -> int:
        """Aggregated relay ID of the pH+ dosage relay."""
        return self._ph_plus_dosage_relay_id

    @property
    def ph_minus_dosage_relay_id(self) -> int:
        """Aggregated relay ID of the pH- dosage relay."""
        return self._ph_minus_dosage_relay_id

    @property
    def chlorine_dosage_relay_id(self) -> int:
        """Aggregated relay ID of the chlorine dosage relay."""
        return self._chlorine_dosage_relay_id

    def is_chlorine_dosage_enabled(self) -> bool:
        """Returns True if chlorine dosage control is enabled."""
        return self._dosage_control & 1 == 1

    def is_electrolysis_enabled(self) -> bool:
        """Returns True if electrolysis control is enabled."""
        return self._dosage_control & 16 == 16

    def is_ph_minus_dosage_enabled(self) -> bool:
        """Returns True if pH- dosage control is enabled."""
        return self._dosage_control & 256 == 256

    def is_ph_plus_dosage_enabled(self) -> bool:
        """Returns True if pH+ dosage control is enabled."""
        return self._dosage_control & 4096 == 4096

    def is_dosage_enabled(self, data_entity: DataObject) -> bool:
        """Returns True if dosage is enabled for the given canister or consumption object."""
        match data_entity.column:
            case 36 | 39:
                return self.is_chlorine_dosage_enabled()
            case 37 | 40:
                return self.is_ph_minus_dosage_enabled()
            case 38 | 41:
                return self.is_ph_plus_dosage_enabled()
            case _:
                return False

    def get_dosage_relay(self, data_entity: DataObject) -> int | None:
        """Returns the aggregated relay ID for the dosage entity, or None if not applicable."""
        match data_entity.column:
            case 36 | 39:
                return self._chlorine_dosage_relay_id
            case 37 | 40:
                return self._ph_minus_dosage_relay_id
            case 38 | 41:
                return self._ph_plus_dosage_relay_id
            case _:
                return None

    def is_dosage_relay(
        self,
        relay_object: Relay | None = None,
        data_object: DataObject | None = None,
        relay_id: int | None = None,
    ) -> bool:
        """Returns True if the given relay refers to a dosage control relay.

        Accepts one of: relay_object, data_object (must be a relay category), or relay_id.
        Raises BadRelayException if data_object is provided but is not a relay category.
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
        """Returns the reason for the last controller reset as a human-readable string."""
        if self._reset_root_cause not in RESET_ROOT_CAUSE:
            return RESET_ROOT_CAUSE[0]
        return RESET_ROOT_CAUSE[self._reset_root_cause]

    def get_ntp_fault_state_as_str(self) -> str:
        """Returns the NTP fault state as a human-readable string.

        NTP_FAULT_STATE values 1, 2, and 4 are bit flags (logfile / warning / error severity).
        For composite values not in the lookup table, the highest-severity active bit is returned.
        """
        if self._ntp_fault_state in NTP_FAULT_STATE:
            return NTP_FAULT_STATE[self._ntp_fault_state]
        for bit in (4, 2, 1):
            if self._ntp_fault_state & bit:
                return NTP_FAULT_STATE[bit]
        return NTP_FAULT_STATE[0]

    def is_tcpip_boost_enabled(self) -> bool:
        """Returns True if TCP/IP boost is enabled."""
        return self._config_other_enable & 1 == 1

    def is_sd_card_enabled(self) -> bool:
        """Returns True if the SD card is enabled."""
        return self._config_other_enable & 2 == 2

    def is_dmx_enabled(self) -> bool:
        """Returns True if DMX is enabled."""
        return self._config_other_enable & 4 == 4

    def is_avatar_enabled(self) -> bool:
        """Returns True if the avatar feature is enabled."""
        return self._config_other_enable & 8 == 8

    def is_relay_extension_enabled(self) -> bool:
        """Returns True if the relay extension module is enabled."""
        return self._config_other_enable & 16 == 16

    def is_high_bus_load_enabled(self) -> bool:
        """Returns True if high bus load mode is enabled."""
        return self._config_other_enable & 32 == 32

    def is_flow_sensor_enabled(self) -> bool:
        """Returns True if the flow sensor is enabled."""
        return self._config_other_enable & 64 == 64

    def is_repeated_mails_enabled(self) -> bool:
        """Returns True if repeated email notifications are enabled."""
        return self._config_other_enable & 128 == 128

    def is_dmx_extension_enabled(self) -> bool:
        """Returns True if the DMX extension module is enabled."""
        return self._config_other_enable & 256 == 256

    def _parse(self) -> None:
        """Parse the raw data and populate category-specific object lists."""
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
        """All DataObjects in the analog category."""
        return self._analog_objects

    @property
    def electrode_objects(self) -> list[DataObject]:
        """All DataObjects in the electrode category."""
        return self._electrode_objects

    @property
    def temperature_objects(self) -> list[DataObject]:
        """All DataObjects in the temperature category."""
        return self._temperature_objects

    @property
    def relay_objects(self) -> list[DataObject]:
        """All DataObjects in the internal relay category."""
        return self._relay_objects

    def relays(self) -> list[Relay]:
        """Returns internal relays as a list of Relay instances."""
        return [Relay(obj) for obj in self._relay_objects]

    @property
    def digital_input_objects(self) -> list[DataObject]:
        """All DataObjects in the digital input category."""
        return self._digital_input_objects

    @property
    def external_relay_objects(self) -> list[DataObject]:
        """All DataObjects in the external relay category."""
        return self._external_relay_objects

    def external_relays(self) -> list[Relay]:
        """Returns external relays as a list of Relay instances."""
        return [Relay(obj) for obj in self._external_relay_objects]

    @property
    def canister_objects(self) -> list[DataObject]:
        """All DataObjects in the canister category."""
        return self._canister_objects

    @property
    def consumption_objects(self) -> list[DataObject]:
        """All DataObjects in the consumption category."""
        return self._consumption_objects

    @property
    def redox_electrode(self) -> DataObject:
        """DataObject for the redox electrode."""
        return self._electrode_objects[0]

    @property
    def ph_electrode(self) -> DataObject:
        """DataObject for the pH electrode."""
        return self._electrode_objects[1]

    @property
    def chlorine_canister(self) -> DataObject:
        """DataObject for the chlorine canister level."""
        return self._canister_objects[0]

    @property
    def ph_minus_canister(self) -> DataObject:
        """DataObject for the pH- canister level."""
        return self._canister_objects[1]

    @property
    def ph_plus_canister(self) -> DataObject:
        """DataObject for the pH+ canister level."""
        return self._canister_objects[2]

    @property
    def chlorine_consumption(self) -> DataObject:
        """DataObject for chlorine consumption."""
        return self._consumption_objects[0]

    @property
    def ph_minus_consumption(self) -> DataObject:
        """DataObject for pH- consumption."""
        return self._consumption_objects[1]

    @property
    def ph_plus_consumption(self) -> DataObject:
        """DataObject for pH+ consumption."""
        return self._consumption_objects[2]

    @property
    def aggregated_relay_objects(self) -> list[DataObject]:
        """All relay DataObjects: internal relays first, then external relays."""
        return self._relay_objects + self._external_relay_objects

    @property
    def chlorine_dosage_relay(self) -> DataObject:
        """DataObject of the chlorine dosage relay."""
        return self.aggregated_relay_objects[self._chlorine_dosage_relay_id]

    @property
    def ph_minus_dosage_relay(self) -> DataObject:
        """DataObject of the pH- dosage relay."""
        return self.aggregated_relay_objects[self._ph_minus_dosage_relay_id]

    @property
    def ph_plus_dosage_relay(self) -> DataObject:
        """DataObject of the pH+ dosage relay."""
        return self.aggregated_relay_objects[self._ph_plus_dosage_relay_id]

    def get_relay(self, relay_id: int) -> Relay:
        """Returns the Relay instance for the given aggregated relay ID."""
        return Relay(self.aggregated_relay_objects[relay_id])

    def get_relays(self) -> list[Relay]:
        """Returns all relays (internal + external) as Relay instances."""
        return [Relay(obj) for obj in self.aggregated_relay_objects]

    def determine_overall_relay_bit_state(self) -> list[int]:
        """Determine the overall relay bit state from the current state.

        Returns [enable_mask, on_mask] — a two-element list suitable for the ENA= payload.
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
    """DMX channel state representation."""

    value: int
    _index: int
    _name: str

    def __init__(self, index: int, value: int):
        """Initialize a DMX channel with its index and current value."""
        self.value = value
        self._index = index
        self._name = f"CH{index + 1:0>2}"

    @property
    def index(self) -> int:
        """Zero-based channel index."""
        return self._index

    @property
    def name(self) -> str:
        """Channel name (e.g. CH01, CH16)."""
        return self._name

    def __str__(self) -> str:
        return str(self.value)


class GetDmxData:
    """Data model for reading and updating DMX channel states from /GetDmx.csv."""

    _channels: list[DmxChannelData]

    def __init__(self, raw_data: str):
        """Initialize from the raw /GetDmx.csv response string."""
        self._raw_data = raw_data
        self._channels = []

        line = 0
        lines = raw_data.splitlines()
        while line < len(lines) and len(lines[line].strip()) < 1:
            line += 1

        for idx, value in enumerate(lines[line].split(",")):
            self._channels.append(DmxChannelData(idx, int(value)))

    def __getitem__(self, index: int) -> DmxChannelData:
        """Direct channel access by index."""
        return self._channels[index]

    def __iter__(self) -> Iterator[DmxChannelData]:
        """Iterate over all channels in order."""
        return iter(self._channels)

    def __str__(self) -> str:
        return self._raw_data

    def get_value(self, index: int) -> int:
        """Get the current value of the channel at index (0 = channel 1, 15 = channel 16)."""
        return self._channels[index].value

    def set(self, index: int, value: int) -> None:
        """Set the value for the channel at index (0 = channel 1, 15 = channel 16).

        Values outside [0, 255] are clamped. Raises IndexError for out-of-range index.
        """
        if index > 15 or index < 0:
            raise IndexError("Index must be between 0 (channel 1) and 15 (channel 16)")
        self._channels[index].value = max(0, min(255, value))

    @property
    def post_data(self) -> dict[str, str]:
        """HTTP POST payload dict for updating DMX channels via the controller API."""
        return {
            "TYPE": "0",
            "LEN": "16",
            "CH1_8": ",".join(map(str, self._channels[:8])),
            "CH9_16": ",".join(map(str, self._channels[8:])),
            "DMX512": "1",
        }


class BadRelayException(Exception):
    """Raised when an invalid or inappropriate relay is given as a parameter."""


class InvalidPayloadException(Exception):
    """Raised when the API response cannot be parsed as expected."""
