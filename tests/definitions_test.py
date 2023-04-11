"""Testing data structures and helper classes from definitions module."""
import unittest

from proconip.definitions import ConfigObject
from test_helper import BASE_URL, USERNAME, PASSWORD


class ConfigObjectTestCase(unittest.TestCase):
    def test_initialization(self):
        actual = ConfigObject(BASE_URL, USERNAME, PASSWORD)
        self.assertEqual(actual.base_url, BASE_URL)
        self.assertEqual(actual.username, USERNAME)
        self.assertEqual(actual.password, PASSWORD)


if __name__ == '__main__':
    unittest.main()
