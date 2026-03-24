PYTHON_BIN ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: setup format lint typecheck test verify db-migrate collect-bing run clean

MARKET ?= en-US
COUNT ?= 1

setup:
	$(PYTHON_BIN) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"
	$(VENV_PYTHON) -m pip freeze --all --exclude-editable > requirements.lock.txt

format:
	$(VENV_PYTHON) -m ruff check . --fix
	$(VENV_PYTHON) -m ruff format .

lint:
	$(VENV_PYTHON) -m ruff check .

typecheck:
	$(VENV_PYTHON) -m mypy app tests

test:
	$(VENV_PYTHON) -m pytest

verify: lint typecheck test

db-migrate:
	$(VENV_PYTHON) -m app.repositories.migrations

collect-bing:
	$(VENV_PYTHON) -m app.collectors.bing --market $(MARKET) --count $(COUNT)

run:
	$(VENV_PYTHON) -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
