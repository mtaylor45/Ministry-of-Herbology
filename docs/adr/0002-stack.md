# ADR 0002 — Stack: SvelteKit, FastAPI, Postgres/TimescaleDB

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

The app is self-hosted on a 3-node Docker swarm with images in Harbor, behind
Nginx. It is mobile-first, offline-capable, and stores a lot of time-series data
(sensor readings every 5–15 minutes, hourly weather, 10-day forecasts) that it
must chart over 1, 7 and 30 days.

## Decision

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | SvelteKit PWA | Small bundles matter on a phone in a garden; the service worker gives us offline care pages for free. |
| Maps | Leaflet | `CRS.Simple` handles floor plans without a projection; a georeferenced image overlay handles the survey. Both in one library. |
| Charts | uPlot | Tiny and fast with tens of thousands of points, which the 30-day views will have. |
| API | FastAPI | The OpenAPI document is the contract, and FastAPI is generated from and validated against the same types. |
| Database | Postgres 16 + TimescaleDB | One database for relational plant data *and* hypertable time-series, with continuous aggregates doing the 1/7/30-day rollups. No second datastore. |
| Jobs | Redis + Arq | Async-native, same asyncio world as FastAPI, no Celery ceremony. |
| Object storage | MinIO (or a NAS share) | Plates, photos and uploaded plans are large and do not belong in Postgres. |

## Alternatives considered

- **Next.js** instead of SvelteKit: larger runtime, and we need no React ecosystem here.
- **InfluxDB** for time-series: a second datastore, a second query language, and
  joins between a reading and its specimen become application-level work.
- **Celery**: heavier than this workload needs.

## Consequences

Python 3.11 and Node 22 are the toolchains. Every service is a container; the dev
stack is the prod stack with different compose files. TimescaleDB pins us to a
Postgres image that carries the extension.
