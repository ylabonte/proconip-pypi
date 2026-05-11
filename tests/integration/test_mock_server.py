"""End-to-end smoke test: real proconip client against the local mock subprocess.

Skipped by default (`-m 'not integration'` in pyproject.toml). Run with:

    pytest -m integration

Each test boots `python -m tools.proconip_mock` on a free port, exercises one
client surface, and shuts the subprocess down. No mocking — the real client
talks HTTP to the real mock.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import aiohttp
import pytest

from proconip import (
    ConfigObject,
    DosageTarget,
    GetDmxData,
    GetStateData,
    async_get_dmx,
    async_get_state,
    async_set_dmx,
    async_start_dosage,
    async_switch_off,
    async_switch_on,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_until_ready(host: str, port: int, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.05)
    raise RuntimeError(f"mock server did not start on {host}:{port} within {timeout_s}s")


@pytest.fixture
def mock_server() -> Iterator[ConfigObject]:
    port = _free_port()
    env = {
        **os.environ,
        "PROCONIP_MOCK_HOST": "127.0.0.1",
        "PROCONIP_MOCK_PORT": str(port),
        "PROCONIP_MOCK_USER": "admin",
        "PROCONIP_MOCK_PASS": "admin",
    }
    # Capture stdout+stderr so a failed startup (port conflict, import error,
    # missing dependency) surfaces actionable detail in the test report
    # rather than just "did not start within Xs".
    proc = subprocess.Popen(
        [sys.executable, "-m", "tools.proconip_mock"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        try:
            _wait_until_ready("127.0.0.1", port)
        except RuntimeError as exc:
            proc.terminate()
            try:
                output, _ = proc.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                output, _ = proc.communicate()
            tail = (output or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"{exc}\n--- mock subprocess output ---\n{tail or '(empty)'}\n--- end ---"
            ) from exc
        yield ConfigObject(f"http://127.0.0.1:{port}", "admin", "admin")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


async def test_get_state_round_trip(mock_server: ConfigObject) -> None:
    async with aiohttp.ClientSession() as session:
        state = await async_get_state(session, mock_server)
    assert isinstance(state, GetStateData)
    assert state.version  # SYSINFO row preserved through render → parse
    # Sensors at startup are at their drift-curve centers
    assert 7.30 <= state.ph_electrode.value <= 7.50
    assert 670 <= state.redox_electrode.value <= 730


async def test_relay_switch_round_trips(mock_server: ConfigObject) -> None:
    async with aiohttp.ClientSession() as session:
        before = await async_get_state(session, mock_server)
        relay = before.get_relay(0)
        await async_switch_on(session, mock_server, before, relay)

        after_on = await async_get_state(session, mock_server)
        assert after_on.get_relay(0).is_on()
        assert after_on.get_relay(0).is_manual_mode()

        await async_switch_off(session, mock_server, after_on, after_on.get_relay(0))
        after_off = await async_get_state(session, mock_server)
        assert after_off.get_relay(0).is_off()
        assert after_off.get_relay(0).is_manual_mode()


async def test_dmx_round_trips(mock_server: ConfigObject) -> None:
    async with aiohttp.ClientSession() as session:
        dmx = await async_get_dmx(session, mock_server)
        assert isinstance(dmx, GetDmxData)
        for index in range(16):
            dmx.set(index, (index + 1) * 10)
        await async_set_dmx(session, mock_server, dmx)

        readback = await async_get_dmx(session, mock_server)
    assert [readback.get_value(i) for i in range(16)] == [(i + 1) * 10 for i in range(16)]


async def test_manual_dosage_returns_ok(mock_server: ConfigObject) -> None:
    async with aiohttp.ClientSession() as session:
        result = await async_start_dosage(session, mock_server, DosageTarget.CHLORINE, 60)
    assert result.strip() == "OK"
