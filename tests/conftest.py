"""Shared pytest fixtures for the proconip test suite."""

import pathlib

import pytest

from proconip.definitions import ConfigObject, GetDmxData, GetStateData

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

BASE_URL = "http://127.0.0.1"
USERNAME = "admin"
PASSWORD = "admin"


@pytest.fixture
def config() -> ConfigObject:
    return ConfigObject(BASE_URL, USERNAME, PASSWORD)


@pytest.fixture
def get_state_csv() -> str:
    return (FIXTURES_DIR / "get_state.csv").read_text()


@pytest.fixture
def get_dmx_csv() -> str:
    return (FIXTURES_DIR / "get_dmx.csv").read_text()


@pytest.fixture
def get_state_data(get_state_csv: str) -> GetStateData:
    return GetStateData(get_state_csv)


@pytest.fixture
def get_dmx_data(get_dmx_csv: str) -> GetDmxData:
    return GetDmxData(get_dmx_csv)


@pytest.fixture
def get_state_electrolysis_csv() -> str:
    """`get_state.csv` reconfigured for a salt-electrolysis chlorine supply.

    Derived from the real capture: DOSAGE_CNTRL 273 (Cl enabled + bit 4
    electrolysis + pH- enabled), chlorine daily amount in ``g``, and non-zero
    values in the chlorine "canister" (cell lifetime %) and "consumption"
    (calculated production) columns, per the vendor's TRM column table.
    """
    return (FIXTURES_DIR / "get_state_electrolysis.csv").read_text()


@pytest.fixture
def get_state_electrolysis_data(get_state_electrolysis_csv: str) -> GetStateData:
    return GetStateData(get_state_electrolysis_csv)
