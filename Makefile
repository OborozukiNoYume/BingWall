UV_BIN ?= uv
PYTHON_VERSION ?= 3.14
VENV ?= .venv
UV_RUN := $(UV_BIN) run python

.PHONY: setup format lint typecheck test verify verify-deploy db-migrate collect-bing collect-nasa-apod create-scheduled-collection-tasks scheduled-collect consume-collection-tasks inspect-resources archive-wallpapers backup restore install-cron verify-backup-restore run clean

MARKET ?= en-US
COUNT ?= 1
CRON_APP_DIR ?= /opt/bingwall/app
CRON_UV_BIN ?= $(UV_BIN)
CRON_LOG_DIR ?= /var/log/bingwall
CRON_ENV_FILE ?= /etc/bingwall/bingwall.env
CRONTAB_BIN ?= crontab

setup:
	$(UV_BIN) python install $(PYTHON_VERSION)
	$(UV_BIN) sync --python $(PYTHON_VERSION) --frozen

format:
	$(UV_RUN) -m ruff check . --fix
	$(UV_RUN) -m ruff format .

lint:
	$(UV_RUN) -m ruff check .

typecheck:
	$(UV_RUN) -m mypy app tests scripts/create_scheduled_collection_tasks.py scripts/install_cron.py scripts/run_resource_inspection.py scripts/run_wallpaper_archive.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py

test:
	$(UV_RUN) -m pytest

verify: lint typecheck test

verify-deploy:
	$(UV_RUN) scripts/verify_t1_6.py

db-migrate:
	$(UV_RUN) -m app.repositories.migrations

collect-bing:
	$(UV_RUN) -m app.collectors.bing --market $(MARKET) --count $(COUNT)

collect-nasa-apod:
	$(UV_RUN) -m app.collectors.nasa_apod --market $(MARKET)

create-scheduled-collection-tasks:
	$(UV_RUN) scripts/create_scheduled_collection_tasks.py

scheduled-collect:
	$(UV_RUN) scripts/create_scheduled_collection_tasks.py
	$(UV_RUN) -m app.collectors.manual_tasks --max-tasks 5

consume-collection-tasks:
	$(UV_RUN) -m app.collectors.manual_tasks

inspect-resources:
	$(UV_RUN) scripts/run_resource_inspection.py

archive-wallpapers:
	$(UV_RUN) scripts/run_wallpaper_archive.py

backup:
	$(UV_RUN) scripts/run_backup.py

restore:
	@if [ -z "$(SNAPSHOT)" ]; then echo "SNAPSHOT is required, e.g. make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1"; exit 1; fi
	@if [ -n "$(TARGET_ROOT)" ]; then $(UV_RUN) scripts/run_restore.py --snapshot "$(SNAPSHOT)" --target-root "$(TARGET_ROOT)" $(if $(FORCE),--force,); else $(UV_RUN) scripts/run_restore.py --snapshot "$(SNAPSHOT)" $(if $(FORCE),--force,); fi

install-cron:
	$(UV_RUN) scripts/install_cron.py --install --app-dir "$(CRON_APP_DIR)" --uv-bin "$(CRON_UV_BIN)" --log-dir "$(CRON_LOG_DIR)" --env-file "$(CRON_ENV_FILE)" --crontab-bin "$(CRONTAB_BIN)"

verify-backup-restore:
	$(UV_RUN) scripts/verify_t2_5.py

run:
	$(UV_RUN) -c 'from app.core.config import get_settings; import uvicorn; settings = get_settings(); uvicorn.run("app.main:create_app", factory=True, host=settings.app_host, port=settings.app_port)'

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
