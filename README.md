# Python package for the ProCon.IP Pool Controller

[![Pylint](https://github.com/ylabonte/proconip-pypi/actions/workflows/pylint.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/pylint.yml)
[![Unittest](https://github.com/ylabonte/proconip-pypi/actions/workflows/unittest.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/unittest.yml)
[![CodeQL](https://github.com/ylabonte/proconip-pypi/actions/workflows/codeql.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/codeql.yml)
[![PyPi Package release](https://github.com/ylabonte/proconip-pypi/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/python-publish.yml)

[![PyPI](https://img.shields.io/pypi/v/proconip?label=Current%20Release)](https://pypi.org/project/proconip/)

## Overview

* [Introduction (_What is this library for?_)](#introduction)
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
It is somehow a port of my [procon-ip](https://github.com/ylabonte/procon-ip) 
TypeScript library (available as [NPM Package](https://www.npmjs.com/package/procon-ip)). 
As the TypeScript library was a byproduct of my ioBroker adapter for the pool 
controller unit, this library is primary intended for the implementation of a 
Home Assistant integration.

Documentation might follow. Until this please take a look at the sources. I
tried to keep it simple and readable. An IDE with proper auto-completion should
help understand and use the library without further documentation.

Feel free to ask questions by using github's issues system, so others can take
advantage, contribute and are able to find the answer if they have a similar 
question. Thanks! :)

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
from proconip.definitions import ConfigObject
from proconip.api import GetState


async def reading_data_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    get_state_api = GetState(client_session, config)
    data = await get_state_api.async_get_state()
    await client_session.close()
    print(f"Redox (Chlor): {data.redox_electrode.display_value}")
    print(f"pH: {data.ph_electrode.display_value}")
    for relay in (relay for relay in data.relays() if relay.name != "n.a."):
        print(f"{relay.name}: {relay.display_value}")
    for temp in (temp for temp in data.temperature_objects if temp.name != "n.a."):
        print(f"{temp.name}: {temp.display_value}")


asyncio.run(reading_data_example())
```

### Switching relays

```python
import asyncio
import aiohttp
from proconip.definitions import ConfigObject
from proconip.api import GetState, RelaySwitch


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
from proconip.definitions import ConfigObject
from proconip.api import DosageControl


async def manual_dosage_example():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    dosage_control = DosageControl(client_session, config)
    await dosage_control.async_chlorine_dosage(3600) # start for 1 hour
    await dosage_control.async_ph_minus_dosage(60) # start for 1 minute
    await client_session.close()


asyncio.run(manual_dosage_example())
```

### Reading and changing DMX channels states

```python
import asyncio
import aiohttp
from proconip.definitions import ConfigObject
from proconip.api import DmxControl


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

### v1.4.1 (2024-08-18)
* Update dependencies

### v1.4.0 (2024-06-24)
* Introduce new API class `DmxControl` with three methods:
  * `async_get_raw_dmx()` to get the raw body string of the '/GetDmx.csv'.
  * `async_get_dmx()` to get structured DMX channel states.
  * `async_set()` to set DMX channel states.

### v1.3.1 (2024-05-09)
* Add dedicated `api.TimeoutException` to raise for connection timeouts.
* Add dependabot with `versioning-strategy: "increase"` and an auto-merge workflow for automated updates on the github 
  `main` branch.
* Add code scanning (CodeQL) workflow.

### v1.3.0 (2023-08-16)
* Add `GetStateData.get_relays()` to get all available Relay instances.

### v1.2.7 (2023-07-04)
* Fix calculation formula for actual values (`offset + gain * raw`).

### v1.2.6 (2023-06-20)
* Fix DosageTarget enum and return value of `DosageControl.async_ph_plus_dosage`.

### v1.2.5 (2023-06-18)
* Fix return type/value of `DosageControl.async_ph_plus_dosage()`

### v1.2.4 (2023-06-18)
* Refactor request exception handling

### v1.2.3 (2023-06-17)
* Fix api methods to produce `BadCredentialsExceptions` in case of 401 and 403 responses.

### v1.2.2 (2023-06-12)
* Fix typo in `BadStatusCodeException`

### v1.2.1 (2023-06-12)
* Avoid invalid operations regarding dosage control relays.

### v1.2.0 (2023-06-12)
* Add DosageControl abilities.

### v1.1.0 (2023-05-23)
*  Unify api methods and naming conventions:
  * Same names for functions and class methods with same functionality.
  * `async_` prefixes for all async functions/methods.

### v1.0.0 (2023-05-21)
* Fix post data for switching relays.

### v0.0.2 (2023-05-18)
* Add relay switching capabilities.

### v0.0.1 (2023-04-23)
* Initial release with data reading capabilities.

## Disclaimer

**Just to be clear: I have nothing to do with the development, selling, marketing or support of the pool controller
unit itself.  
I just developed small TypeScript/JS and Python libraries as by-products of an ioBroker adapter and a Home Assistant
integration for integrating the pool controller unit with common smart home solutions.**