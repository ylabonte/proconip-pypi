"""Tests for the API module — HTTP layer, error mapping, and class wrappers."""

import aiohttp
import pytest
from aioresponses import aioresponses

from proconip.api import (
    BadCredentialsException,
    BadStatusCodeException,
    DmxControl,
    DosageControl,
    GetState,
    ProconipApiException,
    RelaySwitch,
    TimeoutException,
    async_get_dmx,
    async_get_raw_dmx,
    async_get_raw_state,
    async_get_state,
    async_set_auto_mode,
    async_set_dmx,
    async_start_dosage,
    async_switch_off,
    async_switch_on,
)
from proconip.definitions import ConfigObject, DosageTarget, GetDmxData, GetStateData

BASE_URL = "http://127.0.0.1"
GET_STATE_URL = f"{BASE_URL}/GetState.csv"
USRCFG_URL = f"{BASE_URL}/usrcfg.cgi"
GET_DMX_URL = f"{BASE_URL}/GetDmx.csv"

SIMPLE_STATE_CSV = "SYSINFO,1.7.3,0,0,0,0,257,4,4,5\ncol\nunit\n0\n1\n2,0,0,2,2,2,2,2\n"

SIMPLE_DMX_CSV = "0,10,20,30,40,50,60,70,80,90,100,110,120,130,140,150\n"


@pytest.fixture
def config() -> ConfigObject:
    return ConfigObject(BASE_URL, "admin", "admin")


# ---------------------------------------------------------------------------
# async_get_raw_state
# ---------------------------------------------------------------------------


async def test_get_raw_state_happy_path(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, body="raw_csv_response", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_get_raw_state(session, config)
    assert result == "raw_csv_response"


async def test_get_raw_state_401_raises_bad_credentials(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, status=401)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(BadCredentialsException):
                await async_get_raw_state(session, config)


async def test_get_raw_state_403_raises_bad_credentials(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, status=403)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(BadCredentialsException):
                await async_get_raw_state(session, config)


async def test_get_raw_state_500_raises_bad_status_code(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, status=500)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(BadStatusCodeException):
                await async_get_raw_state(session, config)


async def test_get_raw_state_timeout_raises_timeout_exception(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, exception=TimeoutError())
        async with aiohttp.ClientSession() as session:
            with pytest.raises(TimeoutException):
                await async_get_raw_state(session, config)


async def test_get_raw_state_connection_error_raises_api_exception(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, exception=aiohttp.ClientConnectionError("conn failed"))
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ProconipApiException):
                await async_get_raw_state(session, config)


# ---------------------------------------------------------------------------
# async_get_state
# ---------------------------------------------------------------------------


async def test_get_state_returns_parsed_data(config: ConfigObject, get_state_csv: str) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, body=get_state_csv, status=200)
        async with aiohttp.ClientSession() as session:
            state = await async_get_state(session, config)
    assert isinstance(state, GetStateData)
    assert state.version == "1.7.3"


# ---------------------------------------------------------------------------
# async_get_raw_dmx / async_get_dmx
# ---------------------------------------------------------------------------


async def test_get_raw_dmx(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_DMX_URL, body=SIMPLE_DMX_CSV, status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_get_raw_dmx(session, config)
    assert result == SIMPLE_DMX_CSV


async def test_get_dmx_returns_parsed_data(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_DMX_URL, body=SIMPLE_DMX_CSV, status=200)
        async with aiohttp.ClientSession() as session:
            dmx = await async_get_dmx(session, config)
    assert isinstance(dmx, GetDmxData)
    assert dmx.get_value(0) == 0
    assert dmx.get_value(15) == 150


async def test_get_dmx_401_raises_bad_credentials(config: ConfigObject) -> None:
    with aioresponses() as m:
        m.get(GET_DMX_URL, status=401)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(BadCredentialsException):
                await async_get_dmx(session, config)


# ---------------------------------------------------------------------------
# async_switch_on / async_switch_off / async_set_auto_mode
# ---------------------------------------------------------------------------


async def test_switch_on_sends_post(config: ConfigObject, get_state_csv: str) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)  # not a dosage relay
    with aioresponses() as m:
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_switch_on(session, config, state, relay)
    assert result == "ok"


async def test_switch_on_dosage_relay_raises_bad_relay(
    config: ConfigObject, get_state_csv: str
) -> None:
    from proconip.definitions import BadRelayException

    state = GetStateData(get_state_csv)
    # chlorine_dosage_relay_id = 5 from fixture SYSINFO
    dosage_relay = state.get_relay(5)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadRelayException):
            await async_switch_on(session, config, state, dosage_relay)


