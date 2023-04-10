from aiohttp import BasicAuth, ClientSession
from yarl import URL

from .definitions import ConfigObject


async def async_get_raw(client_session: ClientSession, config: ConfigObject):
    """Get raw data (csv string) from the GetState.csv interface."""
    url = URL(config.base_url).with_path("/GetState.csv")
    result = await client_session.get(url, auth=BasicAuth(config.username, password=config.password))
    if result.status == 200:
        return result.text()
    elif result.status in [401, 403]:
        raise BadCredentialsException


async def async_get_structured(client_session: ClientSession, config: ConfigObject):
    """Get structured data from the GetState.csv interface."""
    #TODO structure!
    return await async_get_raw(client_session, config)


class BadCredentialsException(Exception):
    """Exception to raise when we get an 401 Unauthorized or 403 Forbidden response."""
