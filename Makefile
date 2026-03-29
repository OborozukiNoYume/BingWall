UV_BIN ?= uv
PYTHON_VERSION ?= 3.14
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: setup format lint typecheck test verify verify-deploy db-migrate collect-bing collect-nasa-apod create-scheduled-collection-tasks scheduled-collect consume-collection-tasks inspect-resources archive-wallpapers backup restore install-cron verify-backup-restore run clean

MARKET ?= en-US
COUNT ?= 1
CRON_APP_DIR ?= /opt/bingwall/app
CRON_VENV_PYTHON ?= $(CRON_APP_DIR)/.venv/bin/python
CRON_LOG_DIR ?= /var/log/bingwall
CRON_ENV_FILE ?= /etc/bingwall/bingwall.env
CRONTAB_BIN ?= crontab

setup:
	$(UV_BIN) python install $(PYTHON_VERSION)
	$(UV_BIN) sync --python $(PYTHON_VERSION) --frozen

format:
	$(VENV_PYTHON) -m ruff check . --fix
	$(VENV_PYTHON) -m ruff format .

lint:
	$(VENV_PYTHON) -m ruff check .

typecheck:
	$(VENV_PYTHON) -m mypy app tests scripts/create_scheduled_collection_tasks.py scripts/install_cron.py scripts/run_resource_inspection.py scripts/run_wallpaper_archive.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py

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

create-scheduled-collection-tasks:
	$(VENV_PYTHON) scripts/create_scheduled_collection_tasks.py

scheduled-collect:
	$(VENV_PYTHON) scripts/create_scheduled_collection_tasks.py
	$(VENV_PYTHON) -m app.collectors.manual_tasks --max-tasks 5

consume-collection-tasks:
	$(VENV_PYTHON) -m app.collectors.manual_tasks

inspect-resources:
	$(VENV_PYTHON) scripts/run_resource_inspection.py

archive-wallpapers:
	$(VENV_PYTHON) scripts/run_wallpaper_archive.py

backup:
	$(VENV_PYTHON) scripts/run_backup.py

restore:
	@if [ -z "$(SNAPSHOT)" ]; then echo "SNAPSHOT is required, e.g. make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1"; exit 1; fi
	@if [ -n "$(TARGET_ROOT)" ]; then $(VENV_PYTHON) scripts/run_restore.py --snapshot "$(SNAPSHOT)" --target-root "$(TARGET_ROOT)" $(if $(FORCE),--force,); else $(VENV_PYTHON) scripts/run_restore.py --snapshot "$(SNAPSHOT)" $(if $(FORCE),--force,); fi

install-cron:
	$(VENV_PYTHON) scripts/install_cron.py --install --app-dir "$(CRON_APP_DIR)" --venv-python "$(CRON_VENV_PYTHON)" --log-dir "$(CRON_LOG_DIR)" --env-file "$(CRON_ENV_FILE)" --crontab-bin "$(CRONTAB_BIN)"

verify-backup-restore:
	$(VENV_PYTHON) scripts/verify_t2_5.py

run:
	$(VENV_PYTHON) -c 'from app.core.config import get_settings; import uvicorn; settings = get_settings(); uvicorn.run("app.main:create_app", factory=True, host=settings.app_host, port=settings.app_port)'

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
