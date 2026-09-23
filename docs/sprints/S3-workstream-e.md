# S3 — Weather and Environment (Workstream E)

Appended by E ahead of the demo. A owns the sprint's own summary.

## Exit criterion

> Readings stored every 5–15 minutes; forecast visible.

**Met, with one caveat below.** `ingest_observations` is scheduled every ten
minutes and `ingest_forecast` hourly, both `run_at_startup`; `/almanac/forecast`
serves the 10-day daily and 1-day hourly series. The caveat is that nothing in
this repository has a Postgres connection yet: the jobs write through
`workers/weather/store.py` when `ctx` carries one and report what they did when
it does not. Wiring the pool belongs to whoever owns the app's lifespan — see
the requests to A and B below.

## Shipped

- **Open-Meteo ingest** — forecast, recent actuals and archive backfill, with
  NWS as the secondary source the contract names: gridpoint forecast when
  Open-Meteo will not answer, station observations when a station is
  configured, and advisories, which only NWS publishes.
- **Timescale rollups** — the Almanac's history reads `weather_daily` and
  `reading_daily`, never the raw hypertable, and an ingest refreshes the window
  it just touched rather than waiting for the hourly policy.
- **The water balance** — `D(t) = clamp(D(t-1) + K_c·ET₀ − f_cover·P − I, 0,
  D_max)`, still written once in `workers/weather/tasks.py`. The S0 mock had a
  second copy of it inside `api/almanac/router.py`; that is gone.
- **The frost guard** — 3 °F margin, 72-hour lookahead, one alert per plant,
  containers indoors and in-ground plants covered, return-outdoors after three
  mild nights counted from the last frost.
- **ADR 0016's ET₀ fallback** — Hargreaves, computed locally, labelled per day.
- **`/almanac`** — all four endpoints, served from the engines.

## The thing this sprint was actually about

Under ADR 0010 there is no soil hardware, so the water balance is the sole
authority on outdoor watering, and its worst failure is not being wrong — it is
**failing closed and looking healthy**. If ET₀ stops arriving, the deficit stops
advancing, every plant reads as comfortable and the app goes quiet, which is
indistinguishable from a garden that needs nothing.

So degraded inputs leave the engines as degraded confidence:

- ET₀ from Open-Meteo, else Hargreaves (labelled, caps at `medium`), else
  missing — and a missing day does **not** advance the deficit, is counted, and
  is declared, because an unknown day is not a zero-evaporation day.
- A category-default `water_k_c` under ADR 0013 caps the answer at `medium` and
  names the table and category it came from; an uncited one drags the answer to
  `unknown` while still producing a complete decision (ADR 0004, rule 6).
- A stale ingest, a forecast day, or a run on NWS each add their own reason.
- The frost guard reports the plants it **could not** assess beside the alerts,
  so an unanswerable question cannot read as a reassuring answer.

One thing is deliberately *not* a caveat: a missing soil sensor. ADR 0010 makes
model-only the shipping path, and a warning that fires on every plant every day
is a warning nobody reads on the day it means something.

## For A

1. **`WaterBalance` and `FrostAlert` need the confidence fields.** The
   responses carry `confidence`, `degraded`, `degradations[]`, per-day
   `et0_method` and `reference_et0_mm`, `k_c_confidence`, `k_c_source` and
   `k_c_is_category_default`. All additive; none in the contract. Rule 1 says E
   does not add them.
2. **`/almanac/frost` has no room for a plant that cannot be judged.** The
   response is typed as a list of `FrostAlert`. An envelope
   (`{alerts: [], unassessable: []}`) would let the UI show it.
3. **The advisory trigger and the contract test disagree.** The plan says alert
   when the low crosses the threshold *or* an NWS advisory covers the site, but
   `test_a_frost_alert_reports_the_night_it_actually_names` requires every
   alert's stated low to sit at or below its own stated threshold — which an
   advisory-only alert cannot satisfy. E has implemented the advisory as
   corroboration that extends the lookahead and raises confidence. A decides.
4. **`weather_obs` has no unique index.** `weather_daily` sums `precip_mm` with
   no source in the grouping, so two rows for one hour double the day's rain
   and clear a deficit nothing cleared. E replaces each window on write; a
   unique index on `(site_id, time)` would let the database enforce it.
5. **`climate_indices` is not a dependency.** ADR 0016 names it. Dependencies
   live in `api/pyproject.toml`, which E does not own. The Hargreaves method is
   implemented as one pure function meanwhile; adding the library or amending
   the ADR is A's call.

## For L and A — a fixture discrepancy

`fixtures/site.json` gives `nws_zone: INZ050`, which NWS resolves to **Wayne
County**. The site's own coordinates (39.7684, -86.1581) resolve to **INZ047,
Marion County**; the recorded `/points` payload says so. An advisory fetched for
the wrong county is an advisory about somebody else's frost. Fixtures belong to
L and A, so this is reported, not edited.

Separately: every *outdoor* specimen in the fixtures has a cited `water_k_c`.
The two uncited ones are both indoors, so the fixtures never exercise the
uncited path on the engine that ADR 0004's warning is actually about. The unit
tests cover it directly, but a scenario would be better.

## For B — a CI hole

`api/pyproject.toml` sets `[tool.black] line-length = 100`, and CLAUDE.md says
the same. CI runs `black --check api workers tests scripts` **from the
repository root**, where black finds no configuration and falls back to its
default of 88. A contributor who runs `black api/almanac` locally, picking up
the project's own setting, produces files CI then rejects. The tree is
currently formatted at 88 throughout, so the fix is either a root
`pyproject.toml` or `-l 100` in the workflow — not a reformat.

Minor, same area: a test module's basename must be unique repository-wide,
because there is no root pytest config and the default import mode names
modules by basename. `workers/weather/tests/test_http.py` collided with
`workers/botany/tests/test_http.py` and stopped the whole run at collection.
Fixed here with a package marker and a rename.
