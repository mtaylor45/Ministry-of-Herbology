# S4 — Workstream G: Scheduling and Rules

`api/tending/` was the S0 mock — one `router.py` serving fixtures — and is now a
working scheduler behind the five frozen endpoints, in both mock and live mode.

Sprint exit criterion: *daily care runs from the app, and tasks appear in the
calendar.*

## What landed

1. **Care rules → tasks.** Rules resolve per specimen (a specimen rule beats a
   species rule for the same job), and occurrences are generated for a 30-day
   horizon on read.
2. **Recurrences with season and dormancy modifiers.** Seasons are the *site's*,
   by latitude, not the server's. Dormancy suspends watering rather than
   stretching it, and a plant that is off the schedule for that reason is named
   rather than silently absent.
3. **Completion logging.** One-tap and the batch path Morning Rounds needs,
   through one code path so they cannot diverge. Every completion writes a
   `task_event` — the history is the point.
4. **ICS feeds** with filters, deep links, all-day routine events, timed frost
   events with an alarm, and per-feed revocable tokens.

## The decision that mattered most

**A task's identity is its occurrence, not its due date.** The id, and therefore
the `ics_uid`, is a pure function of the nth cycle since the job was last
actually done. A watering stretched by a winter modifier keeps its UID, bumps
`SEQUENCE`, and moves the event a subscriber already has.

The S0 mock keyed the UID on the due date. That is stable exactly until
something reschedules, and then each reschedule is a permanent extra event in
someone's calendar with no way to withdraw the first. The brief flagged this as
the thing to get right before anything else, and it was right: nothing else in
this sprint would have been hard to change afterwards, and this would have been
impossible.

Completion moves the anchor, which retires the cycle counted from the old one.
Those occurrences are cancelled rather than deleted, because a subscribed feed
can only say "this is gone" by saying it.

## Escalations for Workstream A

Five, none worked around further than stated. Rule 1: nothing under
`contracts/` was edited.

### 1. `Task` needs the three certainty fields ADR 0018 gave `WaterBalance`

ADR 0018's reasoning was that an answer built on a degraded input must not
arrive looking like a clean one. A task generated from that same water balance
is the next link in the chain, and the chain currently ends at the API boundary.

Requested, additive: `confidence`, `degraded`, `degradations[]` on `Task`, with
the existing `Degradation` schema. They are served today (additive, so a 1.2.0
client is unaffected) and the plain-language version also goes on `detail`,
which is in the contract, so the caveat is visible to a client that reads
neither.

### 2. `task` has no columns to keep that certainty in

The frozen `task` table has `detail` and nothing else. Generation runs on every
read, so the values are recomputed and merged onto the rows before serialising —
which works, and is the wrong place for it. A completed task is never
regenerated, so its confidence is simply not recoverable; `detail` survives and
is the only reason the caveat does.

Requested: `confidence text`, `degraded boolean`, `degradations jsonb` on
`task`, forward-only.

### 3. `MorningRounds` needs an `unscheduled[]`, for the same reason `/almanac/frost` got an envelope

ADR 0018 §2: *"a list of alerts cannot say 'and these three I could not
judge'"*. Morning Rounds has the same shape of hole. A plant with no watering
interval anywhere — no cited care value, no species column, no household rule —
gets no task, and a plant with no task is indistinguishable from a plant that
needs nothing.

It is served today as `unscheduled: [{specimen_id, reason}]`, matching
`FrostReport.unassessable`. Requested as a contract addition so J can build
against it.

### 4. `water_balance` stores a deficit but not its confidence — for E and A

ADR 0018 put `confidence`, `degraded` and `degradations[]` on E's *response*.
The table behind it was not given the same columns, so in live mode this package
reads a deficit and a threshold and cannot see any of the reasoning that ADR
exists to preserve. It reports a modelled deficit at `medium` — which is what
`workers/weather/quality.py` itself calls a modelled figure worth — and adds the
staleness it can verify from the row's own date.

That is the most honest thing available and it is not good enough: the live path
is quieter about its own uncertainty than the mock path, which is the wrong way
round. The fix is columns on `water_balance`, or E's engine exposed to the API
as a function rather than as a table. Raised rather than guessed at.

### 5. The calendar token is written to two access logs — for B, and an ADR 0019 addendum

`GET /api/v1/calendar/{token}.ics` puts the credential in the request path. This
package never logs it, imports no logger and calls no `print` (there is a test).
But uvicorn's access log and the deployment's nginx log both record request
paths by default, so the one credential the application issues is written to
disk in plaintext on every fetch, by two components neither of which is G's.

Moving the token out of the URL is not available — Google's and Apple's fetchers
carry no session, which is why it is there. The fix is redaction in B's nginx
`log_format` and in the API's logging configuration, for `/api/v1/calendar/*`.
ADR 0019 wrote the credential rules down for the operator; this is the gap
between what it says and what the stack does.

## Not taken, deliberately

- **A scheduled generation job.** The natural home is an Arq worker, and
  `workers/` is not G's. Generation therefore runs on read, idempotently. The
  seam is `service.generate_tasks`: a worker calls the same function and these
  endpoints become pure reads, with no other change. Assigning that job is A's.
- **"Satisfied by rain" is S5.** E's state is consumed where it exists — a
  satisfied watering shows as satisfied and its calendar event is cancelled by
  UID — but nothing here computes it. The baseline weather fixture has no rain
  on its closing days, so the mock stack currently shows an empty `satisfied`
  list; the path is covered by unit tests. A fixture with rain in the last day
  or two would make it visible in the demo (Workstream L).
- **Bring-indoors and the relocation flow are S6.** A `new_location_id` sent
  with a completion is recorded on the task event so the history is not lost;
  the specimen is not moved, because that write is C's.
- **ADR 0018 §3's advisory-trigger gap is untouched.** It asked S4 to add an
  explicit `trigger` to `FrostAlert`. Frost *tasks* are S6 and the alert shape
  is E's; flagged here only so it is not assumed closed.

## Verified

- `.venv/bin/pytest tests/contract -q` — 48 passed
- `.venv/bin/pytest tests api workers scripts -q` — 751 passed, 37 skipped
- `.venv/bin/pytest api/tending -q` — 84 passed, 12 skipped (the live-Postgres
  suite, which needs `MOH_TEST_DATABASE_URL`)
- `ruff`, `black` (88), `mypy api/tending` clean

`tests/contract/test_api_matches_spec.py` loses the five `S4 (G)` entries from
`NOT_YET_IMPLEMENTED`; that file is `ALWAYS_ALLOWED` precisely so the workstream
that implements a path strikes its own entry.
