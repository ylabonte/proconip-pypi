"""Async HTTP client for the ProCon.IP pool controller.

The controller exposes four HTTP endpoints — `/GetState.csv` for sensor and
relay state, `/GetDmx.csv` for DMX channel state, `/usrcfg.cgi` for
configuration writes (including manual relay switching and DMX updates), and
`/Command.htm` for manual dosage commands. This module wraps all four with
typed exceptions and a configurable per-request timeout.

Each operation is available in two equivalent forms:

- **Free async functions** like `async_get_state` and `async_switch_on`. These
  take an `aiohttp.ClientSession` and `ConfigObject` explicitly, which makes
  them composable in larger applications that already manage their own
  session lifecycle.
- **OO wrappers** like `GetState`, `RelaySwitch`, `DosageControl`, and
  `DmxControl`. These bind the session and config once at construction and
  expose ergonomic instance methods so callers don't have to repeat those
  arguments on every call.

The OO wrappers delegate to the free functions, so behavior is identical.

All requests use HTTP Basic auth and run inside an `asyncio.timeout` block
that covers both the request and the response body read. Network failures,
HTTP error codes, and timeouts are all mapped to `ProconipApiException`
subclasses so callers can handle them uniformly.
"""

import asyncio
import socket

from aiohttp import (
    BasicAuth,
    ClientError,
    ClientResponse,
    ClientSession,
)
from yarl import URL

from .definitions import (
    API_PATH_COMMAND,
    API_PATH_GET_DMX,
    API_PATH_GET_STATE,
    API_PATH_USRCFG,
    BadRelayException,
    ConfigObject,
    DosageTarget,
    GetDmxData,
    GetStateData,
    Relay,
)


class ProconipApiException(Exception):
    """Base exception for any failed API call.

    Catch this if you want to handle all controller-side and network failures
    uniformly. The more specific subclasses below let you distinguish auth,
    HTTP, and timeout problems when that's useful.
    """


class BadCredentialsException(ProconipApiException):
    """Raised when the controller rejects the request with HTTP 401 or 403.

    Almost always means the username or password in the `ConfigObject` is wrong.
    """


class BadStatusCodeException(ProconipApiException):
    """Raised on any unexpected HTTP error status (4xx or 5xx) other than 401/403.

    The original `aiohttp.ClientResponseError` is preserved as the cause and
    can be inspected via `__cause__` if the status code or response details
    are needed.
    """


class TimeoutException(ProconipApiException):
    """Raised when a request does not complete within the configured timeout.

    This covers both network-level stalls (connection or socket I/O) and slow
    response bodies, since the timeout context wraps the entire exchange.
    """


async def _handle_response(response: ClientResponse) -> str:
    """Validate the response and return its body, mapping HTTP errors to typed exceptions."""
    if response.status in (401, 403):
        raise BadCredentialsException("Invalid credentials")
    try:
        response.raise_for_status()
    except ClientError as exc:
        raise BadStatusCodeException(f"Unexpected response status {response.status}") from exc
    return await response.text()


async def async_get_raw_data(
    client_session: ClientSession,
    config: ConfigObject,
    url: URL,
    timeout: float = 10.0,
) -> str:
    """Send an authenticated GET request and return the response body as text.

    This is the low-level primitive used by the higher-level state, DMX, and
    dosage helpers. Most callers will want one of those instead — reach for
    this directly only when you need to hit a custom URL on the controller.

    Args:
        client_session: An open `aiohttp.ClientSession` owned and closed by
            the caller. Reuse one session across many calls for connection
            pooling.
        config: Controller configuration. The username and password are sent
            as HTTP Basic auth credentials.
        url: Fully-qualified URL to GET. Build it from `config.base_url` plus
            an `API_PATH_*` constant if you want to stay close to the
            standard endpoints.
        timeout: Maximum seconds to wait for the entire exchange (request and
            response body). Defaults to 10 seconds.

    Returns:
        The raw response body as a string. The controller typically returns
        CSV; the caller is responsible for parsing.

    Raises:
        BadCredentialsException: If the controller responds with HTTP 401 or 403.
        BadStatusCodeException: If any other 4xx or 5xx status is returned.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For DNS failures, connection resets, and other
            network-level errors.
    """
    auth = BasicAuth(config.username, config.password)
    try:
        async with asyncio.timeout(timeout):
            async with client_session.get(url, auth=auth) as response:
                return await _handle_response(response)
    except TimeoutError as exc:
        raise TimeoutException("API request timed out") from exc
    except (ClientError, socket.gaierror) as exc:
        raise ProconipApiException(f"API request failed ({exc})") from exc


