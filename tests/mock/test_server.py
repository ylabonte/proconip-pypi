"""Tests for the mock controller's aiohttp HTTP layer.

Uses `aiohttp.test_utils.TestClient` to exercise the routes in-process — no
sockets, no subprocesses. Auth, status codes, and the four endpoint contracts
are checked directly. End-to-end behavior with the real `proconip` client
lives in `tests/integration/`.
"""

from base64 import b64encode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from proconip.definitions import GetDmxData, GetStateData
from tools.proconip_mock.server import create_app
from tools.proconip_mock.state import MockState


def _basic(user: str, password: str) -> str:
    return "Basic " + b64encode(f"{user}:{password}".encode()).decode()


@pytest.fixture
def state() -> MockState:
    clock = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    return MockState(monotonic=lambda: next(clock))


@pytest.fixture
async def client(state: MockState) -> TestClient:
    app = create_app(state, username="admin", password="secret")
    async with TestClient(TestServer(app)) as client:
        yield client


class TestAuth:
    async def test_get_state_requires_auth(self, client: TestClient) -> None:
        response = await client.get("/GetState.csv")
        assert response.status == 401
        assert "Basic" in response.headers.get("WWW-Authenticate", "")

    async def test_wrong_password_rejected(self, client: TestClient) -> None:
        response = await client.get(
            "/GetState.csv", headers={"Authorization": _basic("admin", "wrong")}
        )
        assert response.status == 401

    async def test_correct_credentials_accepted(self, client: TestClient) -> None:
        response = await client.get(
            "/GetState.csv", headers={"Authorization": _basic("admin", "secret")}
        )
        assert response.status == 200


class TestGetStateRoute:
    async def test_returns_parseable_csv(self, client: TestClient) -> None:
        response = await client.get(
            "/GetState.csv", headers={"Authorization": _basic("admin", "secret")}
        )
        body = await response.text()
        # Real client should be able to parse the response without errors
        parsed = GetStateData(body)
        assert parsed.version


class TestGetDmxRoute:
    async def test_returns_parseable_csv(self, client: TestClient) -> None:
        response = await client.get(
            "/GetDmx.csv", headers={"Authorization": _basic("admin", "secret")}
        )
        body = await response.text()
        parsed = GetDmxData(body)
        assert parsed.get_value(0) == 0


class TestUsrcfgRelay:
    async def test_post_ena_updates_state(self, client: TestClient, state: MockState) -> None:
        response = await client.post(
            "/usrcfg.cgi",
            data="ENA=1,1&MANUAL=1",
            headers={
                "Authorization": _basic("admin", "secret"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        assert response.status == 200
        assert state.relay_enabled[0] is True
        assert state.relay_on[0] is True


class TestUsrcfgDmx:
    async def test_post_dmx_updates_state(self, client: TestClient, state: MockState) -> None:
        payload = "TYPE=0&LEN=16&CH1_8=1,2,3,4,5,6,7,8&CH9_16=9,10,11,12,13,14,15,16&DMX512=1"
        response = await client.post(
            "/usrcfg.cgi",
            data=payload,
            headers={
                "Authorization": _basic("admin", "secret"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        assert response.status == 200
        assert state.dmx == list(range(1, 17))


class TestCommandHtm:
    async def test_dosage_command_acks(self, client: TestClient) -> None:
        response = await client.get(
            "/Command.htm",
            params={"MAN_DOSAGE": "0,60"},
            headers={"Authorization": _basic("admin", "secret")},
        )
        assert response.status == 200
        text = await response.text()
        assert text.strip() == "OK"
