# ADR 0003 — Contract-first development with directory ownership

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

Twelve agents work the same monorepo in parallel. The two failure modes are
agents blocking on each other, and agents silently editing each other's code.

## Decision

1. `contracts/` (schema, OpenAPI, MQTT topics) and `fixtures/` are **frozen in
   S0**. Only Workstream A changes them, and only through an ADR.
2. Every workstream owns a directory, listed in `CLAUDE.md` and enforced by
   `.github/CODEOWNERS` and a CI ownership check. A workstream writes only inside
   its own paths.
3. Every service ships a **mock** matching the contract under `<service>/mocks/`,
   driven by `fixtures/`. A consumer builds against the mock, never against
   another agent's timetable.
4. `tests/contract/` asserts the running API matches `openapi.yaml` and that the
   database matches the migrations. Contract tests run on every PR.
5. One task, one PR, opened as a draft, reviewed and merged by A.

## Consequences

Contract changes cost an ADR round-trip, which is deliberate friction on the one
thing that breaks everyone. In exchange, no workstream is ever blocked: the mock
always exists, and it always matches what will ship.
