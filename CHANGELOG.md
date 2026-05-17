# Changelog

## [2.1.0] — 2026-05-14

### Changed

- **License changed from AGPL-3.0-or-later to MIT.** The `LICENSE` file now contains the MIT License. `pyproject.toml` SPDX expression and Trove classifier updated to match. No source-code changes; runtime behavior is unchanged. Downstream consumers should review the new license terms before upgrading.
- **Development dependencies moved from `[project.optional-dependencies]` to `[dependency-groups]`** (PEP 735). The `dev`, `test`, and `docs` groups were never user-facing extras; they're for working *on* the package, not *with* it. They no longer appear as `Provides-Extra:` on PyPI. Local install: `pip install -e . --group dev --group test --group docs` (requires pip ≥ 25.1). CI workflows (`test.yml`, `lint.yml`, `docs.yml`) and `CONTRIBUTING.md` updated accordingly.

## [2.0.0] — 2026-05-10

### BREAKING CHANGES

- **Python ≥ 3.13 required.** The minimum supported Python version has been raised from 3.10 to 3.13 to align with Home Assistant Core 2026.5 and to drop the `async-timeout` dependency (now part of the stdlib as `asyncio.timeout`).
- **`Relay` value semantics fixed.** `Relay.__init__` previously passed the already-computed `value` (offset + gain × raw) as the raw value to the parent `DataObject.__init__`, causing the transform to be applied twice. For controllers with non-trivial offset/gain values this produced incorrect relay state reads. Fixed to pass `raw_value` so the transform is applied exactly once. Controllers with `offset=0, gain=1` (the typical case) are unaffected.
- **`async-timeout` dependency removed.** Replace any direct use of `async_timeout` with `asyncio.timeout` (Python 3.11+ stdlib).
- **`TimeoutException` is now actually raised** (it was defined but never used in v1.x; `ProconipApiException` was raised instead). Code that catches `ProconipApiException` for timeouts will still work, but narrowing to `TimeoutException` is now possible and recommended.
- **`src/setup.py` removed.** The package is now built exclusively with hatchling and hatch-vcs.

### Added

- Top-level `from proconip import ...` imports: all public classes, functions, and exceptions are now re-exported from `proconip.__init__`.
- `proconip.__version__` attribute (derived from git tags via hatch-vcs).
- `py.typed` marker (PEP 561) — the package is now typed.
- `EXTERNAL_RELAY_ID_OFFSET` constant (replaces magic number `8`).
- `GetDmxData.__iter__` — `for channel in dmx_data:` now works via an explicit iterator.
- `InvalidPayloadException` class — raised by `GetStateData` and `GetDmxData` when the controller's payload is empty or truncated.
- `configurable timeout` parameter (`timeout: float = 10.0`) on all public async functions; the timeout now wraps both the request and response body read.
- OO wrappers (`GetState`, `RelaySwitch`, `DosageControl`, `DmxControl`) now accept a `timeout` argument in `__init__` and on every async method (defaults to `10.0` seconds; the method-level argument, when supplied, overrides the value bound in the constructor).
- `CHANGELOG.md` (this file) — release notes extracted from README.
- **Documentation site** at <https://ylabonte.github.io/proconip-pypi/> built with MkDocs Material + mkdocstrings; rebuilds on every `main` push and release. Source docstrings audited and expanded throughout the public surface.
- `CLAUDE.md` — project memory for AI agents (and humans) capturing tech stack, conventions, and pitfalls.

### Fixed

