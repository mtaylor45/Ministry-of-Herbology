# ADR 0001 — Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

Twelve agent workstreams build this app in parallel against a frozen contract. A
decision made silently in one workstream becomes an unpleasant surprise in
another. We need a written, reviewable trail of the decisions that cross
boundaries.

## Decision

We record architecturally significant decisions as ADRs in `docs/adr/`, numbered
sequentially, in the format of this file. An ADR is required for:

- any change to `contracts/` (schema, OpenAPI, event topics);
- any change to the stack or a new runtime dependency;
- any change to workstream ownership boundaries;
- resolution of an item in `docs/adr/0006-open-decisions.md`.

Workstream A merges ADRs. Any workstream may propose one.

## Consequences

Changes to the contract are slower and visible, which is the point. Feature PRs
that need a contract change are split: an ADR PR first, then the feature.
