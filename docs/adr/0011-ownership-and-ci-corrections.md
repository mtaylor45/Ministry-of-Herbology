# ADR 0011 — Corrections to directory ownership and CI, from S1's first PRs

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

The first three S1 pull requests (#3 Workstream C, #4 Workstream I, #5
Workstream D) all passed their tests. Two failed the ownership gate, and all
three reported the same class of problem: the rules written in S0 make some
required work impossible to do inside a workstream's own directory.

To their credit, all three escalated rather than working around it, which is
exactly what rule 2 asks for. The rules were wrong, not the workstreams.

## Decisions

### 1. The gallery belongs to the design system

`web/src/routes/gallery/` moves to Workstream I. A component gallery is a
design-system artefact, not a feature screen; it renders components with no
API, no fixtures and no store behind it. I still may not write any other route.

### 2. `NOT_YET_IMPLEMENTED` is a shared progress marker

Rule 6 requires the workstream that implements a contract path to strike its
own entry from `NOT_YET_IMPLEMENTED` in
`tests/contract/test_api_matches_spec.py` — a file in Workstream L's
directory. That was a contradiction built into S0, and every sprint from here
hits it. Workstream C hit it first and chose correctly: the task named the
edit, and leaving the entry would have turned
`test_not_yet_implemented_entries_are_actually_missing` red anyway.

That one file is now writable by every workstream. Only the exemption list is
shared; the rest of L's suite is not.

### 3. A workstream's own tests must actually run in CI

**This was the serious one.** Rule 2 puts each workstream's tests inside its
own directory, and CI ran `pytest tests -q` — which collects only L's suite.
Workstream C had written 93 tests and Workstream D 107, and **none of them
would ever have run in CI.** Three sprints of that and the contract suite
would have been the only thing standing between us and a broken `main`.

CI now runs `pytest tests api workers -q`. Workstream C reported this; it is
the most valuable finding in the three PRs.

### 4. The API image must carry `workers/`

`infra/docker/api.Dockerfile` copied only `api/`, `contracts/` and
`fixtures/`, so a router living under `workers/` could not be mounted in the
built image. It now copies `workers/` and puts it on `PYTHONPATH`, as
`worker.Dockerfile` already did.

### 5. `workers/` is a package

Added `workers/__init__.py`, so a module is not reachable as both `botany.x`
and `workers.botany.x` — which aborts a whole `mypy` run.

## Consequences

- Three PRs unblock without any workstream having to violate rule 2.
- CI gets slower and much more honest. Expect it to start catching things.
- The general lesson, recorded for the sprints ahead: **when a rule makes
  required work impossible, the rule is the bug.** Escalating is the correct
  move and costs a round-trip; working around it silently costs far more.
