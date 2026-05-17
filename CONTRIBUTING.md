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
3. Write commit messages in [Conventional Commits](https://www.conventionalcommits.org/) format — they drive the release notes (see below).
4. Ensure `pytest`, `ruff check .`, and `mypy src` all pass locally.
5. Open a pull request against `main`. Use the PR template.

## Commit messages drive releases

Releases are fully automated by [release-please](https://github.com/googleapis/release-please) — maintainers don't tag or publish by hand. Commit messages on `main` determine the next version and what appears in the changelog.

### Format

```
<type>(<optional scope>): <subject>

[optional body]

[optional footer(s)]
```

### Types and their effect

| Type | Triggers version bump | Appears in CHANGELOG |
|---|---|---|
| `feat` | **minor** | Features |
| `fix` | **patch** | Bug Fixes |
| `perf` | **patch** | Performance |
| `revert` | **patch** | Reverts |
| `deps` | none | Dependencies |
| `docs` | none | Documentation |
| `refactor` / `test` / `build` / `ci` / `chore` | none | hidden |

### Breaking changes

Use `!` after the type/scope or add a `BREAKING CHANGE:` footer — either triggers a **major** bump.

```
feat(api)!: drop deprecated async_get_dmx_raw alias

BREAKING CHANGE: callers must migrate to async_get_raw_dmx (introduced in v1.4).
```

### Examples (from this repo's history)

```
feat(mock): env-var entry points for config_other_enable
fix(devcontainer): start-mock.sh probes the configured host
docs(mock): sync README and drift docstring with latest changes
chore(deps): tidy dependabot groups and commit prefixes
```

## Release flow (for maintainers)

1. PRs merge to `main` as usual.
2. `release.yml` runs `release-please-action@v4`, which analyzes commits since the last tag.
3. If any commits trigger a version bump, it opens (or updates) a **"chore: release X.Y.Z"** PR that updates `CHANGELOG.md` and `.release-please-manifest.json`.
4. Review that PR like any other; merging it triggers release-please to:
   - Create the exact-version git tag (e.g. `v2.2.0`)
   - Create the GitHub Release with the CHANGELOG section as notes
5. `python-publish.yml` fires on `release: published` → Trusted Publishing to PyPI.

## Ideas and questions

Use [GitHub Issues](https://github.com/ylabonte/proconip-pypi/issues) for
feature requests, bug reports, and questions so the community can benefit.

## Contact

Yannic Labonte <yannic.labonte@gmail.com>
