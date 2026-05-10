"""Async Python library for interacting with the ProCon.IP pool controller."""

try:
    from ._version import __version__
except ImportError:  # pragma: no cover
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("proconip")
    except PackageNotFoundError:
        __version__ = "0.0.0.dev0"

from .api import (
    BadCredentialsException,
    BadStatusCodeException,
    DmxControl,
    DosageControl,
    GetState,
    ProconipApiException,
    RelaySwitch,
    TimeoutException,
    async_get_dmx,
    async_get_raw_data,
    async_get_raw_dmx,
    async_get_raw_state,
    async_get_state,
    async_post_usrcfg_cgi,
    async_set_auto_mode,
    async_set_dmx,
    async_start_dosage,
    async_switch_off,
    async_switch_on,
)
from .definitions import (
    CATEGORY_ANALOG,
    CATEGORY_CANISTER,
    CATEGORY_CONSUMPTION,
    CATEGORY_DIGITAL_INPUT,
    CATEGORY_ELECTRODE,
    CATEGORY_EXTERNAL_RELAY,
    CATEGORY_RELAY,
    CATEGORY_TEMPERATURE,
    CATEGORY_TIME,
    EXTERNAL_RELAY_ID_OFFSET,
    BadRelayException,
    ConfigObject,
    DataObject,
    DmxChannelData,
    DosageTarget,
    GetDmxData,
    GetStateData,
    InvalidPayloadException,
    Relay,
)

__all__ = [
    "__version__",
    # exceptions
    "ProconipApiException",
    "BadCredentialsException",
    "BadStatusCodeException",
    "TimeoutException",
    "BadRelayException",
    "InvalidPayloadException",
    # config
    "ConfigObject",
    # data classes
    "DataObject",
    "Relay",
    "GetStateData",
    "DmxChannelData",
    "GetDmxData",
    # enums
    "DosageTarget",
    # constants
    "EXTERNAL_RELAY_ID_OFFSET",
    "CATEGORY_TIME",
    "CATEGORY_ANALOG",
    "CATEGORY_ELECTRODE",
    "CATEGORY_TEMPERATURE",
    "CATEGORY_RELAY",
    "CATEGORY_DIGITAL_INPUT",
    "CATEGORY_EXTERNAL_RELAY",
    "CATEGORY_CANISTER",
    "CATEGORY_CONSUMPTION",
    # OO wrappers
    "GetState",
    "RelaySwitch",
    "DosageControl",
    "DmxControl",
    # free async functions
    "async_get_raw_data",
    "async_get_raw_state",
    "async_get_state",
    "async_post_usrcfg_cgi",
    "async_switch_on",
    "async_switch_off",
    "async_set_auto_mode",
    "async_start_dosage",
    "async_get_raw_dmx",
    "async_get_dmx",
    "async_set_dmx",
]
