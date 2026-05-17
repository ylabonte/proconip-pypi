# Contributing

## Development setup

```bash
git clone https://github.com/ylabonte/proconip-pypi.git
cd proconip-pypi

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e . --group dev --group test
pre-commit install
```

## Running tests

```bash
pytest                             # run tests with coverage report
pytest -x                          # stop on first failure
pytest tests/test_api.py -v        # run a single file
```

## Code quality

```bash
ruff check .                       # lint
ruff format .                      # auto-format
mypy src                           # type check
```

Pre-commit hooks run these automatically on `git commit`.

## Submitting changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with tests.
3. Ensure `pytest`, `ruff check .`, and `mypy src` all pass locally.
4. If your change should appear in the release notes, add a changeset:
   ```bash
   pnpm install        # one-time, installs @changesets/cli
   pnpm changeset      # interactive: pick patch / minor / major + write a summary
   ```
   Commit the generated `.changeset/<random-name>.md` alongside your code.
   Skip this step for docs-only, CI-only, or other non-user-visible changes.
5. Open a pull request against `main`. Use the PR template.

## Release process

Releases are fully automated via [changesets](https://github.com/changesets/changesets) — maintainers don't tag or publish by hand.

When a PR with one or more `.changeset/*.md` files merges to `main`, `release.yml` opens (or updates) a **"Version Packages" PR** that bumps the version in `package.json` and prepends a new entry to `CHANGELOG.md`. Review that PR like any other; merging it triggers:

1. Creation of the exact-version git tag (e.g. `v2.2.0`)
2. Creation of the GitHub Release with the CHANGELOG section as notes
3. `python-publish.yml` fires on `release: published` → Trusted Publishing to PyPI

### Changeset bump types

- **patch** — bug fixes, internal refactors with no API impact, doc fixes that ship in the package
- **minor** — new features, new public API surface, backwards-compatible additions
- **major** — breaking changes (removed/renamed public API, behavior changes that require consumer updates)

When in doubt, lean toward the more conservative (lower) bump — major bumps are expensive for downstream Home Assistant users.

## Ideas and questions

Use [GitHub Issues](https://github.com/ylabonte/proconip-pypi/issues) for
feature requests, bug reports, and questions so the community can benefit.

## Contact

Yannic Labonte <yannic.labonte@gmail.com>
