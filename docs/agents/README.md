# The twelve workstreams

Twelve agents build this app in parallel. Each owns one directory, builds
against the frozen contract, and ships one PR per task. Workstream A reviews and
merges everything.

Agent definitions live in [`.claude/agents/`](../../.claude/agents/) — one file
per workstream, loadable by name. The same briefs are the prompt for a remote
session when a workstream runs on its own machine.

| ID | Agent | Owns | Active in |
| --- | --- | --- | --- |
| A | `ws-a-architect` | `contracts/`, `docs/adr/` | every sprint |
| B | `ws-b-platform` | `infra/`, `.github/`, `scripts/`, `Makefile` | S0, S1, S10 |
| C | `ws-c-inventory` | `api/inventory/` | S1, S2 |
| D | `ws-d-botany` | `workers/botany/` | S1, S2 |
| E | `ws-e-weather` | `workers/weather/`, `api/almanac/` | S3, S5, S6 |
| F | `ws-f-hub` | `workers/hub/` | S3, S4, S5, S9 |
| G | `ws-g-scheduling` | `api/tending/` | S4, S5, S6, S9 |
| H | `ws-h-maps` | `api/grounds/`, `web/src/lib/map/` | S7 |
| I | `ws-i-design-system` | `web/src/lib/ui/`, `web/src/app-shell/` | S0, S1, S9 |
| J | `ws-j-feature-ui` | `web/src/routes/` | S2, S3, S4, S6, S7, S8, S9 |
| K | `ws-k-journal` | `workers/plates/`, `web/src/routes/journal/` | S8 |
| L | `ws-l-qa-docs` | `tests/`, `fixtures/`, `docs/user/` | S0, S5, S10 |

## How a workstream works

1. **Read first.** `CLAUDE.md`, `docs/plan/development-plan.md`, the ADRs, and
   `contracts/` — in that order. The contract is the answer to most questions.
2. **Branch.** `ws-<id>/<sprint>-<slug>`, e.g. `ws-e/s3-openmeteo-ingest`. CI
   reads the workstream id out of the branch name to check ownership.
3. **Build against mocks.** Every dependency already answers on HTTP with
   fixture data. Nobody waits.
4. **Test.** `make contract` is the fast signal; `make test` is the full one.
   A workstream that changes an engine must keep the scenario suite green.
5. **One PR, opened as a draft**, with tests, a short description, and the
   sprint task it closes. A reviews and merges.
6. **Never edit `contracts/`.** If the contract is wrong, say so in an issue or
   PR description and tag A. A writes the ADR.

## Monitoring

Each workstream reports at three points:

- **On pickup** — one line: what it is starting, and anything it is blocked on.
- **On PR** — the PR description carries the sprint task, the tests added, and
  any contract friction it hit.
- **At the sprint demo** — against that sprint's exit criteria in the plan,
  passed or not, with no rounding up.

A tracks all of it in `docs/sprints/S<n>.md` and holds the exit-criteria call.

## Escalate rather than guess

- A contract change is needed → stop, describe it, tag A.
- An open decision in `docs/adr/0006-open-decisions.md` blocks you → build
  against the stated default and note it in the PR.
- A plant-care value has no source → ship it as `confidence: unknown`. Never
  invent one (ADR 0004).
