"""Defines data structures for use with and used by the GetState.csv and usercfg.cgi APIs."""
import dataclasses
from enum import IntEnum


API_PATH_GET_STATE = "/GetState.csv"
API_PATH_USRCFG = "/usrcfg.cgi"
API_PATH_COMMAND = "/Command.htm"


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


@dataclasses.dataclass
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
    def from_dict(data: dict[str, str]):
        """Set attributes from a dictionary."""
        if "base_url" not in data:
            raise ValueError("base_url is required")
        if "username" not in data:
            raise ValueError("username is required")
        if "password" not in data:
            raise ValueError("password is required")
        return ConfigObject(data["base_url"], data["username"], data["password"])

    def to_dict(self):
        """Return a dictionary representation of the object."""
        return {
            "base_url": self.base_url,
            "username": self.username,
            "password": self.password,
        }


# pylint: disable=R0902
@dataclasses.dataclass
class DataObject:
    """Represents a single data unit combining the lines 2, 3, 4 and 5 from raw data."""

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

    # pylint: disable=R0913
    def __init__(self, column: int, name: str, unit: str, offset: float, gain: float, value: float):
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
            self._display_value = f"{int(self._value / 256):02d}:{(int(self._value) % 256):02d}"
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

    def __str__(self):
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
        """Offset of the data object (used to calculate the actual value)."""
        return self._offset

    @property
    def gain(self) -> float:
        """Gain of the data object (used to calculate the actual value)."""
        return self._gain

    @property
    def raw_value(self) -> float:
        """Raw value of the data object (as measured and received from the pool controller)."""
        return self._raw_value

    @property
    def value(self) -> float:
        """Actual value of the data object (calculated from raw value, offset and gain)."""
        return self._value

    @property
    def display_value(self) -> str:
        """Value of the data object formatted for display."""
        return self._display_value

    @property
    def column(self) -> int:
        """Column of the data object in the raw data."""
        return self._column

    @property
    def category(self) -> str:
        """Category of the data object."""
        return self._category

    @property
    def category_id(self) -> int:
        """Category ID of the data object (counts from 0 for each category)."""
        return self._category_id


@dataclasses.dataclass
class Relay(DataObject):
    """Represents a relay."""

    def __init__(self, data_object: DataObject):
        super().__init__(
            data_object.column,
            data_object.name,
            data_object.unit,
            data_object.offset,
            data_object.gain,
            data_object.value)

    def __str__(self):
        return f"{self._name}: {self._display_value}"

    @property
    def relay_id(self) -> int:
        """Returns the aggregated relays id (eg. 8 for the first external relay)."""
        offset = 8 if self.category == CATEGORY_EXTERNAL_RELAY else 0
        return self.category_id + offset

    def is_on(self) -> bool:
        """Returns whether the relay is on."""
        return int(self._value) & 1 == 1

    def is_off(self) -> bool:
        """Returns whether the relay is off."""
        return not self.is_on()

    def is_manual_mode(self) -> bool:
        """Returns whether the relay is in manual mode."""
        return int(self._value) & 2 == 2

    def is_auto_mode(self) -> bool:
        """Returns whether the relay is in manual mode."""
        return not self.is_manual_mode()

    def get_bit_mask(self) -> int:
        """Returns the bit mask of the relay."""
        if self._category == CATEGORY_EXTERNAL_RELAY:
            return 1 << (self._category_id + 8)
        return 1 << self._category_id


