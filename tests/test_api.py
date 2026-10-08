"""Tests for the API module — HTTP layer, error mapping, and class wrappers.

Requests go over a real socket to `FakeController`, an in-process aiohttp
server, so the suite exercises whichever aiohttp version is installed end to
end (response construction, auth headers, timeouts) instead of a mocked
client internals layer.
"""

import asyncio
import base64
import socket
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from proconip.api import (
    BadCredentialsException,
    BadStatusCodeException,
    DigitalInputControl,
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
    async_trigger_digital_input,
)
from proconip.definitions import ConfigObject, DosageTarget, GetDmxData, GetStateData

GET_STATE_PATH = "/GetState.csv"
USRCFG_PATH = "/usrcfg.cgi"
GET_DMX_PATH = "/GetDmx.csv"

SIMPLE_DMX_CSV = "0,10,20,30,40,50,60,70,80,90,100,110,120,130,140,150\n"

_real_sleep = asyncio.sleep


@dataclass
class RecordedRequest:
    method: str
    path_qs: str
    body: str
    authorization: str | None


@dataclass
class _QueuedResponse:
    body: str
    status: int
    delay: float


class FakeController:
    """Stand-in ProCon.IP controller with queued responses per method and path.

    Each `add()` queues one response; requests consume them in order. An
    unmatched request gets a 404 so a wrong URL fails loudly.
    """

    def __init__(self) -> None:
        self.base_url = ""
        self.requests: list[RecordedRequest] = []
        self._responses: defaultdict[tuple[str, str], deque[_QueuedResponse]] = defaultdict(deque)

    def add(
        self, method: str, path_qs: str, *, body: str = "", status: int = 200, delay: float = 0.0
    ) -> None:
        self._responses[(method, path_qs)].append(_QueuedResponse(body, status, delay))

    def get(self, path_qs: str, *, body: str = "", status: int = 200, delay: float = 0.0) -> None:
        self.add("GET", path_qs, body=body, status=status, delay=delay)

    def post(self, path_qs: str, *, body: str = "", status: int = 200, delay: float = 0.0) -> None:
        self.add("POST", path_qs, body=body, status=status, delay=delay)

    def posts_to(self, path: str) -> list[RecordedRequest]:
        return [r for r in self.requests if r.method == "POST" and r.path_qs == path]

    async def handle(self, request: web.BaseRequest) -> web.Response:
        self.requests.append(
            RecordedRequest(
                method=request.method,
                path_qs=request.path_qs,
                body=await request.text(),
                authorization=request.headers.get("Authorization"),
            )
        )
        queue = self._responses.get((request.method, request.path_qs))
        if not queue:
            return web.Response(status=404, text=f"unexpected {request.method} {request.path_qs}")
        response = queue.popleft()
        if response.delay:
            await _real_sleep(response.delay)
        return web.Response(text=response.body, status=response.status)


@pytest.fixture
async def controller() -> AsyncIterator[FakeController]:
    fake = FakeController()
    async with RawTestServer(fake.handle) as server:
        fake.base_url = f"http://{server.host}:{server.port}"
        yield fake


@pytest.fixture
def config(controller: FakeController) -> ConfigObject:
    return ConfigObject(controller.base_url, "admin", "admin")


def _sleep_spy(
    on_hold: Callable[[float], Awaitable[None]],
) -> Callable[..., Awaitable[object]]:
    """Patch target for `asyncio.sleep` that only intercepts the hold delay.

    `proconip.api.asyncio` is the global asyncio module, so the patch is seen
    by aiohttp and the event loop too; every other sleep passes through.
    """

    async def fake_sleep(delay: float, *args: object) -> object:
        if delay == 0.6:
            return await on_hold(delay)
        return await _real_sleep(delay, *args)

    return fake_sleep


# ---------------------------------------------------------------------------
# async_get_raw_state
# ---------------------------------------------------------------------------


