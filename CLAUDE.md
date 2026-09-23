# The Ministry of Herbology — agent working agreement

A self-hosted, mobile-first web app for inventorying and tending indoor and outdoor
plants, with weather- and sensor-aware care scheduling and a wizarding-botany theme.

The authoritative scope, sprint plan and workstream list live in
`docs/plan/development-plan.md`. Read it before starting work. The visual reference
is `docs/design/style-guide.md`.

## The eight rules

1. **Contract-first.** `contracts/` (DB schema, OpenAPI spec, event topics) and
   `fixtures/` are frozen. Only Workstream A (Architect) changes them, and only via
   an ADR in `docs/adr/`. If you need a contract change, open an issue/PR describing
   it and tag A — do not edit `contracts/` yourself.
2. **Own your directory.** Each workstream writes only inside its owned paths (see
   `docs/agents/README.md` and `.github/CODEOWNERS`). Cross-cutting changes go
   through A.
3. **Build against mocks.** Every service ships a mock matching the contract, so no
   agent waits on another. Mocks live beside the code they stand in for
   (`*/mocks/`) and are driven by `fixtures/`.
4. **One task, one PR.** Each PR carries tests, a short description, and a link to
   its sprint task. A reviews and merges. Open PRs as drafts.
5. **Definition of done.** Tests pass in CI, the change deploys to staging, the UI
   meets WCAG AA, and docs are updated.
6. **No invented plant facts.** Every care value carries a source citation
   (`source_id`) and a confidence level, and the user can edit it. A value with no
   citation must be `confidence: unknown` and visibly marked in the UI.
7. **Theme without franchise assets.** Wizarding-botany aesthetic only: no
   franchise crests or emblems, house names or house iconography, film typefaces,
   character names, or other franchise IP. One *original* Ministry seal is
   permitted — it may evoke the genre, but it copies no trademarked or copyrighted
   design; ADR 0017 draws the line and A reviews the mark. Themed copy is always
   paired with a plain-language equivalent. The visual reference is
   `docs/design/style-guide.md` — read it before designing any surface, and ADR 0017
   for where it yields to accessibility, the contract and this rule.
8. **Weekly integration demo** at the end of each sprint, exit criteria checked by
   the maintainer.

## Layout

| Path | Owner | Contents |
| --- | --- | --- |
| `contracts/` | A | Schema, OpenAPI, event topics — frozen |
| `docs/adr/` | A | Architecture decision records |
| `docs/design/` | A | The Enchanted Academy style guide — the visual reference |
| `infra/`, `.github/` | B | CI, images, compose, swarm stacks |
| `api/inventory/` | C | Specimens, locations, zones, groups, photos, logs, members |
| `workers/botany/` | D | Taxon resolution, source connectors, cited care synthesis |
| `workers/weather/`, `api/almanac/` | E | Open-Meteo/NWS ingest, water balance, frost engine |
| `workers/hub/` | F | Home Assistant adapter, soil sensors, MQTT, calendar push |
| `api/tending/` | G | Care rules, tasks, recurrences, notifications, ICS feeds |
| `api/grounds/`, `web/src/lib/map/` | H | Plans, surveys, calibration, zones, pins |
| `web/src/lib/ui/`, `web/src/app-shell/` | I | Theme tokens, components, PWA shell, a11y |
| `web/src/routes/` | J | Morning Rounds, Register, Specimen facets, Almanac, Office |
| `workers/plates/`, `web/src/routes/journal/` | K | Plate sourcing, AI fallback, book view |
| `tests/`, `fixtures/`, `docs/user/` | L | Scenario fixtures, e2e, contract tests, user docs |

## Stack

SvelteKit PWA · FastAPI (Python 3.11) · Postgres 16 + TimescaleDB · Redis + Arq ·
Leaflet · uPlot · Docker stack behind Nginx. See `docs/adr/0002-stack.md`.

## Conventions

- Python: `ruff` + `black` line length 100, `mypy` on `api/` and `workers/`.
  Tests with `pytest`.
- TypeScript/Svelte: `prettier` + `eslint`, `svelte-check`. Tests with `vitest`;
  e2e with Playwright (browsers are preinstalled; never run `playwright install`).
- Units are SI internally (mm, °C, litres); display units are a user preference.
- All timestamps stored UTC, `timestamptz`. Local time is resolved per-site.
- Migrations are forward-only, numbered, in `contracts/schema/`.
- Branch naming: `ws-<id>/<sprint>-<slug>`, e.g. `ws-e/s3-openmeteo-ingest`.
- Commits: imperative mood, prefixed with the workstream id: `[E] add ET0 ingest`.

## Local development

```
make dev        # docker compose up: postgres+timescale, redis, api, web, mqtt
make test       # ruff, mypy, pytest, vitest, contract tests
make fixtures   # reload fixture data into the dev database
```
