# S5 — Smart Watering (Workstream E)

Appended by E ahead of the demo. A owns the sprint's own summary.

## Exit criterion

> Scenario suite passes; rain visibly clears due waterings.

**E's half is met.** With the deployment put under the `storm` recording,
`GET /api/v1/tending/rounds` returns two settled waterings where `main` returned
an empty list, each attributed to rain, each keeping its place on the round
rather than vanishing. The scenario suite itself is L's and runs in parallel;
the switch it drives is described below and is stable.

## What was actually broken, and what was not

The engine was not broken. Replayed directly, it already marked the storm's rain
day `satisfied` with `satisfied_by: "rain"`, exactly as
`fixtures/scenarios/storm.json` expects, and G's `api/tending/domain.py` already
turned that into a task that keeps its place. All four links were sound.

What was missing is that **the running app could not be put under a scenario**.
`world.weather_days` took a `scenario=` argument and every caller in the app
left it out, so the API and the worker were permanently on
`weather/baseline_30d.json` — whose closing fortnight has no downpour big enough
to clear anybody's deficit. Four working links and nothing to see.

That is the class of defect no unit test catches, which is why the proof added
here (`api/almanac/tests/test_almanac_scenario_end_to_end.py`) goes over HTTP
through the whole chain rather than over four seams separately.

## The scenario selector — for L, and for anyone running the demo

Two operator inputs on `WeatherSettings`, ADR 0019 style: a parameter with no
usable default, unset in every shipped deployment, opt-in.

| Variable | Meaning | Default |
| --- | --- | --- |
| `MOH_WEATHER_SCENARIO` | A file in `fixtures/scenarios/`, without the extension: `drought`, `storm`, `frost` | unset — the baseline recording |
| `MOH_WEATHER_SCENARIO_DAY` | Which day of that recording is "today" | unset — the recording's last day |

```
MOH_WEATHER_SCENARIO=storm MOH_WEATHER_SCENARIO_DAY=2026-07-07 <run the api / the worker>
```

These names are stable. L's end-to-end suite may depend on them.

Three things worth knowing about them:

- **Both processes read one setting**, resolved in one place
  (`world.active_scenario`). If the Almanac resolved the scenario and the worker
  did not, a deployment would serve a balance cleared by rain out of one process
  while the other wrote rows that never saw it, and the disagreement would
  surface as a task that reappears overnight.
- **The day matters.** `storm` runs three days past its downpour. Replayed
  whole, the deficit has already rebuilt and the series honestly reports `ok` —
  the right answer to a question nobody asked. The balance is a history that
  ends *now*, so "now" has to be sayable. A rain-bearing fixture that ends on
  its rain day needs no second variable; `storm` as frozen does.
- **It is not a test hook.** An operator who wants to watch 38 mm of rain clear
  a due watering before trusting the app with their garden takes this exact
  path. A private route for the suite would prove only that the private route
  works.

Selecting a scenario moves the whole Almanac, not just the balance: forecast,
history and the frost guard follow it too, so one deployment describes one week
of weather. With nothing selected, the frost guard stays on `frost` where it has
been since S3 — the baseline is a mild fortnight in May and a frost endpoint
that answers "nothing, ever" mocks nothing.

Two guard rails, both for the same reason: under ADR 0010 a quiet app is
indistinguishable from a garden that needs nothing, so a misconfiguration may
never be able to produce one.

- A **typo'd scenario name** raises, listing the recordings that do exist,
  rather than serving an Almanac with no days in it.
- A **day outside the selected recording** raises too. It would select no
  weather, an empty series advances no deficit, and every plant would read as
  comfortable.

The frost lookahead is deliberately *not* cut off at the selected day, and this
is the one asymmetry in the switch worth knowing about. The balance is a history
and ends at today; the guard is a 72-hour lookahead and is about the nights
still ahead of the reader. Truncating it would leave a deployment standing two
nights before a freeze reporting no freeze, and the cost of that silence is a
dead plant rather than a stale number. There is a test for it.

The frost guard's lookahead is still anchored at the first night of the
recording rather than at the selected day. That is S6's business and is left
alone here.

## ADR 0020 §4 — the certainty now reaches the table

