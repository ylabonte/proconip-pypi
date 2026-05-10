# Python package for the ProCon.IP Pool Controller

[![Lint](https://github.com/ylabonte/proconip-pypi/actions/workflows/lint.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/lint.yml)
[![Test](https://github.com/ylabonte/proconip-pypi/actions/workflows/test.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/test.yml)
[![CodeQL](https://github.com/ylabonte/proconip-pypi/actions/workflows/codeql.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/codeql.yml)
[![PyPI Package release](https://github.com/ylabonte/proconip-pypi/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/python-publish.yml)

[![PyPI](https://img.shields.io/pypi/v/proconip?label=Current%20Release)](https://pypi.org/project/proconip/)
[![Python Versions](https://img.shields.io/pypi/pyversions/proconip)](https://pypi.org/project/proconip/)

## Overview

* [Introduction (_What is this library for?_)](#introduction)
* [Requirements](#requirements)
* [Installation](#installation)
* [Usage](#usage-examples)
  * [Reading the current state](#reading-the-current-state)
  * [Switching relays](#switching-relays)
* [A brief description of the ProCon.IP pool controller](#a-brief-description-of-the-proconip-pool-controller)
* [Get support](#get-support)
* [Give support](#give-support)
* [Release Notes](#release-notes)
* [Disclaimer](#disclaimer)

---
![ProCon.IP Python Library](https://raw.githubusercontent.com/ylabonte/proconip-pypi/main/logo.png)

## Introduction

The name of this library refers to the [ProCon.IP pool controller](#a-brief-description-of-the-proconip-pool-controller).
It is a port of my [procon-ip](https://github.com/ylabonte/procon-ip)
TypeScript library (available as [NPM Package](https://www.npmjs.com/package/procon-ip)).
As the TypeScript library was a byproduct of my ioBroker adapter for the pool
controller unit, this library is primarily intended for the implementation of a
Home Assistant integration.

The library is fully typed (PEP 561). An IDE with auto-completion should make
it straightforward to use without additional documentation.

Feel free to ask questions via [GitHub Issues](https://github.com/ylabonte/proconip-pypi/issues)
so others can benefit from the answers too. Thanks!

## Requirements

- **Python ≥ 3.13**
- `aiohttp >= 3.10, < 4`
- `yarl >= 1.9, < 2`

These dependency ranges are compatible with
[Home Assistant Core 2026.5](https://www.home-assistant.io/) pins
(`aiohttp==3.13.5`, `yarl==1.23.0`).

> **v2.0.0 breaking changes** — see [CHANGELOG.md](CHANGELOG.md) for details:
> - Python ≥ 3.13 required (was ≥ 3.10)
> - `async-timeout` dependency removed (use `asyncio.timeout` from stdlib)
> - `Relay` value semantics fixed (offset+gain applied exactly once)
> - `TimeoutException` is now actually raised for timeouts

## Installation

This library is available on [PyPI](https://pypi.org/project/proconip/). So you 
can easily install it with pip:
```bash
pip install proconip
```
or
```bash
python -m pip install proconip
```
In both cases you can add `--upgrade` to update to the latest version.

## Usage examples

### Reading the current state

```python
import asyncio
import aiohttp
from proconip import ConfigObject, GetState


async def reading_data_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    get_state_api = GetState(client_session, config)
    data = await get_state_api.async_get_state()
    await client_session.close()
    print(f"Redox (Chlor): {data.redox_electrode.display_value}")
    print(f"pH: {data.ph_electrode.display_value}")
    for relay in (r for r in data.relays() if r.name != "n.a."):
        print(f"{relay.name}: {relay.display_value}")
    for temp in (t for t in data.temperature_objects if t.name != "n.a."):
        print(f"{temp.name}: {temp.display_value}")


asyncio.run(reading_data_example())
```

### Switching relays

```python
import asyncio
import aiohttp
from proconip import ConfigObject, GetState, RelaySwitch


async def relay_switching_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    get_state_api = GetState(client_session, config)
    relay_switch = RelaySwitch(client_session, config)
    data = await get_state_api.async_get_state()
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    await relay_switch.async_set_auto_mode(data, 1)
    data = await get_state_api.async_get_state()
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    await relay_switch.async_switch_on(data, 2)
    data = await get_state_api.async_get_state()
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    await relay_switch.async_switch_off(data, 1)
    data = await get_state_api.async_get_state()
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    await relay_switch.async_switch_off(data, 2)
    data = await get_state_api.async_get_state()
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    await client_session.close()


asyncio.run(relay_switching_example())
```

### Starting manual dosage

Manual dosage depends on the same factors as if started from the web interface
of the pool control itself.

```python
import asyncio
import aiohttp
from proconip import ConfigObject, DosageControl


async def manual_dosage_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    dosage_control = DosageControl(client_session, config)
    await dosage_control.async_chlorine_dosage(3600) # start for 1 hour
    await dosage_control.async_ph_minus_dosage(60) # start for 1 minute
    await client_session.close()


asyncio.run(manual_dosage_example())
```

### Reading and changing DMX channel states

```python
import asyncio
import aiohttp
from proconip import ConfigObject, DmxControl


async def dmx_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    dmx_control = DmxControl(client_session, config)
    dmx_data = await dmx_control.async_get_dmx()
    for channel in dmx_data:
        print(f"{channel.name} before: {channel.value}")
        dmx_data.set(channel.index, (channel.value + 128) % 256)
        print(f"{channel.name} after: {dmx_data.get_value(channel.index)}")
      
    await dmx_control.async_set(dmx_data)
    await client_session.close()


asyncio.run(dmx_example())

```

## A brief description of the ProCon.IP pool controller

The ProCon.IP pool controller is a low budget network attached control unit for
home swimming pools. With its software switched relays, it can control
multiple pumps (for the pool filter and different dosage aspects) either
simply planned per time schedule or depending on a reading/value from one of
its many input channels for measurements (eg. i/o flow sensors, Dallas 1-Wire
thermometers, redox and pH electrodes). At least there is also the option to
switch these relays on demand, which makes them also applicable for switching
lights (or anything else you want) on/off.
Not all of its functionality is reachable via API. In fact there is one
documented API for reading (polling) values as CSV (`/GetState.csv`). In my
memories there was another one for switching the relays on/off and on with
timer. But I cannot find the second one anymore. So not even pretty, but
functional: The ProCon.IP has two native web interfaces, which can be
analyzed, to some kind of reverse engineer a given functionality (like
switching the relays).

For more information see the following links (sorry it's only in german;
haven't found an english documentation/information so far):

* [pooldigital.de webshop](https://pooldigital.de/poolsteuerungen/procon.ip/35/procon.ip-webbasierte-poolsteuerung-/-dosieranlage)
* [pooldigital.de forum](https://www.poolsteuerung.de/)

## Get support

Need help? Please use the [github issues system](https://github.com/ylabonte/proconip-pypi/issues)
to ask your question. This way others can contribute or at least take advantage of the final solution.

## Give support

If you want to support this project or my work in general, you can do so without having any coding abilities.
Because programmers are described as machines that convert coffee (their habitual input) into code (their habitual
output), there is a really simple way to support me:

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >](https://www.buymeacoffee.com/ylabonte)

## Release Notes

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## Disclaimer

**Just to be clear: I have nothing to do with the development, selling, marketing or support of the pool controller
unit itself.  
I just developed small TypeScript/JS and Python libraries as by-products of an ioBroker adapter and a Home Assistant
integration for integrating the pool controller unit with common smart home solutions.**