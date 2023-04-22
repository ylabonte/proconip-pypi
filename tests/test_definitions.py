"""Testing data structures and helper classes from definitions module."""
import unittest

from proconip.definitions import (
    ConfigObject,
    GetStateData,
    CATEGORY_ANALOG,
    CATEGORY_ELECTRODE,
    CATEGORY_TEMPERATURE,
    CATEGORY_RELAY,
    CATEGORY_DIGITAL_INPUT,
    CATEGORY_EXTERNAL_RELAY,
    CATEGORY_CANISTER,
    CATEGORY_CONSUMPTION,
)
from .helper import (
    BASE_URL,
    GET_STATE_CSV,
    USERNAME,
    PASSWORD,
)


class ConfigObjectTestCase(unittest.TestCase):
    """Testing the ConfigObject class."""
    def test_initialization(self):
        """Test the initialization of the ConfigObject class."""
        actual = ConfigObject(BASE_URL, USERNAME, PASSWORD)
        self.assertEqual(actual.base_url, BASE_URL)
        self.assertEqual(actual.username, USERNAME)
        self.assertEqual(actual.password, PASSWORD)


class GetStateDataTestCase(unittest.TestCase):
    """Testing the GetStateData class."""
    def setUp(self):
        """Set up the test case."""
        self.actual = GetStateData(GET_STATE_CSV)

    def test_initialization(self):
        """Test the initialization of the GetStateData class."""
        actual = GetStateData(GET_STATE_CSV)
        self.assertIsNotNone(actual)

    def test_system_info(self):
        """"Test the system info properties of the GetStateData class."""
        self.assertEqual("1.7.3", self.actual.version)
        self.assertEqual(9559698, self.actual.cpu_time)
        self.assertEqual(1, self.actual.reset_root_cause)
        self.assertEqual(3, self.actual.ntp_fault_state)
        self.assertEqual(0, self.actual.config_other_enable)
        self.assertEqual(False, self.actual.is_tcpip_boost_enabled())
        self.assertEqual(False, self.actual.is_sd_card_enabled())
        self.assertEqual(False, self.actual.is_dmx_enabled())
        self.assertEqual(False, self.actual.is_avatar_enabled())
        self.assertEqual(False, self.actual.is_relay_extension_enabled())
        self.assertEqual(False, self.actual.is_high_bus_load_enabled())
        self.assertEqual(False, self.actual.is_flow_sensor_enabled())
        self.assertEqual(False, self.actual.is_repeated_mails_enabled())
        self.assertEqual(False, self.actual.is_dmx_extension_enabled())
        self.assertEqual(257, self.actual.dosage_control)
        self.assertEqual(4, self.actual.ph_plus_dosage_relay_id)
        self.assertEqual(4, self.actual.ph_minus_dosage_relay_id)
        self.assertEqual(5, self.actual.chlorine_dosage_relay_id)
        self.assertEqual(True, self.actual.is_chlorine_dosage_enabled())
        self.assertEqual(False, self.actual.is_electrolysis_enabled())
        self.assertEqual(True, self.actual.is_ph_minus_dosage_enabled())
        self.assertEqual(False, self.actual.is_ph_plus_dosage_enabled())
        self.assertEqual(True, self.actual.is_dosage_enabled(self.actual.canister_objects[0]))
        self.assertEqual(True, self.actual.is_dosage_enabled(self.actual.canister_objects[1]))
        self.assertEqual(False, self.actual.is_dosage_enabled(self.actual.canister_objects[2]))
        self.assertEqual(True, self.actual.is_dosage_enabled(self.actual.consumption_objects[0]))
        self.assertEqual(True, self.actual.is_dosage_enabled(self.actual.consumption_objects[1]))
        self.assertEqual(False, self.actual.is_dosage_enabled(self.actual.consumption_objects[2]))
        self.assertEqual("External reset", self.actual.get_reset_root_cause_as_str())
        self.assertEqual("Warning (GUI warning, yellow)", self.actual.get_ntp_fault_state_as_str())

    def test_time(self):
        """Test the time property of the GetStateData class."""
        self.assertEqual("02:17", self.actual.time)

    def test_analog_objects(self):
        """Test the analog objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.analog_objects), 5)
        for category_id, analog_object in enumerate(self.actual.analog_objects):
            self.assertIsNotNone(analog_object.name)
            self.assertIsNotNone(analog_object.unit)
            self.assertIsNotNone(analog_object.offset)
            self.assertIsNotNone(analog_object.gain)
            self.assertIsNotNone(analog_object.raw_value)
            self.assertIsNotNone(analog_object.value)
            self.assertIsNotNone(analog_object.display_value)
            self.assertEqual(analog_object.column, category_id + 1)
            self.assertEqual(analog_object.category, CATEGORY_ANALOG)
            self.assertEqual(analog_object.category_id, category_id)

    def test_electrode_objects(self):
        """Test the electrode objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.electrode_objects), 2)
        self.assertIn(self.actual.redox_electrode, self.actual.electrode_objects)
        self.assertIn(self.actual.ph_electrode, self.actual.electrode_objects)
        self.assertEqual("Redox", self.actual.redox_electrode.name)
        self.assertEqual("mV", self.actual.redox_electrode.unit)
        self.assertIsNotNone(self.actual.redox_electrode.offset)
        self.assertIsNotNone(self.actual.redox_electrode.gain)
        self.assertIsNotNone(self.actual.redox_electrode.raw_value)
        self.assertIsNotNone(self.actual.redox_electrode.value)
        self.assertIsNotNone(self.actual.redox_electrode.display_value)
        self.assertIsNotNone(self.actual.redox_electrode.column)
        self.assertIsNotNone(self.actual.redox_electrode.category_id)
        self.assertIsNotNone(self.actual.redox_electrode.category)
        self.assertEqual("pH", self.actual.ph_electrode.name)
        self.assertEqual("pH", self.actual.ph_electrode.unit)
        self.assertIsNotNone(self.actual.ph_electrode.offset)
        self.assertIsNotNone(self.actual.ph_electrode.gain)
        self.assertIsNotNone(self.actual.ph_electrode.raw_value)
        self.assertIsNotNone(self.actual.ph_electrode.value)
        self.assertIsNotNone(self.actual.ph_electrode.display_value)
        self.assertIsNotNone(self.actual.ph_electrode.column)
        self.assertEqual(self.actual.ph_electrode.column - 6, self.actual.ph_electrode.category_id)
        self.assertEqual(CATEGORY_ELECTRODE, self.actual.ph_electrode.category)

    def test_temperature_objects(self):
        """Test the temperature objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.temperature_objects), 8)
        for category_id, temperature_object in enumerate(self.actual.temperature_objects):
            self.assertIsNotNone(temperature_object.name)
            self.assertEqual(temperature_object.unit, "C")
            self.assertIsNotNone(temperature_object.offset)
            self.assertIsNotNone(temperature_object.gain)
            self.assertIsNotNone(temperature_object.raw_value)
            self.assertIsNotNone(temperature_object.value)
            self.assertIsNotNone(temperature_object.display_value)
            self.assertEqual(temperature_object.column, category_id + 8)
            self.assertEqual(temperature_object.category, CATEGORY_TEMPERATURE)
            self.assertEqual(temperature_object.category_id, category_id)

    def test_relay_objects(self):
        """Test the relay objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.relay_objects), 8)
        for category_id, relay_object in enumerate(self.actual.relay_objects):
            self.assertIsNotNone(relay_object.name)
            self.assertEqual(relay_object.unit, "--")
            self.assertIsNotNone(relay_object.offset)
            self.assertIsNotNone(relay_object.gain)
            self.assertIsNotNone(relay_object.raw_value)
            self.assertIsNotNone(relay_object.value)
            self.assertIsNotNone(relay_object.display_value)
            self.assertEqual(relay_object.column, category_id + 16)
            self.assertEqual(relay_object.category, CATEGORY_RELAY)
            self.assertEqual(relay_object.category_id, category_id)

    def test_digital_input_objects(self):
        """Test the digital input objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.digital_input_objects), 4)
        for category_id, digital_input_object in enumerate(self.actual.digital_input_objects):
            self.assertIsNotNone(digital_input_object.name)
            self.assertIsNotNone(digital_input_object.unit)
            self.assertIsNotNone(digital_input_object.offset)
            self.assertIsNotNone(digital_input_object.gain)
            self.assertIsNotNone(digital_input_object.raw_value)
            self.assertIsNotNone(digital_input_object.value)
            self.assertIsNotNone(digital_input_object.display_value)
            self.assertEqual(digital_input_object.column, category_id + 24)
            self.assertEqual(digital_input_object.category, CATEGORY_DIGITAL_INPUT)
            self.assertEqual(digital_input_object.category_id, category_id)

    def test_external_relay_objects(self):
        """Test the external relay objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.external_relay_objects), 8)
        for category_id, external_relay_object in enumerate(self.actual.external_relay_objects):
            self.assertIsNotNone(external_relay_object.name)
            self.assertEqual(external_relay_object.unit, "--")
            self.assertIsNotNone(external_relay_object.offset)
            self.assertIsNotNone(external_relay_object.gain)
            self.assertIsNotNone(external_relay_object.raw_value)
            self.assertIsNotNone(external_relay_object.value)
            self.assertIsNotNone(external_relay_object.display_value)
            self.assertEqual(external_relay_object.column, category_id + 28)
            self.assertEqual(external_relay_object.category, CATEGORY_EXTERNAL_RELAY)
            self.assertEqual(external_relay_object.category_id, category_id)

    def test_canister_objects(self):
        """Test the canister objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.canister_objects), 3)
        for category_id, canister_object in enumerate(self.actual.canister_objects):
            self.assertIsNotNone(canister_object.name)
            self.assertEqual(canister_object.unit, "%")
            self.assertIsNotNone(canister_object.offset)
            self.assertIsNotNone(canister_object.gain)
            self.assertIsNotNone(canister_object.raw_value)
            self.assertIsNotNone(canister_object.value)
            self.assertIsNotNone(canister_object.display_value)
            self.assertEqual(canister_object.column, category_id + 36)
            self.assertEqual(canister_object.category, CATEGORY_CANISTER)
            self.assertEqual(canister_object.category_id, category_id)

    def test_consumption_objects(self):
        """Test the consumption objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.consumption_objects), 3)
        for category_id, consumption_object in enumerate(self.actual.consumption_objects):
            self.assertIsNotNone(consumption_object.name)
            self.assertIsNotNone(consumption_object.unit)
            self.assertIsNotNone(consumption_object.offset)
            self.assertIsNotNone(consumption_object.gain)
            self.assertIsNotNone(consumption_object.raw_value)
            self.assertIsNotNone(consumption_object.value)
            self.assertIsNotNone(consumption_object.display_value)
            self.assertEqual(consumption_object.column, category_id + 39)
            self.assertEqual(consumption_object.category, CATEGORY_CONSUMPTION)
            self.assertEqual(consumption_object.category_id, category_id)

    def test_aggregated_relay_objects(self):
        """Test the aggregated relay objects property of the GetStateData class."""
        self.assertEqual(len(self.actual.aggregated_relay_objects), 16)


if __name__ == '__main__':
    unittest.main()