`serialise_balance` has computed `confidence`, `degraded` and `degradations`
honestly since S3; the database path wrote none of them, so a deployment on
Postgres served a number stripped of the doubt the fixture-backed one carried.
The live path quieter about its own uncertainty than the mock — backwards, and
the same shape as every other defect this project has had.

Written now, by `store.water_balance_row` into the columns migration 004 added,
and read back by `almanac.service.balance_from_rows`. Two details:

- A row whose `confidence` is NULL reads as **`unknown`**, with a named reason
  (`certainty_not_recorded`), never as `medium`. The ADR is explicit: an empty
  column means *it did not say*, not *it was certain*.
- A row older than today carries `ingest_stale`. The deficit has not advanced
  since it was computed, so the real figure is higher than the stored one, and
  under ADR 0010 nothing else would ever notice.

## Raised with A rather than worked around

1. **`water_balance` cannot store `status` or `satisfied_by`.** So in *live*
   mode "satisfied by rain" cannot reach G at all: `api/tending/environment.py`
   reads the table directly and can only ever derive `due`/`ok` from the
   deficit. E's own live read replays `tasks.day_status` over consecutive stored
   rows and recovers it for the endpoint, but G reads rows, not the endpoint.
   The honest fix is two columns and a line in G, not a third derivation.
2. **`api/tending/environment.py:from_balance_row` still reports a flat
   `medium`.** Its own docstring says it cannot pass through what it cannot
   read. It can now: the columns are written. That is a one-line change in G's
   package, and G is not running this sprint.
3. **Per-day provenance is still unstored** — `et0_method`, `reference_et0_mm`,
   `gross_precip_mm`, `is_forecast`. The live read omits them rather than
   filling in a plausible value, since none is required by the contract and a
   `hargreaves` nobody recorded is an invented fact about provenance.
4. **`.env.example` and `docs/deploy/` are B's.** The two variables above want a
   line in each; E cannot write either.

## Contract 1.4.0, folded in after the merge

A landed 1.4.0 and ADR 0021 mid-sprint. Two pieces were in `api/almanac/`:

- **`UnassessableSpecimen.specimen`** (§1) is now populated on the `unassessable`
  half of `/almanac/frost`. It is built from the `world.SpecimenContext` that
  produced the verdict rather than from a second lookup in `fixtures`: a plant
  that could not be assessed must not then fail to appear because the lookup for
  its *name* missed. `frost()` was changed the same way for the same reason — it
  dropped an alert whose specimen row it could not find, which under ADR 0010
  means a plant freezes because a name could not be resolved.
- **`CareValue.source` nullable** (§8) needed no change in the balance path.
  `WaterCoefficient.from_care_value` already handled a missing source rather
  than coercing one, and E serves no `CareValue`.

  It did, however, turn up the same defect §1 fixes, one layer down in E's own
  code: a `source_id` that resolved to no row fell back to the **raw uuid** as
  the citation, so `k_c_source` showed a reader a uuid *and* the value read as
  cited, keeping whatever confidence it claimed. Rule 6 is the other way round.
  An unresolved citation is now no citation: `source: None`, `confidence:
  unknown`, `k_c_uncited` on the answer. A user override is the stated exception
  and keeps its confidence.

**And A's point about how those four were found is now acted on.** Nothing in
this repository validated a response body against the frozen schemas, which is
how every task the API served could violate the contract since 1.0.0 with the
unit tests green. `api/almanac/tests/test_almanac_response_schemas.py` validates
all four Almanac responses against the frozen document — under the baseline *and*
under a scenario, since a scenario is a different route through the same
serialisers. It reports every violation rather than the first, and one test
proves the validator bites (five deliberate breaches of a real response, all
caught, including a uuid-format one). `Task`'s new conditional requirement of
`satisfied_by` is held at the far end of the chain by the end-to-end test.

## Not done

Nothing in the brief was left unfinished. The soil-sensor override remains a
seam with no hardware behind it (ADR 0010) and is F's after this.

## After the merge: L's suite, and two bugs it found

#29 and #32 merged, and L's #30 landed in parallel. The combination was red, and
what it exposed was worth more than the two PRs' own test suites.

### The selector was named twice

