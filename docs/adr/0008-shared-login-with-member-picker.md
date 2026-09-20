# ADR 0008 — One shared login with a household member picker

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A
- **Resolves:** open decision 4 in ADR 0006

## Context

Tasks are attributed to a household member, and members have their own
notification preferences and calendar feeds. That could mean real per-member
accounts, or one household session with a picker.

## Decision

**One shared session for the household, with a member picker for attribution.**
The maintainer has confirmed this.

- The `member` table already exists and carries role, notification preferences
  and calendar feeds. Nothing about the data model assumes shared auth.
- Completing a task asks who did it, defaulting to the last member used on that
  device (a per-device preference, not a server-side identity).
- Calendar feed tokens remain **per member and per filter set**, and are the
  one real credential in the system. A shared app session does not make a
  shared feed URL acceptable.

## Consequences

- S4 (the MVP sprint) does not carry an authentication build, which is the
  point: it is the sprint that has to land a daily-usable app.
- This is additive to reverse. Per-member auth later attaches a credential to
  an existing `member` row; no migration of task history is needed, because
  attribution already points at member ids rather than at sessions.
- The app stays inside the household network. ADR 0006 keeps public and
  multi-household hosting out of v1.0, and this decision depends on that.
  If that changes, this ADR is superseded before anything is exposed.
