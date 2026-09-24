# The Ministry of Herbology. Workstream B owns this file.
COMPOSE := docker compose -f infra/compose/docker-compose.dev.yml
VENV    := .venv
PY      := $(VENV)/bin/python

# --- Deployment ---------------------------------------------------------------
#
# Everything below is parameters, never values. `make images` and `make push`
# need MOH_REGISTRY; `make stack-deploy` needs the rest, and reads them from
# MOH_ENV_FILE. docs/deploy/README.md is the guide.

STACK_FILE  := infra/stack/docker-stack.yml
MOH_STACK   ?= moh
MOH_ENV_FILE ?= .env.deploy

# The tag identifies the source it was built from, or the build fails. A dirty
# tree gets a -dirty suffix, so an image whose contents nobody can reconstruct
# cannot be quietly pushed under a clean-looking tag.
GIT_SHA         := $(shell git rev-parse --short=12 HEAD 2>/dev/null)
GIT_DESCRIBE    := $(shell git describe --tags --always --dirty 2>/dev/null)
MOH_IMAGE_TAG   ?= $(GIT_DESCRIBE)
BUILD_TIMESTAMP := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
IMAGES          := api web worker

.PHONY: help dev down logs fixtures test test-api test-web lint format check contract
.PHONY: images push stack-config stack-deploy stack-rm stack-ps
.PHONY: migrate migrate-status backup restore-check

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

# ------------------------------------------------------------------------------
# Deployment. See docs/deploy/README.md.
# ------------------------------------------------------------------------------

# MOH_REGISTRY is your registry and your namespace, with no trailing slash:
#   registry.example.net/ministry-of-herbology, ghcr.io/you, localhost:5000/moh
require-registry:
	@test -n "$(MOH_REGISTRY)" || { \
	  echo "MOH_REGISTRY is not set."; \
	  echo "It is your registry and namespace, with no trailing slash, e.g."; \
	  echo "  make push MOH_REGISTRY=registry.example.net/ministry-of-herbology"; \
	  exit 1; }

require-clean-tree:
	@test -z "$$(git status --porcelain 2>/dev/null)" || test -n "$(MOH_ALLOW_DIRTY)" || { \
	  echo "The working tree has uncommitted changes, so $(MOH_IMAGE_TAG) would not"; \
	  echo "identify what is in the image. Commit them, or accept that by setting"; \
	  echo "MOH_ALLOW_DIRTY=1."; \
	  exit 1; }

images: require-registry ## Build the three images, tagged from the commit
	@echo "Building $(MOH_IMAGE_TAG) for $(MOH_REGISTRY)"
	@for image in $(IMAGES); do \
	  echo "  moh-$$image"; \
	  docker build \
	    --file infra/docker/$$image.Dockerfile \
	    --tag "$(MOH_REGISTRY)/moh-$$image:$(MOH_IMAGE_TAG)" \
	    --label org.opencontainers.image.title="ministry-of-herbology-$$image" \
	    --label org.opencontainers.image.revision="$(GIT_SHA)" \
	    --label org.opencontainers.image.version="$(MOH_IMAGE_TAG)" \
	    --label org.opencontainers.image.created="$(BUILD_TIMESTAMP)" \
	    --label org.opencontainers.image.source="https://github.com/mtaylor45/ministry-of-herbology" \
	    . || exit 1; \
	done
	@echo
	@echo "Built:"
	@for image in $(IMAGES); do echo "  $(MOH_REGISTRY)/moh-$$image:$(MOH_IMAGE_TAG)"; done

push: require-registry require-clean-tree images ## Build, then push to MOH_REGISTRY
	@for image in $(IMAGES); do \
	  echo "pushing moh-$$image"; \
	  docker push "$(MOH_REGISTRY)/moh-$$image:$(MOH_IMAGE_TAG)" || exit 1; \
	done
	@echo
	@echo "Deploy this build with:  MOH_IMAGE_TAG=$(MOH_IMAGE_TAG) make stack-deploy"

# `docker stack deploy` interpolates from the shell and has no --env-file, so
# the env file is sourced here rather than passed. set -a exports every
# assignment in it; the two `set +a` lines put the shell back as it was.
define load_env
set -a; \
[ -f "$(MOH_ENV_FILE)" ] && . "./$(MOH_ENV_FILE)"; \
set +a;
endef

stack-config: ## Render the stack with your variables filled in, and check it
	@$(load_env) \
	docker compose -f $(STACK_FILE) config

stack-deploy: ## Deploy or update the stack (reads MOH_ENV_FILE)
	@test -f "$(MOH_ENV_FILE)" || { \
	  echo "$(MOH_ENV_FILE) does not exist."; \
	  echo "Copy .env.example to $(MOH_ENV_FILE) and fill it in — every value is"; \
	  echo "yours to choose. docs/deploy/README.md walks through it."; \
	  exit 1; }
	@$(load_env) \
	MOH_IMAGE_TAG="$${MOH_IMAGE_TAG:-$(MOH_IMAGE_TAG)}" \
	docker stack deploy \
	  --detach=false \
	  --resolve-image=always \
	  -c $(STACK_FILE) "$(MOH_STACK)"

stack-ps: ## What the stack is doing
	@docker stack ps "$(MOH_STACK)" \
	  --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}\t{{.Error}}'

stack-rm: ## Remove the stack. Volumes and secrets survive this.
	docker stack rm "$(MOH_STACK)"

migrate-status: ## Which schema migrations have run against the live database
	@MOH_STACK="$(MOH_STACK)" scripts/migrate.sh status

migrate: ## Apply pending schema migrations to the live database
	@MOH_STACK="$(MOH_STACK)" scripts/migrate.sh apply

backup: ## Dump the live database into ./backups/
	@MOH_STACK="$(MOH_STACK)" scripts/backup.sh

restore-check: ## Prove the newest backup by restoring it into a scratch database
	@dump=$$(ls -t backups/*.dump 2>/dev/null | head -n 1); \
	test -n "$$dump" || { echo "No backup in ./backups/. Run: make backup"; exit 1; }; \
	echo "Restoring $$dump into a scratch database"; \
	MOH_STACK="$(MOH_STACK)" scripts/restore.sh --from "$$dump"
