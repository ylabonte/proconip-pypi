# proconip

Async Python library for the [ProCon.IP](https://pooldigital.de/poolsteuerungen/procon.ip/35/procon.ip-webbasierte-poolsteuerung-/-dosieranlage)
pool controller. Primarily intended as the foundation for a Home Assistant
integration, but useful on its own for any Python application that needs to
talk to the controller.

## Install

```bash
pip install proconip
```

Requires Python 3.13+. The runtime dependencies (`aiohttp`, `yarl`) are
declared with version ranges that match the Home Assistant Core 2026.5 pins,
so installing `proconip` alongside Home Assistant Core should not produce
resolver conflicts.

## Quickstart

```python
import asyncio
import aiohttp
from proconip import ConfigObject, GetState

async def main() -> None:
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    async with aiohttp.ClientSession() as session:
        api = GetState(session, config)
        state = await api.async_get_state()

    print(f"Redox: {state.redox_electrode.display_value}")
    print(f"pH:    {state.ph_electrode.display_value}")
    for relay in (r for r in state.relays() if r.name != "n.a."):
        print(f"{relay.name}: {relay.display_value}")

asyncio.run(main())
```

See [API Reference](api.md) for the full surface, including relay switching,
manual dosage, and DMX channel control.

## Project layout

- **API Reference** — auto-generated from the source via mkdocstrings.
- **Changelog** — what changed in each release.
- **Contributing** — how to set up a local dev environment.

The source lives at <https://github.com/ylabonte/proconip-pypi>; PyPI page at
<https://pypi.org/project/proconip/>.
