"""Testing get_state module"""
import unittest

from proconip.definitions import ConfigObject

BASE_URL = "http://127.0.0.1"
USERNAME = "admin"
PASSWORD = "admin"


class GetStateTestCase(unittest.TestCase):
    def test_raw(self):
        actual = ConfigObject(BASE_URL, USERNAME, PASSWORD)
        self.assertEqual(actual.base_url, BASE_URL)
        self.assertEqual(actual.username, USERNAME)
        self.assertEqual(actual.password, PASSWORD)





if __name__ == '__main__':
    unittest.main()