async def test_get_raw_state_happy_path(controller: FakeController, config: ConfigObject) -> None:
    controller.get(GET_STATE_PATH, body="raw_csv_response", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_get_raw_state(session, config)
    assert result == "raw_csv_response"


async def test_get_raw_state_401_raises_bad_credentials(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_STATE_PATH, status=401)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadCredentialsException):
            await async_get_raw_state(session, config)


async def test_get_raw_state_403_raises_bad_credentials(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_STATE_PATH, status=403)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadCredentialsException):
            await async_get_raw_state(session, config)


async def test_get_raw_state_500_raises_bad_status_code(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_STATE_PATH, status=500)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadStatusCodeException):
            await async_get_raw_state(session, config)


async def test_get_raw_state_timeout_raises_timeout_exception(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_STATE_PATH, body="too late", delay=1.0)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(TimeoutException):
            await async_get_raw_state(session, config, timeout=0.05)


async def test_get_raw_state_connection_error_raises_api_exception() -> None:
    # Bind and release a port so nothing is listening on it.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    unreachable = ConfigObject(f"http://127.0.0.1:{port}", "admin", "admin")
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProconipApiException):
            await async_get_raw_state(session, unreachable)


async def test_requests_send_basic_auth(controller: FakeController, config: ConfigObject) -> None:
    controller.get(GET_STATE_PATH, body="ok")
    controller.post(USRCFG_PATH, body="ok")
    controller.post(USRCFG_PATH, body="ok")
    async with aiohttp.ClientSession() as session:
        await async_get_raw_state(session, config)
        await async_trigger_digital_input(session, config, 0, hold_seconds=0)
    expected = "Basic " + base64.b64encode(b"admin:admin").decode()
    assert [r.authorization for r in controller.requests] == [expected] * 3


# ---------------------------------------------------------------------------
# async_get_state
# ---------------------------------------------------------------------------


