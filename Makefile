.PHONY: install run test lint format

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"

run:
	.venv/bin/tecdocauto

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .
