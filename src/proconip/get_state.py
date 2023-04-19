"""GetState class to get data from the GetState.csv interface."""

from aiohttp import BasicAuth, ClientSession
from yarl import URL

from .definitions import ConfigObject, GetStateData


async def async_get_raw(client_session: ClientSession, config: ConfigObject) -> str:
    """Get raw data (csv string) from the GetState.csv interface."""
    url = URL(config.base_url).with_path("/GetState.csv")
    result = await client_session.get(url,
                                      auth=BasicAuth(config.username, password=config.password))
    if result.status == 200:
        return await result.text()
    if result.status in [401, 403]:
        raise BadCredentialsException


async def async_get_structured(client_session: ClientSession, config: ConfigObject) -> GetStateData:
    """Get structured data from the GetState.csv interface."""
    raw_data = await async_get_raw(client_session, config)
    structured_data = GetStateData(raw_data)

    return structured_data


class GetState:
    """GetState class to get data from the GetState.csv interface."""
    def __init__(self, client_session: ClientSession, config: ConfigObject):
        self.client_session = client_session
        self.config = config

    async def raw(self) -> str:
        """Get raw data (csv string) from the GetState.csv interface."""
        return await async_get_raw(self.client_session, self.config)

    async def structured(self) -> GetStateData:
        """Get structured data from the GetState.csv interface."""
        return await async_get_structured(self.client_session, self.config)


class BadCredentialsException(Exception):
    """Exception to raise when we get an 401 Unauthorized or 403 Forbidden response."""