async def test_get_state_returns_parsed_data(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    controller.get(GET_STATE_PATH, body=get_state_csv, status=200)
    async with aiohttp.ClientSession() as session:
        state = await async_get_state(session, config)
    assert isinstance(state, GetStateData)
    assert state.version == "1.7.3"


# ---------------------------------------------------------------------------
# async_get_raw_dmx / async_get_dmx
# ---------------------------------------------------------------------------


async def test_get_raw_dmx(controller: FakeController, config: ConfigObject) -> None:
    controller.get(GET_DMX_PATH, body=SIMPLE_DMX_CSV, status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_get_raw_dmx(session, config)
    assert result == SIMPLE_DMX_CSV


async def test_get_dmx_returns_parsed_data(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_DMX_PATH, body=SIMPLE_DMX_CSV, status=200)
    async with aiohttp.ClientSession() as session:
        dmx = await async_get_dmx(session, config)
    assert isinstance(dmx, GetDmxData)
    assert dmx.get_value(0) == 0
    assert dmx.get_value(15) == 150


async def test_get_dmx_401_raises_bad_credentials(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.get(GET_DMX_PATH, status=401)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadCredentialsException):
            await async_get_dmx(session, config)


# ---------------------------------------------------------------------------
# async_switch_on / async_switch_off / async_set_auto_mode
# ---------------------------------------------------------------------------


async def test_switch_on_sends_post(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)  # not a dosage relay
    controller.post(USRCFG_PATH, body="ok", status=200)
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


async def test_switch_off_sends_post(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    controller.post(USRCFG_PATH, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_switch_off(session, config, state, relay)
    assert result == "ok"


async def test_set_auto_mode_sends_post(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    controller.post(USRCFG_PATH, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_set_auto_mode(session, config, state, relay)
    assert result == "ok"


async def test_switch_on_401_raises_bad_credentials(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    relay = state.get_relay(0)
    controller.post(USRCFG_PATH, status=401)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadCredentialsException):
            await async_switch_on(session, config, state, relay)


# ---------------------------------------------------------------------------
# async_start_dosage
# ---------------------------------------------------------------------------


async def test_start_dosage_chlorine(controller: FakeController, config: ConfigObject) -> None:
    expected_path = "/Command.htm?MAN_DOSAGE=0,60"
    controller.get(expected_path, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_start_dosage(session, config, DosageTarget.CHLORINE, 60)
    assert result == "ok"


async def test_start_dosage_ph_minus(controller: FakeController, config: ConfigObject) -> None:
    expected_path = "/Command.htm?MAN_DOSAGE=1,120"
    controller.get(expected_path, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_start_dosage(session, config, DosageTarget.PH_MINUS, 120)
    assert result == "ok"


# ---------------------------------------------------------------------------
# async_set_dmx
# ---------------------------------------------------------------------------


async def test_set_dmx_sends_post(
    controller: FakeController, config: ConfigObject, get_dmx_csv: str
) -> None:
    dmx = GetDmxData(get_dmx_csv)
    controller.post(USRCFG_PATH, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_set_dmx(session, config, dmx)
    assert result == "ok"


# ---------------------------------------------------------------------------
# async_trigger_digital_input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("digital_input_id", "expected_mask"),
    [(0, 1), (1, 2), (2, 4), (3, 8)],
)
async def test_trigger_digital_input_sends_posts(
    controller: FakeController, config: ConfigObject, digital_input_id: int, expected_mask: int
) -> None:
    controller.post(USRCFG_PATH, body="press-ok", status=200)
    controller.post(USRCFG_PATH, body="release-ok", status=200)
    async with aiohttp.ClientSession() as session:
        result = await async_trigger_digital_input(
            session, config, digital_input_id, hold_seconds=0
        )
    posts = controller.posts_to(USRCFG_PATH)
    assert len(posts) == 2
    assert posts[0].body == f"IO={expected_mask}&WEBIO=1"
    assert posts[1].body == "IO=0&WEBIO=1"
    # The function returns the *release* response body.
    assert result == "release-ok"


@pytest.mark.parametrize("digital_input_id", [-1, 4, 99])
async def test_trigger_digital_input_invalid_id_raises(
    controller: FakeController, config: ConfigObject, digital_input_id: int
) -> None:
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ValueError):
            await async_trigger_digital_input(session, config, digital_input_id)
    assert controller.posts_to(USRCFG_PATH) == []


async def test_trigger_digital_input_401_raises_bad_credentials(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.post(USRCFG_PATH, status=401)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BadCredentialsException):
            await async_trigger_digital_input(session, config, 0)


async def test_trigger_digital_input_holds_high_between_posts(
    controller: FakeController, config: ConfigObject
) -> None:
    """By default the input is held HIGH ~600ms between press and release.

    Mirrors the controller's web UI, which waits before clearing the bit.
    asyncio.sleep is patched so the test stays fast while proving the hold
    happens *between* the two POSTs (one POST recorded when sleep fires).
    """
    posts_at_sleep: list[int] = []

    async def record_sleep(delay: float) -> None:
        posts_at_sleep.append(len(controller.posts_to(USRCFG_PATH)))
        assert delay == 0.6

    controller.post(USRCFG_PATH, body="press-ok", status=200)
    controller.post(USRCFG_PATH, body="release-ok", status=200)
    with patch("proconip.api.asyncio.sleep", side_effect=_sleep_spy(record_sleep)):
        async with aiohttp.ClientSession() as session:
            result = await async_trigger_digital_input(session, config, 0)

    assert result == "release-ok"
    assert len(controller.posts_to(USRCFG_PATH)) == 2
    # sleep fired exactly once, after the press POST and before the release.
    assert posts_at_sleep == [1]


async def test_trigger_digital_input_releases_on_cancel(
    controller: FakeController, config: ConfigObject
) -> None:
    """A cancelled hold still attempts a best-effort release, then re-raises.

    Otherwise a press would set the bit and the cancellation would leave the
    input asserted HIGH with no release.
    """

    async def cancel_during_hold(delay: float) -> None:
        raise asyncio.CancelledError

    controller.post(USRCFG_PATH, body="press-ok", status=200)
    controller.post(USRCFG_PATH, body="release-ok", status=200)
    with patch("proconip.api.asyncio.sleep", side_effect=_sleep_spy(cancel_during_hold)):
        async with aiohttp.ClientSession() as session:
            with pytest.raises(asyncio.CancelledError):
                await async_trigger_digital_input(session, config, 0)
    posts = controller.posts_to(USRCFG_PATH)
    assert [p.body for p in posts] == ["IO=1&WEBIO=1", "IO=0&WEBIO=1"]


def test_digital_input_count_is_exported_from_package() -> None:
    from proconip import DIGITAL_INPUT_COUNT

    assert DIGITAL_INPUT_COUNT == 4


# ---------------------------------------------------------------------------
# OO class wrappers
# ---------------------------------------------------------------------------


async def test_get_state_class_get_raw_state(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    controller.get(GET_STATE_PATH, body=get_state_csv, status=200)
    async with aiohttp.ClientSession() as session:
        api = GetState(session, config)
        raw = await api.async_get_raw_state()
    assert raw == get_state_csv


async def test_get_state_class_get_state(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    controller.get(GET_STATE_PATH, body=get_state_csv, status=200)
    async with aiohttp.ClientSession() as session:
        api = GetState(session, config)
        state = await api.async_get_state()
    assert isinstance(state, GetStateData)


async def test_relay_switch_class(
    controller: FakeController, config: ConfigObject, get_state_csv: str
) -> None:
    state = GetStateData(get_state_csv)
    controller.post(USRCFG_PATH, body="ok", status=200)
    controller.post(USRCFG_PATH, body="ok", status=200)
    controller.post(USRCFG_PATH, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        rs = RelaySwitch(session, config)
        await rs.async_switch_on(state, 0)
        await rs.async_switch_off(state, 0)
        await rs.async_set_auto_mode(state, 0)


async def test_dosage_control_class(controller: FakeController, config: ConfigObject) -> None:
    cmd_url_chlorine = "/Command.htm?MAN_DOSAGE=0,60"
    cmd_url_ph_minus = "/Command.htm?MAN_DOSAGE=1,30"
    cmd_url_ph_plus = "/Command.htm?MAN_DOSAGE=2,45"
    controller.get(cmd_url_chlorine, body="ok", status=200)
    controller.get(cmd_url_ph_minus, body="ok", status=200)
    controller.get(cmd_url_ph_plus, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        dc = DosageControl(session, config)
        await dc.async_chlorine_dosage(60)
        await dc.async_ph_minus_dosage(30)
        await dc.async_ph_plus_dosage(45)


async def test_dmx_control_class(
    controller: FakeController, config: ConfigObject, get_dmx_csv: str
) -> None:
    dmx = GetDmxData(get_dmx_csv)
    controller.get(GET_DMX_PATH, body=SIMPLE_DMX_CSV, status=200)
    controller.get(GET_DMX_PATH, body=SIMPLE_DMX_CSV, status=200)
    controller.post(USRCFG_PATH, body="ok", status=200)
    async with aiohttp.ClientSession() as session:
        dc = DmxControl(session, config)
        raw = await dc.async_get_raw_dmx()
        parsed = await dc.async_get_dmx()
        await dc.async_set(dmx)
    assert raw == SIMPLE_DMX_CSV
    assert isinstance(parsed, GetDmxData)


async def test_digital_input_control_class(
    controller: FakeController, config: ConfigObject
) -> None:
    controller.post(USRCFG_PATH, body="press-ok", status=200)
    controller.post(USRCFG_PATH, body="release-ok", status=200)
    async with aiohttp.ClientSession() as session:
        dic = DigitalInputControl(session, config)
        result = await dic.async_trigger(2, hold_seconds=0)
    posts = controller.posts_to(USRCFG_PATH)
    assert [p.body for p in posts] == ["IO=4&WEBIO=1", "IO=0&WEBIO=1"]
    assert result == "release-ok"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_exception_hierarchy() -> None:
    assert issubclass(BadCredentialsException, ProconipApiException)
    assert issubclass(BadStatusCodeException, ProconipApiException)
    assert issubclass(TimeoutException, ProconipApiException)