async def async_get_raw_state(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> str:
    """Fetch the raw `/GetState.csv` body from the controller.

    Use this when you want to handle the CSV yourself. To get a parsed
    object, call `async_get_state` instead.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration including base URL and credentials.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw multi-line CSV body returned by the controller.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors (DNS, connection reset).
    """
    url = URL(config.base_url).with_path(API_PATH_GET_STATE)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


async def async_get_state(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> GetStateData:
    """Fetch and parse the controller's current state.

    This is the most common entry point: it performs the GET request, parses
    the CSV response, and returns a `GetStateData` containing all sensor
    readings, relay states, dosage configuration, and so on.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration including base URL and credentials.
        timeout: Per-request timeout in seconds.

    Returns:
        A `GetStateData` instance with all properties populated.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
        InvalidPayloadException: If the response is empty or truncated.
    """
    raw_data = await async_get_raw_state(client_session, config, timeout=timeout)
    return GetStateData(raw_data)


class GetState:
    """Convenience wrapper that binds a session and config for state reads.

    Construct once with your `aiohttp.ClientSession` and `ConfigObject`, then
    call `async_get_state()` (parsed) or `async_get_raw_state()` (CSV) without
    repeating those arguments each time.

    Example:
        ```python
        async with aiohttp.ClientSession() as session:
            api = GetState(session, config)
            state = await api.async_get_state()
            print(state.ph_electrode.display_value)
        ```
    """

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        """Bind the session and config used by every method on this instance."""
        self.client_session = client_session
        self.config = config

    async def async_get_raw_state(self) -> str:
        """Fetch the raw `/GetState.csv` body using the bound session and config.

        See `async_get_raw_state` (the free function) for the full description
        of behavior and raised exceptions.
        """
        return await async_get_raw_state(self.client_session, self.config)

    async def async_get_state(self) -> GetStateData:
        """Fetch and parse the controller state into a `GetStateData` instance.

        See `async_get_state` (the free function) for the full description of
        behavior and raised exceptions.
        """
        return await async_get_state(self.client_session, self.config)


async def async_post_usrcfg_cgi(
    client_session: ClientSession,
    config: ConfigObject,
    payload: str,
    timeout: float = 10.0,
) -> str:
    """Send a form-encoded POST to `/usrcfg.cgi`.

    This is the low-level primitive behind relay switching and DMX writes.
    Most callers want `async_switch_on`, `async_switch_off`,
    `async_set_auto_mode`, or `async_set_dmx` instead. Use this directly only
    when you need to send a payload the higher-level helpers don't construct.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration including base URL and credentials.
        payload: The pre-encoded `application/x-www-form-urlencoded` body.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by the controller.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    url = URL(config.base_url).with_path(API_PATH_USRCFG)
    auth = BasicAuth(config.username, config.password)
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    try:
        async with asyncio.timeout(timeout):
            async with client_session.post(
                url=url,
                headers=headers,
                data=payload,
                auth=auth,
            ) as response:
                return await _handle_response(response)
    except TimeoutError as exc:
        raise TimeoutException("API request timed out") from exc
    except (ClientError, socket.gaierror) as exc:
        raise ProconipApiException(f"API request failed ({exc})") from exc


async def async_switch_on(
    client_session: ClientSession,
    config: ConfigObject,
    current_state: GetStateData,
    relay: Relay,
    timeout: float = 10.0,
) -> str:
    """Switch a relay to manual ON.

    Manual mode overrides the controller's schedule until the relay is
    explicitly switched off or set back to auto. Other relays in
    ``current_state`` are preserved by reading their bit field, which is why
    a fresh `GetStateData` snapshot is required.

    Dosage relays (chlorine, pH+, pH-) cannot be switched on this way — the
    controller's safety logic interlocks them. Use `async_start_dosage` (or
    `DosageControl`) instead for time-limited manual dosing.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        current_state: A recent `GetStateData` snapshot. Used to compute the
            ENA bit field so that other relays keep their current state.
        relay: The relay to switch on.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by `/usrcfg.cgi`.

    Raises:
        BadRelayException: If ``relay`` is one of the configured dosage
            control relays.
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    if current_state.is_dosage_relay(relay):
        raise BadRelayException("Cannot permanently switch on a dosage relay")
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] |= relay_bit_mask
    bit_state[1] |= relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1",
        timeout=timeout,
    )