- `Relay.__init__` double-applies offset+gain (see Breaking Changes above).
- `GetStateData.__init__` and `GetDmxData.__init__`: bounds check before index access in the leading-blank-line skip loop (`while line < len(lines) and ...` instead of `while len(lines[line]...) and line < len(lines)`).
- `GetStateData._parse`: `_digital_objects` renamed to `_digital_input_objects` — aligns with the class annotation and the `digital_input_objects` property.
- `GetStateData.get_dosage_relay` return type changed from `int` (with `False` fallback) to `int | None`.
- `GetStateData.get_ntp_fault_state_as_str`: rewritten to handle composite bit-flag values correctly (e.g. value `3` = bits 1+2, returns highest-severity bit's description).
- `is_dosage_relay`: `BadRelayException` now includes a descriptive message when `data_object.category` is not a relay category.
- `async_switch_off` docstring said "Switch on" — corrected to "Switch off".
- `Relay.is_auto_mode` docstring said "manual mode" — corrected to "auto mode".
- `determine_overall_relay_bit_state` docstring typo ("relay a bit state" → "relay bit state").
- `async_get_raw_dmx` and `DmxControl.async_get_raw_dmx` docstrings referenced `GetState.csv` — corrected to `GetDmx.csv`.
- `DmxControl` class docstring said "GetDmx class" — corrected to "DmxControl class".
- `GetDmxData.set` error message off-by-one ("channel 0" → "channel 1", "channel 16" matches index 15).
- `GetDmxData.__init__`: replaced `self._channels.insert(idx, ...)` loop with `append`.
- `DmxChannelData.__init__`: modernized format string to f-string.
- `DataObject._relay_state`: error message includes the actual value.
- Stray `"""Actual channel value."""` string literal inside `DmxChannelData` class body removed.
- Dead `_data_values` dict computation removed from `GetStateData.__init__` (was computed but never read, and used the wrong formula).

### Changed

- Build system: `hatchling` + `hatch-vcs` (git-tag-based versioning). Version no longer hard-coded in source.
- Dependencies declared in `[project.dependencies]` in `pyproject.toml` (were missing — wheel shipped with no deps).
- Runtime dependencies: `aiohttp>=3.10,<4` and `yarl>=1.9,<2` (ranges compatible with HA Core 2026.5 pins of `aiohttp==3.13.5` and `yarl==1.23.0`).
- Exception classes moved to the top of `api.py` (were at the bottom, referenced before definition).
- Exception handling in `async_get_raw_data` / `async_post_usrcfg_cgi`: extracted `_handle_response` helper; `BadCredentialsException` now propagates correctly instead of being accidentally re-wrapped as `BadStatusCodeException`.
- `@dataclasses.dataclass` decorator removed from all classes (had no effect since each class defines `__init__`).
- Linting: `black` replaced by `ruff` (lint + format); `mypy` added for type checking.
- CI: `unittest.yml` → `test.yml` (pytest); `pylint.yml` → `lint.yml` (ruff + mypy).
- CI: Added pip caching, `concurrency` (cancel-in-progress), explicit `permissions: contents: read`.
- Publishing: Switched from `PYPI_API_TOKEN` secret to PyPI Trusted Publishing (OIDC); added `attestations: true`.
- `dependabot.yml`: weekly cadence, grouped updates, commit-message prefixes, PR limit.

### Removed

- `async-timeout` dependency.
- `src/setup.py` (legacy build script).
- `src/__init__.py` (was an empty, accidentally-created file).
- `requirements.txt`, `src/requirements.txt`, `tests/requirements.txt` (replaced by `[project.optional-dependencies]` in `pyproject.toml`).
- `pylint: disable=...` comments (pylint is no longer used; ruff rules are configured in `pyproject.toml`).

---

## [1.4.7] — 2024-09-07

- Code refactoring.
- Unification of exception handling.
- Updated setuptools.

## [1.4.6] — 2024-08-24

- Fix incomplete `Content-Type` header.

## [1.4.5] — 2024-08-24

- Add appropriate `Content-Type` header for POST requests.
- Fix some typing hints.

## [1.4.4] — 2024-08-20

- Yet another fix for the DMX POST data payload conversion.

## [1.4.3] — 2024-08-20

- Fix `async_get_raw_dmx()` and `async_get_dmx()`.
- Fix `GetDmxData.post_data` property.
- Update dependencies.

## [1.4.1] — 2024-08-18

- Update dependencies.

## [1.4.0] — 2024-06-24

- Introduce `DmxControl` API class with `async_get_raw_dmx()`, `async_get_dmx()`, and `async_set()`.

## [1.3.1] — 2024-05-09

- Add `api.TimeoutException` (note: not wired up until v2.0.0).
- Add Dependabot and auto-merge workflow.
- Add CodeQL scanning workflow.

## [1.3.0] — 2023-08-16

- Add `GetStateData.get_relays()`.

## [1.2.7] — 2023-07-04

- Fix calculation formula for actual values (`offset + gain * raw`).

## [1.2.6] — 2023-06-20

- Fix `DosageTarget` enum and return value of `DosageControl.async_ph_plus_dosage`.

## [1.2.5] — 2023-06-18

- Fix return type/value of `DosageControl.async_ph_plus_dosage()`.

## [1.2.4] — 2023-06-18

- Refactor request exception handling.

## [1.2.3] — 2023-06-17

- Fix API methods to produce `BadCredentialsException` for 401/403 responses.

## [1.2.2] — 2023-06-12

- Fix typo in `BadStatusCodeException`.

## [1.2.1] — 2023-06-12

- Avoid invalid operations on dosage control relays.

## [1.2.0] — 2023-06-12

- Add dosage control capabilities.

## [1.1.0] — 2023-05-23

- Unify API methods and naming conventions; add `async_` prefixes.

## [1.0.0] — 2023-05-21

- Fix POST data for relay switching.

## [0.0.2] — 2023-05-18

- Add relay switching capabilities.

## [0.0.1] — 2023-04-23

- Initial release with data reading capabilities.

