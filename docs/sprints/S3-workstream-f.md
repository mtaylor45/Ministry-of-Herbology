# S3 — Home and IoT (Workstream F)

Appended by F ahead of the demo. A owns the sprint's own summary.

## Exit criterion

> Indoor and outdoor readings stored every 5–15 minutes.

**The indoor half is met, with the same caveat E recorded for the outdoor
half.** `poll_home_assistant` is scheduled every five minutes with
`run_at_startup`, and each `sensor_source` then decides for itself whether it
is due via its own `poll_seconds` — the cron sets the finest cadence any row
asks for, the row sets the one it wants. A thermostat is not a soil probe.

The caveat is that nothing in this repository has a Postgres connection yet.
The jobs write through `workers/hub/store.py` when `ctx` carries one and report
what they did when it does not — the same seam E left, and wiring the pool
still belongs to whoever owns the app's lifespan.

## Shipped

- **The Home Assistant adapter** — REST polling against `GET /api/states`, one
  request per poll however many entities are mapped, addressed by HA **entity
  id** with no Nest-specific, HomeKit-specific or Matter-specific code
  anywhere in it (ADR 0009).
- **Entity mapping** — `sensor_source.external_ids` read as *metric to entity
  id*, so one row carries a thermostat's temperature and humidity together and
  "the Study" becomes a series the Almanac can chart. A row with a `location_id`
  is room climate; a row with a `specimen_id` is a probe in one pot.
- **`integration.last_error` and health** — every run leaves a mark whether it
  worked or not, and `hub_health` is the Ministry Office's answer to *is the
  hub actually answering?*
- **MQTT publish-back** — every topic, payload and discovery config in
  `contracts/events/mqtt.md`, retained, with stable object ids and the
  availability topic as the last will. The transport is the one missing piece;
  see the request to A and B below.
- **The WebSocket protocol** — the handshake, the subscription, `state_changed`
  parsing and the reconnect backoff. Also transport-less, also below.

## The thing this sprint was actually about

ADR 0009 made Home Assistant the **only** route to indoor conditions. There is
no direct Nest integration and none is planned, so if this adapter stops,
indoor readings stop and nothing else fills in behind it.

That makes one failure worse than being wrong: **being silent**. A job that
quietly stops leaves the last readings in place, the Almanac draws a line
through the gap, and a household sees a chart that looks like a steady 21 °C
room. Every design decision below is about making that impossible.

- **A hub that is down does not look like a hub with nothing to say.** A failed
  poll returns a report with an `error`, never an exception for Arq to log and
  forget, and the text lands on `integration.last_error`.
- **A working hub with a broken mapping is not a success.** The job ran, no
  exception was raised, and the hypertable stayed empty — that is its own
  reported failure, with the offending entity ids named.
- **Every entity that was asked for and did not answer is named, with a
  reason**: not found, unavailable, stale, wrong device class, unconvertible
  unit, out of range. A poll that returns four readings where five were
  configured never passes as four readings.
- **A stale entity is dropped rather than stored.** Home Assistant serves the
  last state it saw with no expiry, so a battery that died in March still reads
  19.4 °C in July. Past `entity_max_age_s` the value is not written, which is
  what lets the Almanac render "no recent reading" instead of a flat line —
  ADR 0009's own words, and the same discipline ADR 0018 has just written into
  the Almanac's responses.
- **A deployment with every source disabled does not read as healthy.** Nothing
  was asked of Home Assistant, so nothing was learned about it, and `last_ok_at`
  is not stamped.
- **`unconfigured` is kept apart from `down`.** One is a setup step and one is a
  fault, and a screen that shows them the same way trains people to ignore the
  row. Likewise a source that has never reported is `awaiting`, not a problem:
  it is usually a deployment four minutes old.

Three refusals in `entities.py` carry the same idea down to a single value. An
unrecognised unit is refused rather than assumed, because 68 °F read as Celsius
is a frost warning and read correctly is a comfortable room. A `device_class`
that contradicts the operator's mapping is refused, because that is what stops
a bathroom hygrometer being stored as `soil_moisture_pct` — which under ADR
0010 would not be a mislabelled row, it would be the app inventing a probe that
does not exist and handing E's water balance an override to obey. And an
impossible value is refused before it reaches a rollup nothing can correct
later.

## ADR 0010, kept honestly