async def async_switch_off(
    client_session: ClientSession,
    config: ConfigObject,
    current_state: GetStateData,
    relay: Relay,
    timeout: float = 10.0,
) -> str:
    """Switch a relay to manual OFF.

    Like `async_switch_on`, this puts the relay into manual mode but with the
    output disabled. Other relays in ``current_state`` keep their state.
    Unlike switching on, this is allowed for dosage relays — turning a dosage
    pump off is always safe.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        current_state: A recent `GetStateData` snapshot used to compute the
            ENA bit field.
        relay: The relay to switch off.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by `/usrcfg.cgi`.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] |= relay_bit_mask
    bit_state[1] &= ~relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1",
        timeout=timeout,
    )


async def async_set_auto_mode(
    client_session: ClientSession,
    config: ConfigObject,
    current_state: GetStateData,
    relay: Relay,
    timeout: float = 10.0,
) -> str:
    """Hand a relay back to the controller's automatic schedule.

    This is the inverse of `async_switch_on`/`async_switch_off`: instead of
    forcing a manual state, the relay's behavior is governed by the
    controller's configured rules (timer, sensor thresholds, dosage logic).

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        current_state: A recent `GetStateData` snapshot used to compute the
            ENA bit field.
        relay: The relay to put back into auto mode.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by `/usrcfg.cgi`.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] &= ~relay_bit_mask
    bit_state[1] &= ~relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1",
        timeout=timeout,
    )


