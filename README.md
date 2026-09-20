# The Ministry of Herbology

A self-hosted, mobile-first web app for keeping an inventory of your indoor and
outdoor plants and actually tending them — with weather-aware watering, frost
alerts, sensor integration and a wizarding-botany theme.

> Status: **S0 — Charter.** Contracts and scaffolding are in place; feature
> workstreams are in flight. See [the development plan](docs/plan/development-plan.md).

## What it does

- **Morning Rounds** — today's tasks, with rain-satisfied waterings and frost
  warnings, one-tap and batch completion.
- **The Register** — your inventory: search and filter by location, zone, status
  and toxicity; groups and beds.
- **The Grounds** — indoor floor plans and an outdoor property survey as map
  layers, with zones and per-plant pins.
- **The Almanac** — 1-day and 10-day forecast; 1/7/30-day indoor and outdoor
  conditions history.
- **The Naturalist's Journal** — an illustrated plate per specimen, browsable as a
  page-turning book.
- **Calendar subscription** — a private ICS feed per household member, filterable,
  subscribable in Google and Apple Calendar.

Every plant has one Specimen page with four linked facets: Register Entry,
Tending, Compendium and Journal.

## Principles

Care values are never invented — each carries a source citation and a confidence
level, and you can edit any of them. Every themed status is paired with a plain
one ("Parched — water today"). The theme is original wizarding-botany: no
franchise assets.

## Stack

SvelteKit PWA · FastAPI · Postgres + TimescaleDB · Redis + Arq · Leaflet · uPlot,
deployed as a Docker stack behind Nginx.

## Getting started

```sh
make dev      # bring up the dev stack
make fixtures # load sample plants, locations and weather scenarios
open http://localhost:5173
```

## Documentation

- [Development plan](docs/plan/development-plan.md) — scope, architecture, sprints
- [Workstreams](docs/agents/README.md) — who owns what
- [Architecture decisions](docs/adr/) — ADRs
- [Contracts](contracts/README.md) — schema, OpenAPI, events
