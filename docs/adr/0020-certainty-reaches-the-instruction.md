# 20. Certainty reaches the instruction, not just the API boundary

Date: 2026-09-24

## Status

Accepted. Contract 1.3.0, migration 004.

## Context

Workstream G built the scheduler in S4 and escalated five gaps rather than
working around any of them. Four are contract or schema; the fifth was a
security defect and is fixed separately with an addendum to ADR 0019.

The four share one shape, and it is the shape this project keeps rediscovering:
**the honest version of an answer is harder to produce than the confident one,
so the confident one wins by default.**

ADR 0018 established that a degraded input must leave the API looking degraded.
It applied that to `WaterBalance` and `FrostAlert`. But a water balance is not
what anyone acts on — a *task* is. The chain runs care value → water balance →
task → a person standing in a garden with a watering can, and ADR 0018 stopped
it at the second link.

## Decision

### 1. `Task` carries `confidence`, `degraded` and `degradations[]`, required

Same three fields, same `Degradation` schema, same reasoning as ADR 0018: a
response that *may* omit them cannot be distinguished from one that had nothing
to declare. The instruction a person acts on is the place this matters most, not
least.

G already serves them, additively, so a 1.2.0 client is unaffected. The plain
sentence also goes on `detail`, which was already contracted — so a client that
reads neither new field still shows the caveat.

### 2. `task` gains columns to keep that certainty in

The frozen table had `detail` and nothing else, so G recomputes on every read and
merges onto the row before serialising. That works for an open task and fails for
a completed one, which is never regenerated: **its confidence is not recoverable
afterwards.** A care record that cannot say how sure it was is a worse record,
and this app's whole claim is that it does not invent plant facts.

`confidence text`, `degraded boolean`, `degradations jsonb`, forward-only in
`004`. Never back-filled: an empty column on a done row means *it did not say*,
not *it was certain*.

### 3. `MorningRounds` gains `unscheduled[]`

ADR 0018 §2 gave `/almanac/frost` an envelope because "a list of alerts cannot
say 'and these three I could not judge'". Morning Rounds has the identical hole
in the screen people open every day. A plant with no watering interval anywhere —
no cited care value, no species column, no household rule — generates no task,
and **a plant with no task is indistinguishable from a plant that needs
nothing.**

Served today as `unscheduled: [{specimen_id, reason}]`, reusing the
`UnassessableSpecimen` schema ADR 0018 already added rather than inventing a
parallel shape. Required, for the same reason the fields above are.

### 4. `water_balance` gains the same three columns

ADR 0018 put certainty on E's *response*. The table behind it kept none, so in
live mode the API reads a deficit and a threshold with no provenance and reports
a flat `medium` — which is what `workers/weather/quality.py` calls a modelled
figure at best, and is the most honest thing available from a row that stores
nothing else.

It is still not good enough, and the direction of the error is the point: **the
live path is quieter about its own uncertainty than the mock path.** The mock
runs the engine and knows why it is unsure; production reads a number. That is
the same failure mode as the four Arq workers — the truthful version was harder
to see than the confident one, so nobody saw it.

The columns land here. **Writing them is E's**, and is S5 work: S5 is Smart
Watering and E owns the engine. Until E fills them, the live path keeps
reporting `medium` with the staleness it can verify from the row's own date, and
that remains visibly worse than the mock.

## Consequences

`contracts/VERSION` → **1.3.0**. Additive on `Task`, additive on
`MorningRounds`, no endpoint changes shape. Migration `004_certainty_columns.sql`
is forward-only and every column is nullable or defaulted, so existing rows stay
valid and read as "did not say".

**Nothing needed implementing.** G already serves all of it; verified against the
running app before the contract was written, rather than after. This ADR makes
the contract describe what is true instead of lagging it.

**J builds Morning Rounds against 1.3.0** and must render `unscheduled` — a
plant the scheduler could not judge has to be visible, or the envelope is
decoration.

**E owns §4's write side in S5.** Raised here rather than left in a sprint note.

## References

- ADR 0018 — the Almanac carries its own certainty; this extends it one link
- ADR 0019 + its 2026-09-24 addendum — the fifth escalation, the token in logs
- ADR 0010 — nothing measures the soil, so the model is the only authority
- `docs/sprints/S4-workstream-g.md` — G's five escalations as written
