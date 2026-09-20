# The Ministry of Herbology. Workstream B owns this file.
COMPOSE := docker compose -f infra/compose/docker-compose.dev.yml
VENV    := .venv
PY      := $(VENV)/bin/python

.PHONY: help dev down logs fixtures test test-api test-web lint format check contract

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: ## Bring up the local stack (db, redis, mqtt, api, worker, web)
	$(COMPOSE) up --build -d
	@echo "API  http://localhost:8000/api/v1/docs"
	@echo "Web  http://localhost:5173"

down: ## Stop the local stack
	$(COMPOSE) down

logs: ## Follow the stack's logs
	$(COMPOSE) logs -f

fixtures: ## Load fixture data into the dev database
	$(COMPOSE) exec -T db psql -U herbology -d herbology -c 'SELECT 1' >/dev/null
	$(PY) scripts/load_fixtures.py

$(VENV):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -e 'api[dev]'

test: test-api test-web ## Run every test suite

test-api: $(VENV) ## Contract and API tests
	$(PY) -m pytest tests -q

test-web: ## Web unit tests
	cd web && npm run test

contract: $(VENV) ## Contract tests only — the fastest signal that a change is safe
	$(PY) -m pytest tests/contract -q

lint: $(VENV) ## Lint everything
	$(VENV)/bin/ruff check api workers tests
	$(VENV)/bin/black --check api workers tests
	cd web && npm run lint

format: $(VENV) ## Format everything
	$(VENV)/bin/ruff check --fix api workers tests
	$(VENV)/bin/black api workers tests
	cd web && npm run format

check: lint test ## What CI runs
