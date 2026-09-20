# Arq workers: botany, weather, hub, plates. Workstream B.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN adduser --system --group --no-create-home herbology

COPY api/pyproject.toml /srv/api/pyproject.toml
RUN pip install --no-cache-dir /srv/api

COPY api/ /srv/api/
COPY workers/ /srv/workers/
COPY contracts/ /srv/contracts/
COPY fixtures/ /srv/fixtures/

ENV PYTHONPATH=/srv/api:/srv
USER herbology

# WORKER_MODULE picks the workstream: workers.weather.tasks, workers.botany.tasks, …
ENV WORKER_MODULE=workers.weather.tasks
CMD ["sh", "-c", "arq ${WORKER_MODULE}.WorkerSettings"]
