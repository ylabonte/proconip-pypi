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
from tools.proconip_mock.server import _sanitize_for_log, create_app
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


class TestErrorResponsesDoNotLeakExceptionText:
    """CodeQL: error responses must not echo internal exception details
    (information exposure through an exception)."""

    async def test_invalid_ena_payload_returns_generic_message(self, client: TestClient) -> None:
        response = await client.post(
            "/usrcfg.cgi",
            data="ENA=not-a-number,0&MANUAL=1",
            headers={
                "Authorization": _basic("admin", "secret"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        body = await response.text()
        assert response.status == 400
        # The literal from a Python int() failure must not appear
        assert "invalid literal" not in body.lower()
        assert "not-a-number" not in body
        # And the body should be short — generic error, not a stack trace
        assert len(body) < 80

    async def test_invalid_dmx_payload_returns_generic_message(self, client: TestClient) -> None:
        response = await client.post(
            "/usrcfg.cgi",
            data="TYPE=0&LEN=16&CH1_8=oops,2,3,4,5,6,7,8&CH9_16=0,0,0,0,0,0,0,0&DMX512=1",
            headers={
                "Authorization": _basic("admin", "secret"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        body = await response.text()
        assert response.status == 400
        assert "invalid literal" not in body.lower()
        assert "oops" not in body
        assert len(body) < 80


class TestSanitizeForLog:
    """CodeQL: user-controlled values logged into a single line must be
    stripped of control characters that could spoof other log entries."""

    def test_passes_printable_through(self) -> None:
        assert _sanitize_for_log("0,60") == "0,60"

    def test_strips_newlines_to_prevent_log_injection(self) -> None:
        # Newlines collapsed → attacker can't forge a fake second log entry.
        # Surrounding printable text is preserved so logs remain useful.
        cleaned = _sanitize_for_log("0,60\nFAKE LOG LINE\r\n")
        assert "\n" not in cleaned
        assert "\r" not in cleaned
        assert cleaned == "0,60FAKE LOG LINE"

    def test_strips_other_control_chars(self) -> None:
        # ESC, NUL, BEL — anything not isprintable
        assert _sanitize_for_log("a\x00b\x07c\x1bd") == "abcd"

    def test_truncates_long_input(self) -> None:
        out = _sanitize_for_log("x" * 500)
        assert len(out) < 100  # well below the unbounded input length
        assert out.endswith("...")

    def test_empty_input(self) -> None:
        assert _sanitize_for_log("") == ""