# pylint: disable=R0904
@dataclasses.dataclass
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
        while len(lines[line].strip()) < 1 and line < len(lines):
            line += 1
        self._system_info = lines[line].split(",")
        self._data_names = lines[line + 1].split(",")
        self._data_units = lines[line + 2].split(",")
        self._data_offsets = [float(offset) for offset in lines[line + 3].split(",")]
        self._data_gain = [float(gain) for gain in lines[line + 4].split(",")]
        self._data_raw_values = [float(raw) for raw in lines[line + 5].split(",")]
        self._data_values: dict[int, float] = {}
        for i, value in enumerate(self._data_raw_values):
            self._data_values[i] = (float(value) - float(self._data_offsets[i])) \
                                   * float(self._data_gain[i])

        self._parse_system_info()
        self._parse()
        self._time = self._data_objects[0].display_value

    def __str__(self):
        return self._raw_data

    def _parse_system_info(self):
        """Parse system information (1st line of the csv data) and populate the respective
        object's attributes."""
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
        """Returns the current time of the controller."""
        return self._time

    @property
    def version(self) -> str:
        """Returns the firmware version of the controller."""
        return self._version

    @property
    def cpu_time(self) -> int:
        """Returns the CPU uptime in seconds."""
        return self._cpu_time

    @property
    def reset_root_cause(self) -> int:
        """Returns the reason for the last reset of the controller encoded as bit state."""
        return self._reset_root_cause

    @property
    def ntp_fault_state(self) -> int:
        """Returns the NTP fault state encoded as bit state."""
        return self._ntp_fault_state

    @property
    def config_other_enable(self) -> int:
        """Returns the various other config flags of the controller encoded as bit state."""
        return self._config_other_enable

    @property
    def dosage_control(self) -> int:
        """Returns the dosage control config flags of the controller encoded as bit state."""
        return self._dosage_control

    @property
    def ph_plus_dosage_relay_id(self) -> int:
        """Returns the dosage relay number (equivalent to DataObject.category_id) for
        the PH+ dosage."""
        return self._ph_plus_dosage_relay_id

    @property
    def ph_minus_dosage_relay_id(self) -> int:
        """Returns the dosage relay number (equivalent to DataObject.category_id) for
        the PH- dosage."""
        return self._ph_minus_dosage_relay_id

    @property
    def chlorine_dosage_relay_id(self) -> int:
        """Returns the dosage relay number (equivalent to DataObject.category_id) for
        the chlorine dosage."""
        return self._chlorine_dosage_relay_id

    def is_chlorine_dosage_enabled(self) -> bool:
        """Returns true if the chlorine dosage control is enabled, false otherwise."""
        return self._dosage_control & 1 == 1

    def is_electrolysis_enabled(self) -> bool:
        """Returns true if the electrolysis control is enabled, false otherwise."""
        return self._dosage_control & 16 == 16

    def is_ph_minus_dosage_enabled(self) -> bool:
        """Returns true if the PH- dosage control is enabled, false otherwise."""
        return self._dosage_control & 256 == 256

    def is_ph_plus_dosage_enabled(self) -> bool:
        """Returns true if the PH+ dosage control is enabled, false otherwise."""
        return self._dosage_control & 4096 == 4096

    def is_dosage_enabled(self, data_entity) -> bool:
        """Returns true if the dosage control is enabled for the given data entity (canister or
        consumption DataObject), false otherwise."""
        match data_entity.column:
            case 36 | 39:
                return self.is_chlorine_dosage_enabled()
            case 37 | 40:
                return self.is_ph_minus_dosage_enabled()
            case 38 | 41:
                return self.is_ph_plus_dosage_enabled()
            case _:
                return False

    def get_dosage_relay(self, data_entity) -> int:
        """Returns the dosage relay index (i in `GetStateData.aggregated_relay_objects[i]`) for
        the given data entity (canister or consumption DataObject)."""
        match data_entity.column:
            case 36 | 39:
                return self._chlorine_dosage_relay_id
            case 37 | 40:
                return self._ph_minus_dosage_relay_id
            case 38 | 41:
                return self._ph_plus_dosage_relay_id
            case _:
                return False

    def is_dosage_relay(self,
                        relay_object: Relay = None,
                        data_object: DataObject = None,
                        relay_id: int = None) -> bool:
        """Returns true if the given relay_object OR data_object OR column refers to a dosage
        control relay."""
        dosage_control_relays = [
            self._chlorine_dosage_relay_id,
            self._ph_minus_dosage_relay_id,
            self._ph_plus_dosage_relay_id,
        ]
        if relay_object is not None:
            return relay_object.relay_id in dosage_control_relays
        if data_object is not None:
            if data_object.category not in (CATEGORY_RELAY, CATEGORY_EXTERNAL_RELAY):
                raise BadRelayException
            offset = 8 if data_object.category == CATEGORY_EXTERNAL_RELAY else 0
            return data_object.category_id + offset in dosage_control_relays
        if relay_id is not None:
            return relay_id in dosage_control_relays
        return False

    def get_reset_root_cause_as_str(self) -> str:
        """Returns the reason for the last reset of the controller as string."""
        if self._reset_root_cause not in RESET_ROOT_CAUSE:
            return RESET_ROOT_CAUSE[0]
        return RESET_ROOT_CAUSE[self._reset_root_cause]

    def get_ntp_fault_state_as_str(self) -> str:
        """Returns the NTP fault state as string."""
        if self._ntp_fault_state in NTP_FAULT_STATE:
            return NTP_FAULT_STATE[self._ntp_fault_state]
        if self._ntp_fault_state > 4:
            return NTP_FAULT_STATE[4]
        if self._ntp_fault_state > 2:
            return NTP_FAULT_STATE[2]
        return NTP_FAULT_STATE[0]

    def is_tcpip_boost_enabled(self) -> bool:
        """Returns true if the TCP/IP boost is enabled, false otherwise."""
        return self._config_other_enable & 1 == 1

    def is_sd_card_enabled(self) -> bool:
        """Returns true if the SD card is enabled, false otherwise."""
        return self._config_other_enable & 2 == 2

    def is_dmx_enabled(self) -> bool:
        """Returns true if the DMX is enabled, false otherwise."""
        return self._config_other_enable & 4 == 4

    def is_avatar_enabled(self) -> bool:
        """Returns true if the avatar is enabled, false otherwise."""
        return self._config_other_enable & 8 == 8

    def is_relay_extension_enabled(self) -> bool:
        """Returns true if the relay extension is enabled, false otherwise."""
        return self._config_other_enable & 16 == 16

    def is_high_bus_load_enabled(self) -> bool:
        """Returns true if high bus load is enabled, false otherwise."""
        return self._config_other_enable & 32 == 32

    def is_flow_sensor_enabled(self) -> bool:
        """Returns true if the flow sensor is enabled, false otherwise."""
        return self._config_other_enable & 64 == 64

    def is_repeated_mails_enabled(self) -> bool:
        """Returns true if repeated mails are enabled, false otherwise."""
        return self._config_other_enable & 128 == 128

    def is_dmx_extension_enabled(self) -> bool:
        """Returns true if the DMX extension is enabled, false otherwise."""
        return self._config_other_enable & 256 == 256

    def _parse(self):
        """Parse the raw data and populate the object's attributes."""
        self._data_objects = []
        for column, name in enumerate(self._data_names):
            self._data_objects.append(DataObject(column,
                                                 name,
                                                 self._data_units[column],
                                                 self._data_offsets[column],
                                                 self._data_gain[column],
                                                 self._data_raw_values[column]))

        self._analog_objects = [obj for obj in self._data_objects
                                if obj.category == CATEGORY_ANALOG]
        self._electrode_objects = [obj for obj in self._data_objects
                                   if obj.category == CATEGORY_ELECTRODE]
        self._temperature_objects = [obj for obj in self._data_objects
                                     if obj.category == CATEGORY_TEMPERATURE]
        self._relay_objects = [obj for obj in self._data_objects
                               if obj.category == CATEGORY_RELAY]
        self._digital_objects = [obj for obj in self._data_objects
                                 if obj.category == CATEGORY_DIGITAL_INPUT]
        self._external_relay_objects = [obj for obj in self._data_objects
                                        if obj.category == CATEGORY_EXTERNAL_RELAY]
        self._canister_objects = [obj for obj in self._data_objects
                                  if obj.category == CATEGORY_CANISTER]
        self._consumption_objects = [obj for obj in self._data_objects
                                     if obj.category == CATEGORY_CONSUMPTION]

    @property
    def analog_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the analog category."""
        return self._analog_objects

    @property
    def electrode_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the electrode category."""
        return self._electrode_objects

    @property
    def temperature_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the temperature category."""
        return self._temperature_objects

    @property
    def relay_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the relay category."""
        return self._relay_objects

    def relays(self) -> list[Relay]:
        """Returns relays as a list of Relay object instances."""
        return [Relay(relay_object) for relay_object in self._relay_objects]

    @property
    def digital_input_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the digital input category."""
        return self._digital_objects

    @property
    def external_relay_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the external relay category."""
        return self._external_relay_objects

    def external_relays(self) -> list[Relay]:
        """Returns external relays as a list of Relay object instances."""
        return [
            Relay(external_relay_object) for external_relay_object in self._external_relay_objects
        ]

    @property
    def canister_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the canister category."""
        return self._canister_objects

    @property
    def consumption_objects(self) -> list[DataObject]:
        """Returns a list of DataObjects of the consumption category."""
        return self._consumption_objects

    @property
    def redox_electrode(self) -> DataObject:
        """Returns the DataObject of the redox electrode."""
        return self._electrode_objects[0]

    @property
    def ph_electrode(self) -> DataObject:
        """Returns the DataObject of the pH electrode."""
        return self._electrode_objects[1]

    @property
    def chlorine_canister(self) -> DataObject:
        """Returns the DataObject of the chlorine canister."""
        return self._canister_objects[0]

    @property
    def ph_minus_canister(self) -> DataObject:
        """Returns the DataObject of the pH minus canister."""
        return self._canister_objects[1]

    @property
    def ph_plus_canister(self) -> DataObject:
        """Returns the DataObject of the pH plus canister."""
        return self._canister_objects[2]

    @property
    def chlorine_consumption(self) -> DataObject:
        """Returns the DataObject of the chlorine consumption."""
        return self._consumption_objects[0]

    @property
    def ph_minus_consumption(self) -> DataObject:
        """Returns the DataObject of the pH minus consumption."""
        return self._consumption_objects[1]

    @property
    def ph_plus_consumption(self) -> DataObject:
        """Returns the DataObject of the pH plus consumption."""
        return self._consumption_objects[2]

    @property
    def aggregated_relay_objects(self) -> list[DataObject]:
        """Returns a list of all relays."""
        return self._relay_objects + self.external_relay_objects

    @property
    def chlorine_dosage_relay(self) -> DataObject:
        """Returns the DataObject of the chlorine dosage relay."""
        return self.aggregated_relay_objects[self._chlorine_dosage_relay_id]

    @property
    def ph_minus_dosage_relay(self) -> DataObject:
        """Returns the DataObject of the pH minus dosage relay."""
        return self.aggregated_relay_objects[self._ph_minus_dosage_relay_id]

    @property
    def ph_plus_dosage_relay(self) -> DataObject:
        """Returns the DataObject of the pH plus dosage relay."""
        return self.aggregated_relay_objects[self._ph_plus_dosage_relay_id]

    def get_relay(self, relay_id: int) -> Relay:
        """Returns the Relay instance for the given id."""
        return Relay(self.aggregated_relay_objects[relay_id])

    def determine_overall_relay_bit_state(self) -> [int, int]:
        """Determine the overall relay bit state from the current state."""
        relays = self.relays()
        bit_state = [255, 0]
        if self.is_relay_extension_enabled():
            relays.extend(self.external_relays())
            bit_state[0] = 65535
        for relay in relays:
            relay_bit_mask = relay.get_bit_mask()
            if relay.is_auto_mode():
                bit_state[0] &= ~relay_bit_mask
            if relay.is_on():
                bit_state[1] |= relay_bit_mask
        return bit_state

class BadRelayException(Exception):
    """Exception to raise when an invalid relay was given as parameter."""
