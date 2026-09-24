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

## Not done

Nothing in the brief was left unfinished. The soil-sensor override remains a
seam with no hardware behind it (ADR 0010) and is F's after this.
