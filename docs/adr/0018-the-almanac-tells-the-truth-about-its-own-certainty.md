# 18. The Almanac's responses carry their own certainty

Date: 2026-09-23

## Status

Proposed. The decisions below are made; the contract edits that implement them
are **not yet applied** — see *Applying this* at the end.

## Context

Workstream E delivered S3 (PR #16, merged) and escalated five contract gaps
rather than working around them, which is what rule 1 asks for and is the
reason this ADR exists.

The engine E built decides whether an outdoor plant is watered. ADR 0010 says
nothing measures the soil and nothing is planned for v1, so there is no second
opinion. E named the failure mode exactly: **the worst outcome is not being
wrong, it is failing closed and looking healthy.** If ET₀ stops arriving the
deficit stops advancing, every plant reads as comfortable, the app goes quiet,
and a quiet app is indistinguishable from a garden that needs nothing.

E's engines therefore carry a confidence and the named reasons for it. The
frozen contract has nowhere to put any of it. A response that drops those
fields is a degraded answer wearing a clean one's clothes — which is the same
defect rule 6 and ADR 0004 forbid for care values, arriving through a different
door.

## Decision

### 1. `WaterBalance` and `FrostAlert` carry their certainty — required, not optional

Both gain `confidence`, `degraded` and `degradations[]`, and those three are
**required**. Optional would defeat the purpose: a client that omits them
cannot be distinguished from an answer that had nothing to declare.

A new `Degradation` schema — `{code, detail, caps_at}` — matches what E
already emits. `caps_at` is the best confidence still honest while that reason
holds; it is a ceiling rather than a subtraction, because two doubts about one
input do not make it twice as doubtful.

`WaterBalance` also gains the fields E computes and had to drop: `k_c_confidence`,
`k_c_source`, `k_c_is_category_default` (ADR 0013 — a category default is not a
measurement), `status`, `satisfied_by`, `cover_factor`, `applies`, `note`, and
per day `reference_et0_mm`, `et0_method`, `gross_precip_mm`, `is_forecast`,
`status`, `satisfied_by`.

`et0_method: unavailable` is the one that matters most: a missing day does not
advance the deficit, is counted, and is declared.

### 2. `/almanac/frost` returns an envelope

From a bare array to `FrostReport` — `{alerts[], unassessable[]}`. A list of
alerts cannot say "and these three I could not judge". E already computes the
second list in `service.unassessable_for_frost()` and cannot serve it.

This is a **breaking response-shape change** and is made now precisely because
it is still free: J has not built the Almanac screen yet. `web/src/lib/api/client.ts`
and `web/src/routes/specimen/[id]/api.ts` type the response as `FrostAlert[]`
and change with it.

### 3. An NWS advisory corroborates; it does not, yet, trigger

The plan says alert when the low crosses the threshold **or** an advisory
covers the site. The contract test `test_a_frost_alert_reports_the_night_it_actually_names`
requires every alert's stated low to sit at or below its own stated threshold,
which an advisory-only alert cannot satisfy. E implemented advisory as
corroboration — it extends the lookahead and raises confidence — and asked A to
decide.

**The invariant stands for now: E's implementation is accepted as shipped.** An
alert that shows a low of 3 °C against a threshold of 2 °C teaches the reader to
distrust every alert after it, and legibility is worth more than coverage in the
common case.

**This is not free and should not be recorded as if it were.** NWS issues
advisories for conditions a gridpoint low misses — cold-air pooling in a hollow,
a clear calm night over damp ground. Under this decision the app stays silent on
exactly those nights, and the cost of that silence is a dead plant rather than a
confusing alert. It is a real gap, deliberately accepted for v1, and S4 should
close it by making the trigger explicit on the alert (`forecast | advisory |
both`) and scoping the test's invariant to forecast-triggered alerts. Raised
with the maintainer rather than buried here.

### 4. `weather_obs` gets a unique index on `(site_id, time)`

`weather_daily` sums `precip_mm` without `source` in its grouping, so two rows
for one hour double the day's rain, clear a deficit nothing cleared, and leave a
plant unwatered. E's writes replace their whole window to prevent it; a
constraint lets the database enforce what one module can only promise.

Unique on `(site_id, time)` rather than `(site_id, time, source)`: `weather_obs`
is the site's observed weather, not every source's opinion of it, and `source`
records which one won. Storing disagreeing sources for one hour is a real
feature, but it is not a v1 need and it would make the aggregate pick a winner
per row. Forward-only migration `003`.

`weather_forecast` has the same shape of risk and is **not** changed here. E did
not raise it, its writes may legitimately re-issue, and imposing a constraint on
code A has not read is how a migration breaks an ingest at runtime. Raised as a
question for E in S4 instead.

### 5. Hargreaves stays local; `climate_indices` is not added

ADR 0016 named `climate_indices`. E implemented FAO-56 Hargreaves as one pure
function with the equations written out, which is the whole of what was needed.
**ADR 0016 is amended: the library is optional, not required.** A self-hosted,
offline-first app earns more from one fewer dependency than from importing a
package for a single published formula, and the function is the seam the library
plugs into if that ever changes.

### 6. Black's line length is 88, and says so

`api/pyproject.toml` and `CLAUDE.md` said 100. CI runs `black --check` from the
repository root, where black finds no configuration and uses its default of 88,
and the tree has been formatted at 88 since S0. A contributor running `black`
inside `api/` picked up 100 and produced files CI rejected.

The number matters less than the agreement, and 88 is what the code already is.
`api/pyproject.toml` and `CLAUDE.md` move to 88; **no file is reformatted**.
Ruff stays at 100, deliberately: black cannot split a long comment or string
literal, and failing the lint on lines black itself will not fix helps nobody.

Moving the tree to 100 is a sprint-boundary job — a mechanical reformat while
four workstreams hold branches collides with every one of them.

### 7. The site's NWS zone is wrong and is corrected

`fixtures/site.json` gives `nws_zone: INZ050`, which is Wayne County. The site's
own coordinates resolve to `INZ047`, Marion County; the NWS `/points` payload E
recorded says so first-hand. An advisory fetched for the wrong county is an
advisory about somebody else's frost.

The fixture is corrected to `INZ047`. E's test asserting the discrepancy becomes
a test asserting the agreement — the recorded payload stays as the evidence.

## Consequences

`contracts/VERSION` goes to **1.2.0**: additive on `WaterBalance` and
`FrostAlert`, breaking on `/almanac/frost`.

E's `api/almanac/router.py` serves the envelope; `api/almanac/tests/`,
`tests/contract/test_mock_stack.py`, `web/src/lib/api/client.ts` and
`web/src/routes/specimen/[id]/api.ts` follow the shape. A makes those edits with
the contract change, in one commit, so main is never left with a spec and a
server that disagree.

**J builds the Almanac against 1.2.0.** The 1-day and 10-day views read
`/almanac/forecast` and `/almanac/history` and are unaffected; anything reading
`/almanac/frost` waits for this to land.

**Workstream L** gains a scenario worth having: every outdoor specimen in the
fixtures has a cited `water_k_c` today, so the fixtures never exercise the
uncited path — the exact path ADR 0004's warning exists for. Unit tests cover it;
a scenario would cover it end to end.

## Applying this

The contract edits are **not in this commit**. Writing to `contracts/` was
declined by this session's tooling as a shared-resource change, and A did not
route around it. What is written here is the decision; the edits to
`contracts/openapi/openapi.yaml`, `contracts/VERSION` and a new
`contracts/schema/003_*.sql`, plus the implementation and test changes that must
land in the same commit, need the maintainer's go-ahead.

Until then the served `/almanac/frost` and the spec agree — on the old shape —
so main stays green and nothing is half-applied.

## References

- PR #16 — E's S3, where all five gaps were escalated
- `docs/sprints/S3-workstream-e.md` — E's write-up
- ADR 0004 — citations and confidence; ADR 0010 — no hardware today;
  ADR 0013 — category defaults; ADR 0016 — ET₀ fallback (amended by §5 above)
