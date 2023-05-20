# Python package for the ProCon.IP Pool Controller

[![Pylint](https://github.com/ylabonte/proconip-pypi/actions/workflows/pylint.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/pylint.yml)
[![Unittest](https://github.com/ylabonte/proconip-pypi/actions/workflows/unittest.yml/badge.svg)](https://github.com/ylabonte/proconip-pypi/actions/workflows/unittest.yml)

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >](https://www.buymeacoffee.com/ylabonte)

## Overview

* [Introduction (_What is this library for?_)](#introduction)
* [Installation](#installation)
* [Usage](#usage)
* [A brief description of the ProCon.IP pool controller](#a-brief-description-of-the-proconip-pool-controller)
* [Disclaimer](#disclaimer)


---

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

## Usage

```python
import asyncio
import aiohttp
from proconip.definitions import ConfigObject
from proconip.api import GetState, RelaySwitch


async def testrun():
    client_session = aiohttp.ClientSession()
    config = ConfigObject("http://192.168.2.3", "admin", "admin")
    get_state = GetState(client_session, config)
    data = await get_state.structured()
    print(f"Redox (Chlor): {data.redox_electrode.display_value}")
    print(f"pH: {data.ph_electrode.display_value}")
    for relay in (relay for relay in data.relays() if relay.name != "n.a."):
        print(f"{relay.name}: {relay.display_value}")
    for temp in (temp for temp in data.temperature_objects if temp.name != "n.a."):
        print(f"{temp.name}: {temp.display_value}")
    
    relay_switch = RelaySwitch(client_session, config)
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    await relay_switch.set_auto_mode(data, 1)
    data = await get_state.structured()
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    await relay_switch.set_on(data, 2)
    data = await get_state.structured()
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    await relay_switch.set_off(data, 1)
    data = await get_state.structured()
    print(f"Relay no. 2: {data.get_relay(1).display_value}")
    await relay_switch.set_off(data, 2)
    data = await get_state.structured()
    print(f"Relay no. 3: {data.get_relay(2).display_value}")
    
    await client_session.close()


asyncio.run(testrun())

```

## A brief description of the ProCon.IP pool controller

![Picture from pooldigital.de](https://www.pooldigital.de/shop/media/image/66/47/a5/ProConIP1_720x600.png)

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

* [pooldigital.de webshop](https://www.pooldigital.de/shop/poolsteuerungen/procon.ip/35/procon.ip-webbasierte-poolsteuerung-/-dosieranlage)
* [pooldigital.de forum](http://forum.pooldigital.de/)

## Disclaimer

**Just to be clear: I have nothing to do with the development, sellings,
marketing or support of the pool controller unit itself. I just developed a
solution to integrate such with [ioBroker](https://github.com/ylabonte/ioBroker.procon-ip)
and now decoupled the library part to make it cleaner.**