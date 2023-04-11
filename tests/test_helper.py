from proconip.definitions import ConfigObject

BASE_URL = "http://127.0.0.1"
USERNAME = "admin"
PASSWORD = "admin"


def get_config_object():
    return ConfigObject(BASE_URL, USERNAME, PASSWORD)