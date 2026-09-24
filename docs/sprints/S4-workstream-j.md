# S4 — Workstream J: Morning Rounds

`web/src/routes/+page.svelte` was the S0 placeholder — a list of themed titles
and a hard-coded "Parched" pill, reading a mock. It is now the screen G's
scheduler makes possible, and the first half of the sprint exit criterion:
*daily care runs from the app.*

## What landed

1. **The round, grouped the way it is read.** `GET /tending/rounds` in four
   sections: what is owed, what was settled without you, what nothing is
   scheduled for, and what the frost is doing tonight.
2. **Batch completion.** `POST /tending/tasks/complete-batch`: tick several,
   mark them done in one action, attributed to a household member. One-tap
   completion posts a batch of one, so both paths are one path — the same
   reason G put them through one function.
3. **Certainty next to the instruction.** Every task's `confidence`, `degraded`
   and `degradations[]`, each degradation's sentence shown as G wrote it.
4. **`unscheduled[]` rendered**, with the reason per plant and a link to the
   facet where a care value can be set.

## The decisions that mattered

### Satisfied is not done, and neither is selected

A watering the rain settled keeps its place on the round, in its own section,
with what settled it — "Sated by the heavens — rain covered it". A task that
vanishes because it rained is a task the reader cannot tell from one that was
never scheduled, which is the whole failure this sprint is supposed to close.

The same distinction bit inside the batch bar. `TaskCheckbox` was built for
completion: a ticked box shows "Done" and strikes its label through. But
attribution happens *at* completion (ADR 0008), so a tick here cannot be the
completion — it is a selection waiting for a member and a button. Every
checkbox on this screen therefore overrides `donePlain`, and the strike-through
is raised with Workstream I rather than restyled from outside its library.

### A silence is rendered, not left blank

Two fields on this screen are served by G and absent from contract 1.2.0. That
makes three states, not two, and the screen tells them apart:

| The API says | The screen shows |
| --- | --- |
| `unscheduled: [{…}]` | the plants, each with the scheduler's reason |
| `unscheduled: []` | nothing — every plant is accounted for |
| no `unscheduled` at all | a notice saying this build cannot tell you |

The same for a task's certainty: a stated `null` reads as "does not say how
sure it is", never as "high", because a completed task's confidence is simply
not recoverable — the frozen `task` table has no column it could have been kept
in. A payload where no task carries the fields at all gets one notice at the
top of the section rather than nine identical ones.

This is the Almanac's `reportsItsOwnConfidence` seam, reused deliberately. That
vocabulary moved out of `almanac/` into `routes/shared/` in the first commit so
the two screens cannot grow two ways of saying one thing.

### A guess must not arrive looking like a measurement

Ten of the twelve fixture species carry an uncited watering interval, so on the
mock stack the marked path is the common one. Those tasks show "A guess, and
said to be one — confidence unknown — nothing attests this", and G's sentence
about the missing citation sits between the instruction and the button that
acts on it. Deliberately not the Almanac's wording: "read through cloud" is
right for a forecast whose ingest is stale and wrong for an interval nobody
ever cited, which is not a reading at all.

## For Workstream A

### 1. Contract 1.2.0 is still the frozen contract, and ADR 0020 does not exist

The brief for this sprint said ADR 0020 had added `unscheduled[]` to
`MorningRounds` in contract 1.3.0. In this tree it has not:
`contracts/openapi/openapi.yaml` is `version: 1.2.0`, `MorningRounds` has no
`unscheduled`, `Task` has no `confidence`, `degraded` or `degradations`, and
`docs/adr/` stops at 0019. G's escalations 1 and 3 are open, not closed.

Nothing was worked around: the screen renders all four fields from what G
serves and renders their absence too. But `tests/contract/` cannot protect a
field the contract does not carry, so today a server could stop sending any of
them and only this screen's own notice would say so. **Requested: land G's
escalations 1 and 3.**

### 2. `unscheduled[]` carries a bare `specimen_id`, so naming a plant costs a whole register

`{specimen_id, reason}` matches `FrostReport.unassessable`, and both have the
same consequence for a client: to put a name beside the reason, Morning Rounds
has to read `GET /specimens` as well. That is an extra request on the home
screen, and when it fails the panel whose entire purpose is to name the plants
nobody scheduled can only print uuids.

`Task` already solves this with `SpecimenBrief`. **Requested: `SpecimenBrief` on
`UnscheduledSpecimen` and on `UnassessableSpecimen`**, the way `Task` and
`FrostAlert` carry it.

### 3. A satisfied task may not say what satisfied it

`satisfied_by` is nullable in the contract, so `status: satisfied` with
`satisfied_by: null` is a legal response and the screen has to render something
for it. It says "Settled — the API did not say what settled it" rather than
picking rain, which is the honest reading but a poor one to show a person.
Worth either a non-null constraint alongside `status: satisfied`, or a note in
the contract that a client must handle it. Raised, not worked around further.

## For Workstream I

Two asks, neither of them worked around inside `web/src/lib/ui/`:

1. **`Label`'s plain half fails WCAG AA on a filled button.** `.plain` is
   `--moh-ink-muted`; on `--moh-accent` that measures **1.26:1** in the browser
   (light theme, 12.8px). Every `Button` given both `themed` and `plain` in the
   `primary` or `destructive` variant is affected — including the gallery's own
   `Tend to it / Water now` and `Uproot / Remove specimen`, and
   `CareValueList`'s "Set it down". The fix looks like one rule: on a filled
   button the plain half should inherit the button's own ink rather than
   `--moh-ink-muted`. Until then this screen's batch button carries its plain
   half alone, which is legible and loses the theming.
2. **`TaskCheckbox` assumes checked means done.** It shows `donePlain` and
   strikes the label through. Batch selection needs checked to mean *selected*,
   because the member is picked after the ticking and before the completion.
   `donePlain` is overridable and is overridden here; the strike-through is
   not. A `meaning="selection" | "completion"` prop would cover both.

## For Workstream L

The baseline weather fixture has no rain on its closing days, so the mock stack
returns an empty `satisfied` list and the demo cannot show the rain-satisfied
path at all — G asked for a fixture with rain in the last day or two, and this
screen is the place it would be seen. The fixture household also has exactly one
member, so the completion picker demonstrates attribution with nothing to
choose between.

## Verified

Run at 375px against the API on the mock stack, in a real browser, and against
a stub for the shapes the fixtures cannot produce:

- batch completion of two tasks: one `POST` carrying both ids and the member,
  the live region announcing "2 tasks marked done, recorded against Keeper",
  the round re-read, the selection cleared, the member remembered;
- one-tap completion of a single task, through the same path;
- a 422 on the batch: the failure named, the selection kept;
- the rounds endpoint failing outright: the screen says nothing on it is a
  statement about the plants;
- a 1.2.0-shaped response: both silence notices, no per-task caveat blocks;
- an empty round, a round with satisfied waterings, and two unscheduled plants
  (one the register could name, one it could not).

Keyboard order is select-all → member → per row: tick, link, complete. Contrast
measured in both themes: 5.69–14.95 for everything this screen draws, the one
exception being I's button label above. No horizontal scroll at 375px.

- `npm test` — 348 passed (36 new)
- `npm run lint`, `npm run build` — clean
- `.venv/bin/pytest tests/contract -q` — 48 passed
- `.venv/bin/pytest tests api workers scripts -q` — 751 passed, 37 skipped
- `python scripts/check_ownership.py --workstream J` — all within J's paths
