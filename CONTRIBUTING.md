# Contributing to TecDocAuto

Thank you for your interest in contributing.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Running tests

```bash
pytest
```

## Code style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

## Pull requests

- Keep changes focused and small.
- Add tests for new functionality.
- Update documentation when behavior changes.
- Use conventional commit messages (`feat:`, `fix:`, `docs:`, `chore:`, ...).