The soil-probe path is complete and tested: a probe binds to a specimen, its
reading is stored with the specimen on it, and the day one appears the only
change needed is a `sensor_source` row. Nothing pretends one exists. The mock
world derives no soil entity, `validation_errors` refuses a soil metric with no
pot behind it, and a missing soil sensor is never reported as a fault — the
model-only path is the shipping path, and a warning that fires on every plant
every day is a warning nobody reads on the day it means something.

## Secrets

- `.env.example` documents variable names only; no value for any of them is in
  this branch, and none was looked for.
- `MOH_HA_TOKEN` and `MOH_MQTT_PASSWORD` are `SecretStr`, so neither survives a
  `repr()`, a log line or a traceback. The token is read in exactly one place,
  `HomeAssistantFetcher._headers`, and in one WebSocket frame.
- `health.redact()` scrubs anything credential-shaped on the way **into**
  `integration.last_error`, because that column is rendered in the UI and an
  httpx error quotes the URL it dialled — which a misconfigured deployment can
  have put credentials in.
- `mqtt.guard()` refuses to publish a payload carrying a token, an API key or a
  tokenised feed URL. It is a check rather than a comment because a broker
  retains a message until something replaces it: a token published once sits
  there until somebody notices. The task attributes are an allow-list for the
  same reason.

## Mocks: there are no recordings, and that is the honest state

E could record NWS and Open-Meteo because both answer an anonymous request.
Home Assistant answers nobody — it is somebody's house, behind a token, with no
public instance to record from. This branch has no HA payload and did not go
looking for one: recording a stranger's exposed hub would have produced a file
with their room names in it.

So `workers/hub/mocks/fetcher.py` **synthesises** responses in HA's documented
`/api/states` shape from `fixtures/locations/locations.json`, stamps every one
`_synthetic`, and `recorded/PROVENANCE.md` says all of this. `record.py` fills
`recorded/` from a real instance the day somebody runs it against their own,
and the fetcher prefers a real recording the moment one exists.

## For A — five things, none of them worked around

1. **`fixtures/` has no `sensor_source` rows.** Everything else this adapter
   needs is frozen and shared; its own mapping table is not, so `world.py`
   derives one climate source per indoor location and labels it synthetic. A
   `fixtures/sensors/sensor_sources.json` — two indoor rooms, and one disabled
   soil probe bound to a specimen so ADR 0010's path has a fixture rather than
   only unit tests — would replace the derivation entirely. Fixtures are L's
   and A's, so this is a request.
2. **`integration` has no unique constraint on `(kind, name)`.** "Record that
   Home Assistant answered" therefore cannot be an upsert without knowing the
   row's id, and a select-then-insert is two rows for one hub the first time two
   workers start together. `store.integration_id_for` derives a stable UUIDv5
   from the kind and name as a stand-in. A unique index would let the database
   enforce what that can only promise.
3. **`reading` has no unique index either.** It matters less than it did for
   `weather_obs`, because rows are written at the poll's own timestamp and
   `reading_hourly` averages rather than sums — a duplicate skews nothing.
   A unique index on `(source_id, metric, time)` would still be worth having.
4. **The contract's `Integration` schema has no `status`.** The Ministry Office
   needs the five-way distinction `health.py` computes — `ok`, `degraded`,
   `down`, `stale`, `unconfigured` — and `last_ok_at` plus `last_error` alone
   cannot express *stale*, which is exactly the silent case. Additive; rule 1
   says F does not add it.
5. **`SensorSource` in the contract types `external_ids` as
   `{string: string}`** with no statement of what the keys mean. This adapter
   reads them as metric names from `reading.metric`. That convention is now
   load-bearing across F, C and J and deserves a line in the spec.

## For A and B — two dependencies F does not own

- **An async MQTT client.** `api/pyproject.toml` carries none, so
  `mqtt.connect_publisher` raises with a message naming what is missing rather
  than quietly no-opping. Every topic, payload and discovery config is complete
  and tested against `MemoryPublisher`; `aiomqtt` and a ~40-line transport is
  the whole remainder. `test_hub_mqtt.py` asserts no client is installed, so
  the day one lands that test goes red on purpose.
- **A WebSocket client**, same story, smaller stakes: REST polling meets the
  exit criterion on its own and keeps working through a hub restart. The
  WebSocket is the optimisation that would serve a probe reporting once an hour
  at an unknown minute.

## For B — a note on the test suite

`workers/hub/tests/` is a package and every module is named `test_hub_*`, so a
basename cannot collide with another workstream's. The autouse fixture blocks
the httpx transport **and** the socket layer, copied from E because it is the
right pattern — and it matters more here: every request this worker makes
carries a long-lived access token, so a test that accidentally dialled a real
address would send it there.
