.PHONY: help show-config venv install test test-fast test-api test-llm test-config test-workflow test-core eval-baseline run doctor ci healthcheck smoke clean

PYTHON ?= python3
.DEFAULT_GOAL := help
VENV_DIR ?= .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
VENV_UVICORN := $(VENV_DIR)/bin/uvicorn
DEPS_STAMP := $(VENV_DIR)/.deps-installed
APP_MODULE ?= paper_writer_agent.api.app:app
APP_RUN_HOST ?= 0.0.0.0
APP_RUN_PORT ?= 8000
HEALTHCHECK_HOST ?= 127.0.0.1
HEALTHCHECK_PORT ?= $(APP_RUN_PORT)
HEALTHCHECK_RETRIES ?= 10
HEALTHCHECK_INTERVAL_S ?= 0.5
HEALTHCHECK_PATH ?= /health
HEALTHCHECK_TIMEOUT_S ?= 5
HEALTHCHECK_LOG_FILE ?= /tmp/pwa_uvicorn.log

$(VENV_PY):
	$(PYTHON) -m venv $(VENV_DIR)

$(DEPS_STAMP): requirements.txt | $(VENV_PY)
	$(VENV_PIP) install -r requirements.txt
	@touch $(DEPS_STAMP)

venv: $(VENV_PY)

help:
	@echo "Available targets:"
	@echo "  make doctor  - create/reuse .venv, install deps if needed, print env versions"
	@echo "  make test    - run full pytest suite in project venv"
	@echo "  make test-fast - run fast unit-style tests (skip API integration tests)"
	@echo "  make test-api - run API tests only"
	@echo "  make test-llm - run LLM tests only"
	@echo "  make test-config - run config tests only"
	@echo "  make test-workflow - run workflow tests only"
	@echo "  make test-core - run llm+config+workflow core tests"
	@echo "  make eval-baseline - run fixed Day11 evaluation samples and print summary JSON"
	@echo "  make run     - run API app with configurable module/host/port"
	@echo "  make ci      - run doctor + test in sequence"
	@echo "  make healthcheck - boot API and verify endpoint (configurable module/host/port/path/timeout/log)"
	@echo "  make smoke   - run healthcheck + ci full verification"
	@echo "  make show-config - print resolved runtime/healthcheck config"
	@echo "  make clean   - remove .venv and pytest cache"

show-config:
	@echo "APP_MODULE=$(APP_MODULE)"
	@echo "APP_RUN_HOST=$(APP_RUN_HOST)"
	@echo "APP_RUN_PORT=$(APP_RUN_PORT)"
	@echo "HEALTHCHECK_HOST=$(HEALTHCHECK_HOST)"
	@echo "HEALTHCHECK_PORT=$(HEALTHCHECK_PORT)"
	@echo "HEALTHCHECK_PATH=$(HEALTHCHECK_PATH)"
	@echo "HEALTHCHECK_RETRIES=$(HEALTHCHECK_RETRIES)"
	@echo "HEALTHCHECK_INTERVAL_S=$(HEALTHCHECK_INTERVAL_S)"
	@echo "HEALTHCHECK_TIMEOUT_S=$(HEALTHCHECK_TIMEOUT_S)"
	@echo "HEALTHCHECK_LOG_FILE=$(HEALTHCHECK_LOG_FILE)"

install: $(DEPS_STAMP)

test: install
	$(VENV_PY) -m pytest -q

test-fast: test-core

test-api: install
	$(VENV_PY) -m pytest -q tests/test_api.py

test-llm: install
	$(VENV_PY) -m pytest -q tests/test_llm.py

test-config: install
	$(VENV_PY) -m pytest -q tests/test_config.py

test-workflow: install
	$(VENV_PY) -m pytest -q tests/test_workflow.py

test-core: test-llm test-config test-workflow

eval-baseline: install
	$(VENV_PY) -m paper_writer_agent.evaluation_runner

run: install
	$(VENV_UVICORN) $(APP_MODULE) --host $(APP_RUN_HOST) --port $(APP_RUN_PORT)

doctor: install
	$(VENV_PY) -c "import sys,fastapi,requests,pytest; print('python=', sys.version.split()[0]); print('fastapi=', fastapi.__version__); print('requests=', requests.__version__); print('pytest=', pytest.__version__)"

ci: doctor test

smoke: healthcheck ci

healthcheck: install
	@set -e; \
	$(VENV_UVICORN) $(APP_MODULE) --host $(HEALTHCHECK_HOST) --port $(HEALTHCHECK_PORT) >$(HEALTHCHECK_LOG_FILE) 2>&1 & \
	PID=$$!; \
	trap "kill $$PID" EXIT; \
	ok=0; \
	attempt=0; \
	resp=""; \
	deadline=`$(VENV_PY) -c "import time; print(time.time() + float('$(HEALTHCHECK_TIMEOUT_S)'))"`; \
	while true; do \
		attempt=$$((attempt+1)); \
		if resp=`curl -fsS http://$(HEALTHCHECK_HOST):$(HEALTHCHECK_PORT)$(HEALTHCHECK_PATH) 2>/dev/null`; then ok=1; break; fi; \
		now=`$(VENV_PY) -c "import time; print(time.time())"`; \
		if $(VENV_PY) -c "import sys; sys.exit(0 if float('$${now}') > float('$${deadline}') else 1)"; then break; fi; \
		if [ $$attempt -ge $(HEALTHCHECK_RETRIES) ]; then break; fi; \
		sleep $(HEALTHCHECK_INTERVAL_S); \
	done; \
	if [ $$ok -ne 1 ]; then \
		echo "healthcheck failed; uvicorn log:"; \
		tail -n 80 $(HEALTHCHECK_LOG_FILE); \
		exit 1; \
	fi; \
	printf "%s" "$$resp"

clean:
	rm -rf $(VENV_DIR) .pytest_cache
