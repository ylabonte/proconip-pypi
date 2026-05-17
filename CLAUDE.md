# CLAUDE.md

Project memory for AI agents (and humans) working on `proconip-pypi`.

## What this library is

`proconip` is an async Python client library for the **ProCon.IP pool controller**.
Its primary consumer is a Home Assistant integration. The public surface is
intentionally small: HTTP wrappers around four controller endpoints
(`/GetState.csv`, `/GetDmx.csv`, `/usrcfg.cgi`, `/Command.htm`) plus typed data
classes that parse the controller's CSV responses.

## Tech stack

- **Python ≥ 3.13** — matches Home Assistant Core 2026.5.
- **Build backend**: `hatchling` + `hatch-vcs` (version derived from git tags;
  do not hardcode a version string anywhere in source).
- **Runtime deps**: `aiohttp>=3.10,<4` and `yarl>=1.9,<2`. These ranges must
  remain compatible with HA Core 2026.5 pins (`aiohttp==3.13.5`,
  `yarl==1.23.0`). Don't tighten them to `==` and don't drop the upper bounds
  without a major version bump.
- **Tests**: pytest, pytest-asyncio (auto mode), pytest-cov, aioresponses.
- **Lint + format**: `ruff` (lint and format). `black` is **not** used.
- **Types**: `mypy` (strict on `src/`). The package is PEP 561 typed
  (`src/proconip/py.typed`).
- **Docs**: MkDocs Material + mkdocstrings, deployed to GitHub Pages on every
  push to `main` and on each release.

## Public API surface

All public symbols are re-exported from `proconip.__init__` and listed in
`__all__`. **Always use top-level imports in examples, docs, and the README**:

```python
from proconip import ConfigObject, GetState, async_get_state
```

Avoid deep imports (`from proconip.api import …`, `from proconip.definitions
import …`) in user-facing material. Internal modules may still import
internally however they like.

## Two API layers

Every operation is exposed twice:

1. **Free async functions** — take `client_session` and `config` explicitly.
   Examples: `async_get_state`, `async_switch_on`, `async_set_dmx`.
2. **OO wrappers** — bind session and config in `__init__`, expose ergonomic
   methods that don't repeat those arguments. Examples: `GetState`,
   `RelaySwitch`, `DosageControl`, `DmxControl`.

The OO wrappers internally call the free functions. **Don't duplicate logic** —
if behavior changes, change the free function and the wrapper picks it up.

## Docstring style

- **Google style**, with `Args:` / `Returns:` / `Raises:` blocks when those
  details aren't obvious from the signature alone.
- **Self-contained and informative**. A docstring should make sense on its
  own — describe what the function does in its own right. Avoid cross-reference
  stubs like "Equivalent to the free function X" or "Same as Y but with bound
  session". If a related function adds context, mention it in the body, but
  still describe the behavior here.
- **One-line summary** for trivial getters/properties; expand when WHY, HOW,
  UNITS, or RAISES are non-obvious.
- **Document units**: e.g. `dosage_duration` is in **seconds**.
- **Document raised exceptions** for any function that talks to the controller:
  `BadCredentialsException`, `BadStatusCodeException`, `TimeoutException`,
  `ProconipApiException`, plus domain-specific ones (`BadRelayException`,
  `InvalidPayloadException`).
- **No "this is used by X" notes** — those go stale.

## Source-of-truth conventions

- **Version**: hatch-vcs reads git tags. There is no `version` string in
  `pyproject.toml` (`dynamic = ["version"]`).
- **Runtime deps**: declared in `[project.dependencies]` in `pyproject.toml`.
  There is no `setup.py` — don't recreate one.
- **Dev/test/docs deps**: declared in `[dependency-groups]` (PEP 735)
  (`dev`, `test`, `docs`). Installed with `pip install --group <name>`
  (requires pip ≥ 25.1). There are no `requirements*.txt` files and no
  `[project.optional-dependencies]` — these aren't user-facing extras.
