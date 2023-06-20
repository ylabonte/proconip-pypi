"""GetState class to get data from the GetState.csv interface."""
import asyncio
import socket
import async_timeout

from aiohttp import (
    BasicAuth,
    ClientError,
    ClientSession,
)
from yarl import URL

from .definitions import (
    API_PATH_GET_STATE,
    API_PATH_USRCFG,
    API_PATH_COMMAND,
    BadRelayException,
    ConfigObject,
    DosageTarget,
    GetStateData,
    Relay,
)


async def async_get_raw_state(
    client_session: ClientSession,
    config: ConfigObject,
) -> str:
    """Get raw data (csv string) from the GetState.csv interface."""
    url = URL(config.base_url).with_path(API_PATH_GET_STATE)
    try:
        async with async_timeout.timeout(10):
            response = await client_session.get(
                url,
                auth=BasicAuth(
                    config.username,
                    password=config.password
                ),
            )
            if response.status in (401, 403):
                raise BadCredentialsException("Invalid credentials")
            response.raise_for_status()
            return await response.text()
    except asyncio.TimeoutError as exception:
        raise ProconipApiException(
            "Timeout error fetching data",
        ) from exception
    except (ClientError, socket.gaierror) as exception:
        raise ProconipApiException(
            "Error fetching data",
        ) from exception
    except Exception as exception:  # pylint: disable=broad-except
        raise BadStatusCodeException(
            "Unexpected response",
        ) from exception


async def async_get_state(
    client_session: ClientSession,
    config: ConfigObject,
) -> GetStateData:
    """Get structured data from the GetState.csv interface."""
    raw_data = await async_get_raw_state(client_session, config)
    structured_data = GetStateData(raw_data)
    return structured_data


class GetState:
    """GetState class to get data from the GetState.csv interface."""
    def __init__(
        self,
        client_session: ClientSession,
        config: ConfigObject
    ):
        self.client_session = client_session
        self.config = config

    async def async_get_raw_state(
        self,
    ) -> str:
        """Get raw data (csv string) from the GetState.csv interface."""
        return await async_get_raw_state(
            self.client_session,
            self.config
        )

    async def async_get_state(
        self,
    ) -> GetStateData:
        """Get structured data from the GetState.csv interface."""
        return await async_get_state(
            self.client_session,
            self.config
        )


async def async_post_usrcfg_cgi(
    client_session: ClientSession,
    config: ConfigObject,
    payload: str,
) -> str:
    """Send post request to the /usrcfg.cgi endpoint."""
    url = URL(config.base_url).with_path(API_PATH_USRCFG)
    try:
        async with async_timeout.timeout(10):
            response = await client_session.post(
                url=url,
                data=payload,
                auth=BasicAuth(
                    login=config.username,
                    password=config.password,
                ),
            )
            response.raise_for_status()
            return await response.text()
    except asyncio.TimeoutError as exception:
        raise ProconipApiException(
            "Timeout error fetching data",
        ) from exception
    except (ClientError, socket.gaierror) as exception:
        raise ProconipApiException(
            "Error fetching data",
        ) from exception
    except Exception as exception:  # pylint: disable=broad-except
        raise BadStatusCodeException(
            "Unexpected response",
        ) from exception


async def async_switch_on(
        client_session: ClientSession,
        config: ConfigObject,
        current_state: GetStateData,
        relay: Relay,
) -> str:
    """Switch on a relay using the usrcfg.cgi interface."""
    if current_state.is_dosage_relay(relay):
        raise BadRelayException(
            "Cannot permanently switch on a dosage relay",
        )
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] |= relay_bit_mask
    bit_state[1] |= relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1"
    )


async def async_switch_off(
        client_session: ClientSession,
        config: ConfigObject,
        current_state: GetStateData,
        relay: Relay,
) -> str:
    """Switch on a relay using the usrcfg.cgi interface."""
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] |= relay_bit_mask
    bit_state[1] &= ~relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1",
    )


async def async_set_auto_mode(
        client_session: ClientSession,
        config: ConfigObject,
        current_state: GetStateData,
        relay: Relay,
) -> str:
    """Switch a relay to auto mode using the usrcfg.cgi interface."""
    bit_state = current_state.determine_overall_relay_bit_state()
    relay_bit_mask = relay.get_bit_mask()
    bit_state[0] &= ~relay_bit_mask
    bit_state[1] &= ~relay_bit_mask
    return await async_post_usrcfg_cgi(
        client_session=client_session,
        config=config,
        payload=f"ENA={bit_state[0]},{bit_state[1]}&MANUAL=1",
    )


class RelaySwitch:
    """RelaySwitch class to set relay states via usrcfg.cgi interface."""
    def __init__(
        self,
        client_session: ClientSession,
        config: ConfigObject,
    ):
        self.client_session = client_session
        self.config = config

    async def async_switch_on(
        self,
        current_state: GetStateData,
        relay_id: int,
    ) -> str:
        """Set relay with given id to manual on."""
        return await async_switch_on(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_switch_off(
        self,
        current_state: GetStateData,
        relay_id: int,
    ) -> str:
        """Set relay with given id to manual off."""
        return await async_switch_off(
            client_session=self.client_session,
            config=self.config,
            current_state=current_state,
            relay=current_state.get_relay(relay_id),
        )

    async def async_set_auto_mode(
        self,
        current_state: GetStateData,
        relay_id: int,
    ) -> str:
        """Set relay with given id to use auto mode."""
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
) -> str:
    """Start manual dosage for given target and duration."""
    query = f"MAN_DOSAGE={dosage_target},{dosage_duration}"
    url = URL(config.base_url).with_path(API_PATH_COMMAND).with_query(query)
    try:
        async with async_timeout.timeout(10):
            response = await client_session.get(
                url=url,
                auth=BasicAuth(
                    login=config.username,
                    password=config.password,
                ),
            )
            response.raise_for_status()
            return await response.text()
    except asyncio.TimeoutError as exception:
        raise ProconipApiException(
            "Timeout error fetching data",
        ) from exception
    except (ClientError, socket.gaierror) as exception:
        raise ProconipApiException(
            "Error fetching data",
        ) from exception
    except Exception as exception:  # pylint: disable=broad-except
        raise BadStatusCodeException(
            "Unexpected response",
        ) from exception


class DosageControl:
    """DosageControl class to start manual dosage via Command.htm endpoint."""
    def __init__(
        self,
        client_session: ClientSession,
        config: ConfigObject,
    ):
        self.client_session = client_session
        self.config = config

    async def async_chlorine_dosage(
        self,
        dosage_duration: int,
    ) -> str:
        """Start manual chlorine dosage."""
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.CHLORINE,
            dosage_duration=dosage_duration,
        )

    async def async_ph_minus_dosage(
        self,
        dosage_duration: int,
    ) -> str:
        """Start manual pH minus dosage."""
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.PH_MINUS,
            dosage_duration=dosage_duration
        )

    async def async_ph_plus_dosage(
        self,
        dosage_duration: int,
    ) -> str:
        """Start manual pH plus dosage."""
        return await async_start_dosage(
            client_session=self.client_session,
            config=self.config,
            dosage_target=DosageTarget.PH_PLUS,
            dosage_duration=dosage_duration
        )


class ProconipApiException(Exception):
    """Exception to raise when an api call fails."""


class BadCredentialsException(ProconipApiException):
    """Exception to raise when we get an 401 Unauthorized or 403 Forbidden response."""


class BadStatusCodeException(ProconipApiException):
    """Exception to raise when we get an unknown response code."""
