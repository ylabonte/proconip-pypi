"""Async API client for the ProCon.IP pool controller."""

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
    """Raised when an API call fails."""


class BadCredentialsException(ProconipApiException):
    """Raised when the controller responds with HTTP 401 or 403."""


class BadStatusCodeException(ProconipApiException):
    """Raised when the controller responds with an unexpected HTTP status code."""


class TimeoutException(ProconipApiException):
    """Raised when the API request times out."""


async def _handle_response(response: ClientResponse) -> str:
    """Validate a response and return its body, raising typed exceptions for failures."""
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
    """Request data from the given URL and return the raw response string."""
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
    """Get raw data (CSV string) from the /GetState.csv endpoint."""
    url = URL(config.base_url).with_path(API_PATH_GET_STATE)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


async def async_get_state(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> GetStateData:
    """Get structured data from the /GetState.csv endpoint."""
    raw_data = await async_get_raw_state(client_session, config, timeout=timeout)
    return GetStateData(raw_data)


class GetState:
    """OO wrapper for reading pool state from the /GetState.csv endpoint."""

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        self.client_session = client_session
        self.config = config

    async def async_get_raw_state(self) -> str:
        """Get raw data (CSV string) from the /GetState.csv endpoint."""
        return await async_get_raw_state(self.client_session, self.config)

    async def async_get_state(self) -> GetStateData:
        """Get structured data from the /GetState.csv endpoint."""
        return await async_get_state(self.client_session, self.config)


async def async_post_usrcfg_cgi(
    client_session: ClientSession,
    config: ConfigObject,
    payload: str,
    timeout: float = 10.0,
) -> str:
    """Send a POST request to the /usrcfg.cgi endpoint."""
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
    """Switch a relay to manual on.

    Raises BadRelayException for dosage control relays, which must not be switched manually.
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
    """Switch a relay to manual off."""
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
    """Switch a relay to auto mode."""
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
    """OO wrapper for relay switching via the /usrcfg.cgi endpoint."""

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        self.client_session = client_session
        self.config = config

    async def async_switch_on(self, current_state: GetStateData, relay_id: int) -> str:
        """Set relay with given aggregated relay ID to manual on."""
        return await async_switch_on(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_switch_off(self, current_state: GetStateData, relay_id: int) -> str:
        """Set relay with given aggregated relay ID to manual off."""
        return await async_switch_off(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_set_auto_mode(self, current_state: GetStateData, relay_id: int) -> str:
        """Set relay with given aggregated relay ID to auto mode."""
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
    """Start manual dosage for the given target and duration (in seconds)."""
    query = f"MAN_DOSAGE={dosage_target},{dosage_duration}"
    url = URL(config.base_url).with_path(API_PATH_COMMAND).with_query(query)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


class DosageControl:
    """OO wrapper for manual dosage control via the /Command.htm endpoint."""

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        self.client_session = client_session
        self.config = config

    async def async_chlorine_dosage(self, dosage_duration: int) -> str:
        """Start manual chlorine dosage for the given duration in seconds."""
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.CHLORINE,
            dosage_duration=dosage_duration,
        )

    async def async_ph_minus_dosage(self, dosage_duration: int) -> str:
        """Start manual pH- dosage for the given duration in seconds."""
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.PH_MINUS,
            dosage_duration=dosage_duration,
        )

    async def async_ph_plus_dosage(self, dosage_duration: int) -> str:
        """Start manual pH+ dosage for the given duration in seconds."""
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
    """Get raw data (CSV string) from the /GetDmx.csv endpoint."""
    url = URL(config.base_url).with_path(API_PATH_GET_DMX)
    return await async_get_raw_data(client_session, config, url, timeout=timeout)


async def async_get_dmx(
    client_session: ClientSession,
    config: ConfigObject,
    timeout: float = 10.0,
) -> GetDmxData:
    """Get structured DMX channel data from the /GetDmx.csv endpoint."""
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
    """Write DMX channel states to the controller."""
    payload = "&".join(f"{k}={v}" for k, v in dmx_states.post_data.items())
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=payload,
        timeout=timeout,
    )


class DmxControl:
    """OO wrapper for DMX channel control via /GetDmx.csv and /usrcfg.cgi."""

    def __init__(self, client_session: ClientSession, config: ConfigObject):
        """Initialize DmxControl with an active client session and config."""
        self.client_session = client_session
        self.config = config

    async def async_get_raw_dmx(self) -> str:
        """Get raw data (CSV string) from the /GetDmx.csv endpoint."""
        return await async_get_raw_dmx(self.client_session, self.config)

    async def async_get_dmx(self) -> GetDmxData:
        """Get structured DMX channel data from the /GetDmx.csv endpoint."""
        return await async_get_dmx(self.client_session, self.config)

    async def async_set(self, data: GetDmxData) -> str:
        """Write DMX channel states to the controller."""
        return await async_set_dmx(
            client_session=self.client_session,
            config=self.config,
            dmx_states=data,
        )