class RelaySwitch:
    """Convenience wrapper that binds a session and config for relay control.

    Construct once with your `aiohttp.ClientSession` and `ConfigObject`, then
    switch relays by **aggregated relay ID** (an integer) instead of
    constructing `Relay` instances by hand.

    Aggregated relay IDs run from 0 to 7 for the eight built-in relays and 8
    to 15 for the eight optional external relays.

    Example:
        ```python
        rs = RelaySwitch(session, config)
        state = await GetState(session, config).async_get_state()
        await rs.async_switch_on(state, relay_id=2)
        ```
    """

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        """Bind the session and config used by every method on this instance."""
        self.client_session = client_session
        self.config = config

    async def async_switch_on(self, current_state: GetStateData, relay_id: int) -> str:
        """Switch the relay identified by ``relay_id`` to manual ON.

        Resolves the relay ID against ``current_state`` and delegates to the
        free function `async_switch_on`. See it for the full description of
        behavior and raised exceptions, including `BadRelayException` for
        dosage relays.
        """
        return await async_switch_on(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_switch_off(self, current_state: GetStateData, relay_id: int) -> str:
        """Switch the relay identified by ``relay_id`` to manual OFF.

        Resolves the relay ID against ``current_state`` and delegates to the
        free function `async_switch_off`. See it for the full description of
        behavior and raised exceptions.
        """
        return await async_switch_off(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_set_auto_mode(self, current_state: GetStateData, relay_id: int) -> str:
        """Hand the relay identified by ``relay_id`` back to AUTO mode.

        Resolves the relay ID against ``current_state`` and delegates to the
        free function `async_set_auto_mode`. See it for the full description
        of behavior and raised exceptions.
        """
        return await async_set_auto_mode(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )


async def async_start_dosage(
    client_session: ClientSession,
    config: ConfigObject,
    dosage_target: DosageTarget,
    dosage_duration: int,
    timeout: float = 10.0,
) -> str:
    """Trigger a manual, time-limited dosage on the controller.

    Manual dosage is the safe alternative to switching a dosage relay on
    directly: the controller still applies the same interlocks it uses for the
    web UI (canister level, dosage enabled in config, redox/pH thresholds, …).
    If those checks fail, the controller silently no-ops while still returning
    HTTP 200 — there is no "dosage refused" error in the protocol.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        dosage_target: Which dosing pump to engage (chlorine, pH-, or pH+).
        dosage_duration: Run time in **seconds**. Allowed range depends on the
            controller's own dosage configuration; values that exceed the
            configured maximum are typically clamped silently by the device.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by `/Command.htm`.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    query = f"MAN_DOSAGE={dosage_target},{dosage_duration}"
    url = URL(config.base_url).with_path(API_PATH_COMMAND).with_query(query)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


class DosageControl:
    """Convenience wrapper for manual dosage commands.

    Construct once with your `aiohttp.ClientSession` and `ConfigObject`, then
    trigger dosing per chemical without specifying the `DosageTarget` enum
    each time.

    Example:
        ```python
        dc = DosageControl(session, config)
        await dc.async_chlorine_dosage(60)   # 60 seconds of chlorine
        ```
    """

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        """Bind the session and config used by every method on this instance."""
        self.client_session = client_session
        self.config = config

    async def async_chlorine_dosage(self, dosage_duration: int) -> str:
        """Run the chlorine dosage pump for ``dosage_duration`` seconds.

        Subject to the same controller-side safety interlocks as manual
        dosage from the web UI. See `async_start_dosage` for full behavior
        and raised exceptions.
        """
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.CHLORINE,
            dosage_duration=dosage_duration,
        )

    async def async_ph_minus_dosage(self, dosage_duration: int) -> str:
        """Run the pH- dosage pump for ``dosage_duration`` seconds.

        Subject to the same controller-side safety interlocks as manual
        dosage from the web UI. See `async_start_dosage` for full behavior
        and raised exceptions.
        """
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.PH_MINUS,
            dosage_duration=dosage_duration,
        )

    async def async_ph_plus_dosage(self, dosage_duration: int) -> str:
        """Run the pH+ dosage pump for ``dosage_duration`` seconds.

        Subject to the same controller-side safety interlocks as manual
        dosage from the web UI. See `async_start_dosage` for full behavior
        and raised exceptions.
        """
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.PH_PLUS,
            dosage_duration=dosage_duration,
        )


async def async_get_raw_dmx(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> str:
    """Fetch the raw `/GetDmx.csv` body — the current 16 DMX channel values.

    Use this when you want to parse the CSV yourself. To get a structured
    `GetDmxData` you can read and mutate, call `async_get_dmx` instead.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        timeout: Per-request timeout in seconds.

    Returns:
        A single CSV line containing the 16 channel values.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    url = URL(config.base_url).with_path(API_PATH_GET_DMX)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


async def async_get_dmx(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> GetDmxData:
    """Fetch and parse the controller's DMX channel state.

    Returns a mutable `GetDmxData` you can iterate over, read with `[index]`,
    or modify with `set(index, value)`. Pass it to `async_set_dmx` to push
    the changes back to the controller.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        timeout: Per-request timeout in seconds.

    Returns:
        A `GetDmxData` containing all 16 DMX channels.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
        InvalidPayloadException: If the response is empty.
    """
    raw_data = await async_get_raw_dmx(
        client_session=client_session, config=config, timeout=timeout
    )
    return GetDmxData(raw_data)


async def async_set_dmx(
    client_session: ClientSession,
    config: ConfigObject,
    dmx_states: GetDmxData,
    timeout: float = 10.0,
) -> str:
    """Push DMX channel values back to the controller.

    The controller's API only accepts the full 16-channel state in a single
    write. The usual pattern is: fetch with `async_get_dmx`, mutate channels
    with `dmx_states.set(index, value)`, then call this function to commit.

    Args:
        client_session: An open `aiohttp.ClientSession`.
        config: Controller configuration.
        dmx_states: The full DMX state to write. All 16 channels are sent.
        timeout: Per-request timeout in seconds.

    Returns:
        The raw response body returned by `/usrcfg.cgi`.

    Raises:
        BadCredentialsException: On HTTP 401 or 403.
        BadStatusCodeException: On any other 4xx or 5xx response.
        TimeoutException: If the exchange exceeds ``timeout`` seconds.
        ProconipApiException: For network-level errors.
    """
    payload = "&".join(f"{k}={v}" for k, v in dmx_states.post_data.items())
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=payload,
        timeout=timeout,
    )


class DmxControl:
    """Convenience wrapper that binds a session and config for DMX I/O.

    Construct once with your `aiohttp.ClientSession` and `ConfigObject`, then
    read or write DMX channels without repeating those arguments each time.

    Example:
        ```python
        dc = DmxControl(session, config)
        dmx = await dc.async_get_dmx()
        for ch in dmx:
            dmx.set(ch.index, (ch.value + 64) % 256)
        await dc.async_set(dmx)
        ```
    """

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        """Bind the session and config used by every method on this instance."""
        self.client_session = client_session
        self.config = config

    async def async_get_raw_dmx(self) -> str:
        """Fetch the raw `/GetDmx.csv` body using the bound session and config.

        See `async_get_raw_dmx` (the free function) for the full description
        of behavior and raised exceptions.
        """
        return await async_get_raw_dmx(self.client_session, self.config)

    async def async_get_dmx(self) -> GetDmxData:
        """Fetch and parse the current DMX state into a `GetDmxData` instance.

        See `async_get_dmx` (the free function) for the full description of
        behavior and raised exceptions.
        """
        return await async_get_dmx(self.client_session, self.config)

    async def async_set(self, data: GetDmxData) -> str:
        """Push the given DMX state back to the controller.

        See `async_set_dmx` (the free function) for the full description of
        behavior and raised exceptions.
        """
        return await async_set_dmx(
            client_session=self.client_session,
            config=self.config,
            dmx_states=data,
        )
