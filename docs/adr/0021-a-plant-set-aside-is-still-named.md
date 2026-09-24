# 0021 — A plant set aside is still named, and a worker is still somebody

- **Status:** Accepted
- **Date:** 2026-09-24
- **Workstream:** A (Architect), answering J's three and F's five from S4
- **Supersedes nothing. Extends ADR 0018 and ADR 0020.**

## Context

S4 shipped the scheduler (G, #24), Morning Rounds (J, #26) and Home Assistant
notifications (F, #27). Contract 1.3.0 landed mid-sprint and carried ADR 0020:
`confidence`, `degraded` and `degradations[]` reach the instruction, and
`MorningRounds.unscheduled[]` names the plants nothing was scheduled for.

Building the two consumers of that contract found eight things wrong with it.
Three are J's, five are F's, two of F's are S3 escalations restated because S4
gave them a second consumer. None was worked around: both workstreams stated
the gap, handled its absence honestly, and left it for this ADR. That is rule 1
working as intended, and the eight are answered here together because six of
them are the same mistake in different places — **a value that the API knows
and does not say, leaving every consumer to guess or to go and ask again**.

## Decisions

### 1. An unassessable plant carries a name, not just an id (J's 2)

`UnassessableSpecimen` — served by `/almanac/frost` as `unassessable[]` and by
`/tending/rounds` as `unscheduled[]` — carries a bare `specimen_id`. To put a
name beside the reason, J's Morning Rounds must also read `GET /specimens`: an
extra request on the home screen, and when it fails the one panel whose purpose
is to *name* the plants nobody can judge can only print uuids. A panel that
exists to say "and these three I could not judge" degrades to "and these three
uuids I could not judge", which is worse than silence because it looks like a
fault in the app rather than a question for the reader.

`Task` already solved this: it carries `specimen: SpecimenBrief`. The sibling
schema should not have a different answer to the same question.

**`UnassessableSpecimen` gains `specimen: SpecimenBrief`**, optional in 1.4.0
and **required in 1.5.0**, at which point `specimen_id` is retired. Two steps
rather than one because E is mid-sprint on `api/almanac/` as this is written
and G, who serves the other half, is not running at all: a required field added
under a live workstream is a broken build somebody else has to discover.

The deprecation is recorded in the schema description, not only here.

### 2. A satisfied task says what satisfied it (J's 3)

`satisfied_by` is nullable, so a task may legally report `status: satisfied`
without saying what settled it — and J's screen, correctly, then says "the API
did not say what settled it" rather than picking rain. That sentence should
never be reachable. "Satisfied" with no cause is the same failure ADR 0018 was
written about: an answer that reads as reassurance while carrying no
information.

**A task whose `status` is `satisfied` must state `satisfied_by`.** Expressed in
the schema as a JSON Schema `if`/`then`, which OpenAPI 3.1 carries, so it is
checked rather than merely asked for. Both producers already hold the invariant
(`api/tending/domain.py` sets `rain` or `manual`); this stops the third one from
not holding it.

### 3. The notification ledger gets a table (F's 1)

F's dedupe ledger is derived from `job_run.detail` over a rolling 36 hours. It
was the honest thing to build against a frozen schema, and F said so rather
than quietly adding a table. It cannot expire a key, and it cannot say which
member was told without unpacking a blob — so "did this phone already get this
frost alert?" is answered by a scan and a guess.

**Migration `005_notification.sql` adds the `notification` table**, forward-only,
in the shape F asked for: `id, kind, dedupe_key, member_id, sent_at, ok`, with
the lookup index the dedupe actually performs. Two notes on the shape:

- `member_id` is nullable and `ON DELETE SET NULL`. The ledger outlives the
  member, because the question it answers is "was this *destination* told", and
  F's dedupe key already names the destination rather than the person (two
  members pointing at one kitchen tablet is one tablet, and it should chime
  once).
- `ok` records the attempt, not the intent. A refused send is a row: a
  credential caught by `assert_clean` on the way out is exactly the event
  somebody will later need to find, and a ledger that only records successes
  cannot be asked why a phone stayed quiet.

Nothing in this table is a credential. It records *that* something was sent and
where to, never the body.

### 4. `notify_prefs` and `external_ids` get a stated convention (F's 2, and S3's 5)

Both are `jsonb` typed `additionalProperties: true` — open blobs, which was
right when nothing depended on their shape and is wrong now that two
workstreams read them and a third (J's Ministry Office) will write them. An
open blob with a convention nobody wrote down is a convention that drifts.

**Both gain their documented shape in the spec**, as a description with the
canonical block, while staying open for keys the app does not know about. The
block is F's, unchanged, because F wrote it against a working adapter.

`service` is a Home Assistant service name and **not** a credential — the
credential is the token in the Authorization header and never comes near a
payload or a stored preference. Any domain is accepted: `script.tell_everyone`
is a perfectly good way for a household to route notifications, and refusing it
would be this app deciding how somebody else's hub is organised. A member with
no `service` is not a recipient, and that is a normal household, not a fault.

### 5. `Integration` states its status (F's 5, S3's 4)

`last_ok_at` and `last_error` cannot express **stale** — answering, never
erroring, and quietly hours behind. That is the exact silent failure this
workstream exists to catch, and every consumer currently recomputes it from two
columns and a threshold they each choose for themselves.

**`Integration` gains `status`**, one of `ok`, `degraded`, `down`, `stale`,
`unconfigured`, optional in 1.4.0 and required in 1.5.0. It is a **computed**
field, not a column: it is derived from `enabled`, `last_ok_at` and
`last_error`, so there is no migration and no second source of truth to fall out
of step with the first. The threshold that separates `ok` from `stale` belongs
to the integration kind and is the server's to decide, once, rather than each
client's to invent.

### 6. A worker is somebody, and S7 is when it gets a name (F's 4)

The `session` security scheme is declared in the spec and enforced nowhere. F's
hub worker now calls `MOH_API_URL` with no Authorization header and no cookie —
deliberately, with a test pinning it, because `MOH_HA_TOKEN` belongs to Home
Assistant and to nothing else. F flagged this before it breaks rather than
after: the day the cookie is enforced, notifications stop, silently, and the
symptom is a household that stops being told about frost.

**Decided:** workers get a service identity distinct from any user session, and
it arrives in **S7 (Hardening)** with the rest of auth, not before. Piecemeal
auth is how a deployment ends up with two half-enforced schemes. Three
constraints bind whoever implements it, and they are decided now so the S7 work
has no room to drift:

- The worker credential is a **swarm secret mounted as a file**, never an
  environment variable (ADR 0019 — `docker inspect` reads an environment block).
- It is **not** `MOH_HA_TOKEN`, and not any token the app issues to a person.
  One credential, one purpose; the calendar-feed token stays the only
  credential this application issues to a human.
- It is **never logged**, and that claim is tested, not asserted in prose. ADR
  0019 made exactly this promise about the calendar token and was wrong in two
  places — uvicorn's access log and an nginx guard aimed at a path no route has
  ever served. The addendum records it. A promise of this shape is a test or it
  is nothing.

Until S7, the unenforced scheme stays unenforced and F's no-header call stays
correct. What is **not** acceptable is enforcing the cookie without doing this
work: that is the silent breakage F named.

### 7. A members fixture (F's 3) — routed, not decided here

`fixtures/` has no members file, so a mock stack read through the API can never
demonstrate a notification, and F's mock derives a synthetic Keeper and marks it
as synthetic. `fixtures/` is L's. L is running S5 as this is written and the
request has been passed on; it is not a contract change and needs no ADR.

### 8. A bare `$ref` to an object cannot say "there isn't one" (found in review)

Not an escalation — found while validating live responses against the schema
before shipping 1.4.0, which is a thing this project had never actually done.
**Every task the API serves violated the frozen contract, and had since 1.0.0.**

`Task.completed_by` is `{ $ref: Member }`. A task that is not finished has no
completer and serves `null`. `Member` is `type: object`, so `null` is a
violation — 36 of 36 tasks, 9 of 9 on Morning Rounds, and 12 of 12 specimens on
`next_task`. Nothing caught it because the contract tests validated that the
*document* was a legal OpenAPI document and that routes matched, never that a
response matched its schema.

Worse than the count is `CareValue.source`. That schema's own description reads:
*"A value with no `source` must carry `confidence: unknown`."* The property was a
bare `$ref`, so the contract **forbade expressing the exact state rule 6 exists
to handle**. An uncited care value could not legally say it was uncited.

Four properties are now `anyOf: [{$ref}, {type: 'null'}]` — `Task.completed_by`,
`Specimen.next_task`, `CareValue.source`, `LogEntry.photo` — being the two
violated live and the two where absence is a normal state the fixtures merely do
not reach. Eleven more bare `$ref`s to object schemas remain, and they are left
alone deliberately: widening a frozen contract on suspicion lets a producer send
`null` where a consumer must have a value, which is the same defect pointing the
other way. They are recorded here so the audit is not redone from scratch:

`Specimen.species`, `Specimen.location`, `TaxonCandidate.source`,
`FrostAlert.specimen`, `Task.specimen`, `Pin.specimen`, `MorningRounds.weather`,
`CalendarFeed.filters`, `CalendarFeedCreate.filters`, `MapLayer.calibration`,
`FieldNote.written_by`.

Of these, `MapLayer.calibration` (an uncalibrated layer is the state *before*
calibration) and `FieldNote.written_by` (a departed member) are the two most
likely to be wrong. They belong to H and K, who should decide when they next
touch them rather than have A guess from outside.

**The missing test matters more than the fix.** A contract nothing validates
against is documentation, and this one drifted for five sprints without a single
failing check. `tests/contract/` is L's; the request is with L.

## Consequences

- Contract **1.4.0**: additive only. Every producer on `main` stays valid.
  Nothing in 1.4.0 breaks a consumer written against 1.3.0.
- Contract **1.5.0** will make `UnassessableSpecimen.specimen` and
  `Integration.status` required and retire `specimen_id`. That is a breaking
  change and lands in a sprint where E, G, J and F can move together. It is
  written down here so it is not rediscovered.
- Migration `005_notification.sql`, forward-only.
- Four properties become nullable (§8). This is a **widening**: a consumer
  written against 1.3.0 that assumed a `Member` object where `null` now arrives
  was already wrong, because `null` was already arriving.
- S7 inherits the worker service identity with its three constraints settled.

## What this ADR does not do

It does not add a `notification` *API*. The table serves the worker's own
dedupe; a notification history somebody can read on a screen is a different
feature with different privacy questions, and inventing the endpoint now would
be guessing at both.

It does not make `status` a column. A computed field can be wrong in one place;
a stored one can be wrong in two, and the second is the one nobody notices.