- **Changelog**: `CHANGELOG.md`. From v2.2.0 onward, entries are managed by
  [changesets](https://github.com/changesets/changesets) — every PR that needs
  release notes must include a `.changeset/<name>.md` file (run
  `pnpm changeset` to create one interactively). Earlier entries (v2.1.0 and
  below) follow Keep-a-Changelog and stay as-is. README links here;
  don't duplicate entries in the README.
- **Test data**: `tests/fixtures/*.csv` loaded via `tests/conftest.py`
  fixtures. Don't inline test CSVs into test functions.

## Local development

```bash
pip install -e . --group dev --group test --group docs
pre-commit install

# Verification commands (each must pass before committing)
pytest                              # tests + coverage (≥80%)
ruff check .                        # lint
ruff format --check .               # format
mypy src                            # types
mkdocs serve                        # docs preview at http://127.0.0.1:8000
mkdocs build --strict               # full doc build (CI parity)
```

## CI workflows

| File | Purpose |
|---|---|
| `lint.yml` | `ruff check`, `ruff format --check`, `mypy src` |
| `test.yml` | `pytest` with coverage; uploads `coverage.xml` artifact |
| `codeql.yml` | Security scan with `security-extended,security-and-quality` |
| `docs.yml` | MkDocs build + deploy to GitHub Pages |
| `release.yml` | Changesets-driven release: opens "Version Packages" PR; on merge, tags + creates GitHub Release. App-authenticated so it can trigger downstream workflows. |
| `python-publish.yml` | Trusted Publishing (OIDC) on `release: published`; `needs: [test, lint]` |
| `update-actions.yml` | Weekly + on-demand `ylabonte/github-actions-updater@v1` run; opens `chore/update-github-actions` PR when actions are outdated |
| `enable-auto-merge.yml` | Auto-merges PRs from `dependabot[bot]` / `github-actions[bot]` (rebase). Human PRs and the changesets "Version Packages" PR are excluded. |

## Common pitfalls (don't repeat these)

- **Don't add `async-timeout` back.** Use stdlib `asyncio.timeout(timeout)`
  (Python 3.11+).
- **Don't catch bare `except Exception`** in HTTP code — it accidentally
  re-wraps our own typed exceptions. Use `(ClientError, socket.gaierror)` and
  let typed domain exceptions propagate.
- **Don't use `match`/`case` for small dispatch tables.** CodeQL flags the
  implicit-fall-through pattern (false positive). Prefer `if … elif … return`.
- **`Relay(data_object)` must pass `data_object.raw_value`** to the parent
  `__init__`, not `data_object.value`. Otherwise `offset + gain` is applied
  twice. Regression test: `tests/test_definitions.py::test_relay_value_not_double_applied`.
- **Don't pin a single Python version in CI** unless you also update
  `requires-python` in `pyproject.toml`. They must agree.
- **Plain HTTP is normal** — controllers are LAN-only. Don't add HTTPS-required
  validation that breaks real deployments.

## Release flow

Changesets-driven. No manual tagging or release creation.

1. While working on a feature/fix branch, run `pnpm changeset` and pick the
   bump type (patch/minor/major). It writes a `.changeset/<name>.md` file —
   commit it alongside your code. PRs without a changeset are fine for
   docs/CI-only changes that don't warrant release notes.
2. PR into `main`. CI (`lint`, `test`, `codeql`, `docs`) must be green; merge.
3. On merge to `main`, `release.yml` runs `changesets/action@v1`:
   - If any pending `.changeset/*.md` files exist, it opens (or updates) a
     **"Version Packages" PR** that bumps `package.json` and prepends the new
     CHANGELOG section.
   - If that "Version Packages" PR is the one being merged, it instead:
     creates the exact-version git tag (e.g. `v2.2.0`), runs `pnpm release`
     (= `changeset publish` — no-op npm push since the package is private),
     and creates the GitHub Release with the CHANGELOG section as notes.
4. The Release-published event triggers `python-publish.yml`: tests + lint
   pass → Trusted Publishing (OIDC) pushes to PyPI with attestations. No
   long-lived API token in use.

**Auth note**: `release.yml` authenticates as a GitHub App
(`RELEASE_APP_CLIENT_ID` + `RELEASE_APP_PRIVATE_KEY` repo secrets) rather
than using the default `GITHUB_TOKEN`. This is required so that the tag /
Release it creates can trigger the downstream `python-publish.yml` workflow
(workflows-triggering-workflows is disabled for the default token by
design). If `python-publish.yml` ever stops firing automatically, check that
the App is still installed and the secrets are present.
