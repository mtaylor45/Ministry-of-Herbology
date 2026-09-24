# Scheduling & Rules — Workstream G

Care rules, tasks, recurrence, completion logging and the tokenized ICS feeds.
Implements the `tending` paths of `contracts/openapi/openapi.yaml`; the contract
is frozen, so nothing here changes a response shape.

## Layout

| Module | What it does |
| --- | --- |
| `router.py` | HTTP only. Validates, delegates, serialises. |
| `service.py` | Generation on read, Morning Rounds, completion, feed rendering. |
| `domain.py` | The engine, pure: occurrences, identity, modifiers, seasons. |
| `defaults.py` | The care rules a fresh install gets, and what they are worth. |
| `titles.py` | Rule 7 in one place: themed title and plain title, always paired. |
| `ics.py` | RFC 5545, via `icalendar`. |
| `tokens.py` | The one credential this application issues. |
| `environment.py` | The single seam onto Workstream E. |
| `repository.py` | The storage protocol, and which implementation answers. |
| `fixture_repository.py` | In-memory schedule seeded from `fixtures/` — mock mode. |
| `database_repository.py` | SQLAlchemy Core on Postgres — live mode. |
| `tables.py` | Core table metadata mirroring `contracts/schema/001_init.sql`. |
| `db.py` | The engine, borrowed from Workstream C rather than duplicated. |

## The rules this code exists to keep

### A task's identity is its occurrence, never its due date

This is the one to read first, because it is the one that cannot be retrofitted.

A task id — and therefore its `ics_uid` — is a pure function of the *occurrence*
a rule generates: the nth cycle since the last time the job was actually done.
It does not contain the due date. Stretch a watering by four days for winter and
it is the same occurrence on a later day: same UID, `SEQUENCE` bumped, and the
subscriber's calendar moves the event it already has.

The S0 mock keyed the UID on the due date, which is stable right up until
something reschedules — and then every reschedule is a second event in
somebody's calendar, permanently, with no way to withdraw the first.

Completion moves the anchor. That retires the whole cycle counted from the old
one: those occurrences are now fiction, so they are marked `cancelled` rather
than deleted, because a subscribed feed can only say "this is gone" by saying
it. New cycles get new identities, which is correct — they are new jobs.

### Rule 7 is a `NOT NULL` pair, not a style note

`title` and `plain_title` are both `NOT NULL` in the frozen schema. Everything
goes through `titles.titles_for`, so there is no code path that can produce one
without the other. A calendar SUMMARY reads `Tend Gilderoy — water 450 ml`: the
themed phrase names the plant, the plain half says what to do, and a person
reading their work calendar at seven in the morning gets an instruction rather
than a puzzle. The full plain title leads the event body.

### Nothing here invents a plant fact

Only modifiers a rule actually carries are applied. There is no ambient table of
"what plants like in winter" in this package and there must not be one — a
multiplier nobody configured is a care value nobody cited, wearing arithmetic.

The rules a fresh install gets are derived strictly from what Workstream D has
attested:

| What D has | What this package does |
| --- | --- |
| A cited interval | A rule at that citation's confidence |
| An uncited interval | A rule at `unknown`, and every task it generates carries the reason in `detail` (ADR 0004) |
| A per-specimen override | The household's own instruction, which outranks the species |
| No interval at all | **No rule**, and the plant is named in the rounds' `unscheduled` list with the reason |

That last row matters. A plant that silently drops off the schedule looks
exactly like a plant that needs nothing, which is the failure ADR 0018 spends
two pages naming in the weather engines. It arrives here through the door marked
"sensible default", and is refused at it.

Ten of the twelve fixture species carry an uncited watering interval, so the
marked path is the common one, not the edge case.

### Certainty is carried through, never laundered

Workstream E's water balance returns `confidence`, `degraded` and
`degradations[]` (ADR 0018). A task generated from it carries all three, plus
this package's own caveat when the balance series ends before the day it is
being used to schedule. The plain-language version goes on `detail`, which is in
the frozen contract, so a client that knows nothing about the structured fields
still shows the reader that the instruction is a guess.

Under ADR 0010 nothing measures the soil, so where E's model has an opinion it
is the *only* authority: an outdoor plant the balance calls comfortable does not
also get an interval watering behind the model's back. The interval is the
fallback for plants the model declines to judge, and nothing else.

### The feed token is a credential

It is the only one this application issues (ADR 0019). Minted from `secrets`,
one per feed, never logged — this package imports no logger and calls no
`print`, and a test asserts it — compared in constant time, and rotated as well
as flagged on revoke, so a revoked URL stops resolving rather than merely being
marked. A revoked feed publishes no URL at all. An unknown token and a revoked
one get the same 404: distinguishing them tells an unauthenticated caller that a
token they hold was once real.

## Two modes, one protocol

`MOH_MOCK_MODE=true` (the default, ADR 0003) serves the whole API from
`fixtures/`, writes included — completion, feed creation and revocation all work
there, because the S4 exit criterion is demonstrated on the mock stack before it
is demonstrated on a deployment. Mock-mode writes live in the process; restart
the API and the schedule regenerates from the fixtures.

Set it false with `MOH_DATABASE_URL` and the same router talks to Postgres,
which is what `infra/stack/docker-stack.yml` does.

## Generation runs on read

Every endpoint that needs today's schedule materialises it first. Because every
task id is a pure function of its occurrence, running it twice writes nothing
the first run did not.

**This is a deliberate shape, and it has a cost worth stating.** The natural
home for a nightly rule evaluation is an Arq job, and `workers/` belongs to
another workstream — reaching in would break rule 2, so the scheduled job is
escalated rather than smuggled. Morning Rounds therefore does the generation
work on the request. That is fine for one household's dozen plants and would not
be fine for a thousand. The seam is `service.generate_tasks`: a worker calls the
same function on a schedule and these endpoints become pure reads, with no other
change.

## What is not here

- **"Satisfied by rain" is Sprint 5's**, with E. The state is *consumed* — when
  E's balance says a watering was satisfied, the task says so and the calendar
  cancels the event — but nothing in this package computes it. The baseline
  weather fixture has no rain on its closing days, so the mock stack currently
  shows an empty `satisfied` list; the path is covered by unit tests rather than
  by the fixture.
- **Future outdoor waterings are not projected.** Working out which day a
  deficit will next cross its threshold is E's engine. A `water_balance` rule
  produces the single outstanding watering, held at one identity for as long as
  it goes undone. Indoor interval rules fill the calendar's horizon.
- **Bring-indoors and the relocation flow are Sprint 6's**, with J. A
  `new_location_id` sent with a completion is recorded on the task event now, so
  the history is not lost in between, but the specimen is not moved — that write
  is Workstream C's.

## Tests

They live in `tests/` inside this package, because rule 2 puts the repository's
top-level `tests/` in Workstream L's hands.

```
.venv/bin/pytest api/tending -q              # no database, no network
```

The suite is network-free by construction: an autouse fixture fails any test
that opens a socket.

The live-Postgres suite skips unless it is given a database it may create tables
in:

```
MOH_TEST_DATABASE_URL=postgresql+asyncpg://herbology@127.0.0.1:5432/herbology_test \
  .venv/bin/pytest api/tending -q
```

It cuts its tables out of `contracts/schema/001_init.sql` rather than retyping
them, so a column that moves in the frozen schema breaks the tests instead of
quietly passing them.