async def test_switch_off_sends_post(config: ConfigObject, get_state_csv: str) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    with aioresponses() as m:
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_switch_off(session, config, state, relay)
    assert result == "ok"


async def test_set_auto_mode_sends_post(config: ConfigObject, get_state_csv: str) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    with aioresponses() as m:
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_set_auto_mode(session, config, state, relay)
    assert result == "ok"


async def test_switch_on_401_raises_bad_credentials(
    config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    with aioresponses() as m:
        m.post(USRCFG_URL, status=401)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(BadCredentialsException):
                await async_switch_on(session, config, state, relay)


# ---------------------------------------------------------------------------
# async_start_dosage
# ---------------------------------------------------------------------------


async def test_start_dosage_chlorine(config: ConfigObject) -> None:
    expected_url = f"{BASE_URL}/Command.htm?MAN_DOSAGE=0,60"
    with aioresponses() as m:
        m.get(expected_url, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_start_dosage(session, config, DosageTarget.CHLORINE, 60)
    assert result == "ok"


async def test_start_dosage_ph_minus(config: ConfigObject) -> None:
    expected_url = f"{BASE_URL}/Command.htm?MAN_DOSAGE=1,120"
    with aioresponses() as m:
        m.get(expected_url, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_start_dosage(session, config, DosageTarget.PH_MINUS, 120)
    assert result == "ok"


# ---------------------------------------------------------------------------
# async_set_dmx
# ---------------------------------------------------------------------------


async def test_set_dmx_sends_post(config: ConfigObject, get_dmx_csv: str) -> None:
    dmx = GetDmxData(get_dmx_csv)
    with aioresponses() as m:
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            result = await async_set_dmx(session, config, dmx)
    assert result == "ok"


# ---------------------------------------------------------------------------
# OO class wrappers
# ---------------------------------------------------------------------------


async def test_get_state_class_get_raw_state(config: ConfigObject, get_state_csv: str) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, body=get_state_csv, status=200)
        async with aiohttp.ClientSession() as session:
            api = GetState(session, config)
            raw = await api.async_get_raw_state()
    assert raw == get_state_csv


async def test_get_state_class_get_state(config: ConfigObject, get_state_csv: str) -> None:
    with aioresponses() as m:
        m.get(GET_STATE_URL, body=get_state_csv, status=200)
        async with aiohttp.ClientSession() as session:
            api = GetState(session, config)
            state = await api.async_get_state()
    assert isinstance(state, GetStateData)


async def test_relay_switch_class(config: ConfigObject, get_state_csv: str) -> None:
    state = GetStateData(get_state_csv)
    with aioresponses() as m:
        m.post(USRCFG_URL, body="ok", status=200)
        m.post(USRCFG_URL, body="ok", status=200)
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            rs = RelaySwitch(session, config)
            await rs.async_switch_on(state, 0)
            await rs.async_switch_off(state, 0)
            await rs.async_set_auto_mode(state, 0)


async def test_dosage_control_class(config: ConfigObject) -> None:
    cmd_url_chlorine = f"{BASE_URL}/Command.htm?MAN_DOSAGE=0,60"
    cmd_url_ph_minus = f"{BASE_URL}/Command.htm?MAN_DOSAGE=1,30"
    cmd_url_ph_plus = f"{BASE_URL}/Command.htm?MAN_DOSAGE=2,45"
    with aioresponses() as m:
        m.get(cmd_url_chlorine, body="ok", status=200)
        m.get(cmd_url_ph_minus, body="ok", status=200)
        m.get(cmd_url_ph_plus, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            dc = DosageControl(session, config)
            await dc.async_chlorine_dosage(60)
            await dc.async_ph_minus_dosage(30)
            await dc.async_ph_plus_dosage(45)


async def test_dmx_control_class(config: ConfigObject, get_dmx_csv: str) -> None:
    dmx = GetDmxData(get_dmx_csv)
    with aioresponses() as m:
        m.get(GET_DMX_URL, body=SIMPLE_DMX_CSV, status=200)
        m.get(GET_DMX_URL, body=SIMPLE_DMX_CSV, status=200)
        m.post(USRCFG_URL, body="ok", status=200)
        async with aiohttp.ClientSession() as session:
            dc = DmxControl(session, config)
            raw = await dc.async_get_raw_dmx()
            parsed = await dc.async_get_dmx()
            await dc.async_set(dmx)
    assert raw == SIMPLE_DMX_CSV
    assert isinstance(parsed, GetDmxData)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_exception_hierarchy() -> None:
    assert issubclass(BadCredentialsException, ProconipApiException)
    assert issubclass(BadStatusCodeException, ProconipApiException)
    assert issubclass(TimeoutException, ProconipApiException)