L wrote `tests/e2e/test_scenario_selector_stories.py` against
`WeatherSettings.scenario` / `MOH_SCENARIO` and skipped it until the field
existed, saying plainly that if E chose another name it was a one-line change on
L's side. E shipped `weather_scenario` / `MOH_WEATHER_SCENARIO`. So five
end-to-end tests of **the sprint's own exit criterion** sat skipped while both
halves were merged and green.

**The field is now `scenario`**, and L is right on the merits: `MOH_` already
scopes the variable and no other field on `WeatherSettings` carries a `weather_`
prefix. `MOH_WEATHER_SCENARIO` and `MOH_WEATHER_SCENARIO_DAY` keep working as
aliases, because a merged pull request documented them and an operator may have
them in a `.env` — they are not the name and are not written down again.

Worth recording as a process point rather than a naming quibble: two workstreams
each shipped a correct, tested, reviewed half, and the seam between them was
untested by construction, because L's test for it *skipped itself* rather than
failing. A skip is invisible in a green run.

### `BALANCE_DAYS` was truncating the deficit, not the screen

`BALANCE_DAYS = 14` is documented as how much the endpoint *shows*. It was also
what the endpoint *replayed*, which silently restarts the deficit at zero a
fortnight ago. Nobody noticed because every recording was under 14 days until
L's drought story ran the selector over a 21-day one:

| | endpoint (14 days) | worker (whole recording) |
| --- | --- | --- |
| lavender hedge, in ground, 60 mm profile | 34.02 mm — `ok` | 51.03 mm — `due` |

The fixture says due by day 15 and the weather agrees. A deficit is what the
weather did, not what the last fortnight of it did, so the replay now covers
everything available and only the per-day array is trimmed. `deficit_mm`,
`status` and the confidence all come from the full replay.

This also falsifies something #29's body claimed a bit too broadly. The endpoint
and the worker were shown to agree on *which recording*; they were never compared
on *how much of it*, and they disagreed.

### The forecast window, raised rather than changed

Under an eleven-day recording the ten-day forecast (`days[:10]`, since S3) stops
one day short of the day the balance is standing on. Setting `MOH_SCENARIO_DAY`
anchors both together; with no day set they disagree about where "now" is. That
is S3's shape rather than this switch's and is left alone deliberately — flagged
for A.

## Still open: the irrigation term (L's xfail, escalated to A for E)

`tests/e2e/test_a_dry_spell_keeps_waterings_due.py::test_completing_the_watering_takes_it_off_the_round`
is xfail, and it is a bad bug: complete a watering and the app immediately asks
again under a new task id, putting a second VEVENT in every subscribed calendar.
`run_balance` takes an `irrigation` mapping and the plan's equation has its I(t)
term; `almanac.service.water_balance` calls it without one.

**Not fixed here, and not for want of trying to keep it small.** Two decisions
sit in it that are not E's alone:

1. **Where the waterings come from.** The completion log is `api/tending/`'s.
   E reading it inverts the existing G→E dependency into a cycle. The clean seam
   is `water_balance(..., irrigation=...)` with G passing what it already knows
   — one line in `api/tending/environment.py:fixture_environments`, which is G's
   file and G is not running.
2. **How millilitres become millimetres.** A completion logs `amount_ml`. Turning
   500 ml on a 25 L pot into millimetres of relieved deficit is the inverse of
   `tasks.capacity_mm`, and picking a factor quietly is exactly the kind of
   invented number rule 6 exists to stop. It wants an ADR line, not a constant
   chosen by whoever got there first.

Raised for A with both halves named rather than half-built.

## A note on fixture-shaped tests, after the second re-cut

`storm` was re-cut twice inside this sprint — the downpour on the closing day in
one shape, mid-series with trailing dry days in another. Both are defensible and
both are L's call over L's file.

E's tests now depend on **neither**. The rain day is found in the recording, and
the storm story stands on it by setting `MOH_SCENARIO_DAY` explicitly rather than
relying on where it happens to sit; setting it is a no-op when the recording ends
there and the whole point when it does not. Verified by running E's suites against
both shapes: 229 passed either way.

The only property still asserted about the fixture is that it has a *single*
downpour, because "the rain day" would otherwise be ambiguous — and that assertion
fails with a sentence rather than as `0.0 == 38.0`.
