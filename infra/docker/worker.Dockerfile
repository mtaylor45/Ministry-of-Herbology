# Arq workers: botany, weather, hub, plates. Workstream B.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN adduser --system --group --no-create-home herbology

# Dependencies and the packages come from one install, after the source is in
# place. The usual trick — copy the manifest, install, then copy the source —
# cannot work here: `[tool.setuptools] packages` names five directories, and
# setuptools resolves them at install time, so installing against a lone
# pyproject.toml fails with "package directory 'app' does not exist".
COPY api/ /srv/api/
COPY workers/ /srv/workers/
COPY contracts/ /srv/contracts/
COPY fixtures/ /srv/fixtures/

RUN pip install --no-cache-dir /srv/api

ENV PYTHONPATH=/srv/api:/srv
USER herbology

# WORKER_MODULE picks the workstream: workers.weather.tasks, workers.botany.tasks, …
ENV WORKER_MODULE=workers.weather.tasks
CMD ["sh", "-c", "arq ${WORKER_MODULE}.WorkerSettings"]
