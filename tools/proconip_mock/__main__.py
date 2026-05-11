"""Run the mock controller as ``python -m tools.proconip_mock``.

Reads bind host, port, and credentials from environment variables, constructs
the aiohttp app, and serves it forever.

Default bind is **127.0.0.1** — the mock listens only on the loopback
interface, so the default `admin`/`admin` credentials aren't reachable from
the LAN. Environments that need external access (devcontainer port
forwarding, Codespaces) override this to `0.0.0.0` via
``PROCONIP_MOCK_HOST`` in ``.devcontainer/devcontainer.json``.
"""

import logging
import os

from aiohttp import web

from .server import create_app
from .state import MockState


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = _env("PROCONIP_MOCK_HOST", "127.0.0.1")
    port = int(_env("PROCONIP_MOCK_PORT", "8080"))
    username = _env("PROCONIP_MOCK_USER", "admin")
    password = _env("PROCONIP_MOCK_PASS", "admin")

    state = MockState()
    app = create_app(state, username=username, password=password)
    # When binding to an unspecified address (`0.0.0.0` / `::`), the literal
    # URL is not connectable from a client; substitute `localhost` so the log
    # line shows something a developer can paste into a browser or curl.
    display_host = "localhost" if host in ("0.0.0.0", "::") else host
    logging.getLogger("proconip_mock").info(
        "ProCon.IP mock listening on http://%s:%d (bind=%s, user=%s)",
        display_host,
        port,
        host,
        username,
    )
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    main()
