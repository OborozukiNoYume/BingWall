PYTHON_BIN ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: setup format lint typecheck test verify verify-deploy db-migrate collect-bing collect-nasa-apod consume-collection-tasks inspect-resources backup restore verify-backup-restore run clean

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
	$(VENV_PYTHON) -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py

test:
	$(VENV_PYTHON) -m pytest

verify: lint typecheck test

verify-deploy:
	$(VENV_PYTHON) scripts/verify_t1_6.py

db-migrate:
	$(VENV_PYTHON) -m app.repositories.migrations

collect-bing:
	$(VENV_PYTHON) -m app.collectors.bing --market $(MARKET) --count $(COUNT)

collect-nasa-apod:
	$(VENV_PYTHON) -m app.collectors.nasa_apod --market $(MARKET)

consume-collection-tasks:
	$(VENV_PYTHON) -m app.collectors.manual_tasks

inspect-resources:
	$(VENV_PYTHON) scripts/run_resource_inspection.py

backup:
	$(VENV_PYTHON) scripts/run_backup.py

restore:
	@if [ -z "$(SNAPSHOT)" ]; then echo "SNAPSHOT is required, e.g. make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1"; exit 1; fi
	@if [ -n "$(TARGET_ROOT)" ]; then $(VENV_PYTHON) scripts/run_restore.py --snapshot "$(SNAPSHOT)" --target-root "$(TARGET_ROOT)" $(if $(FORCE),--force,); else $(VENV_PYTHON) scripts/run_restore.py --snapshot "$(SNAPSHOT)" $(if $(FORCE),--force,); fi

verify-backup-restore:
	$(VENV_PYTHON) scripts/verify_t2_5.py

run:
	$(VENV_PYTHON) -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
