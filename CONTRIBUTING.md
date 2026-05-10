# Contributing

## Development setup

```bash
git clone https://github.com/ylabonte/proconip-pypi.git
cd proconip-pypi

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev,test]"
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
4. Open a pull request against `main`. Use the PR template.

## Ideas and questions

Use [GitHub Issues](https://github.com/ylabonte/proconip-pypi/issues) for
feature requests, bug reports, and questions so the community can benefit.

## Contact

Yannic Labonte <yannic.labonte@gmail.com>
