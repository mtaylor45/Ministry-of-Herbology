# Fixtures

Shared, deterministic sample data. Every mock is driven by these files, and the
weather scenarios are the acceptance tests for the water-balance and frost
engines.

**Workstream L owns this directory** — `CLAUDE.md`, `docs/agents/README.md` and
`scripts/check_ownership.py` all put `fixtures/` with L, and the ownership check
CI runs enforces it. (This file said "only Workstream A changes these" until S5,
which contradicted all three; the frozen thing is `contracts/`, which is A's.)
The freeze that does apply here is narrower and stricter: a fixture must never
contradict the schema, and `tests/contract/test_fixtures.py` is what holds it to
that.

| File | Contents |
| --- | --- |
| `site.json` | One site with coordinates, timezone and NWS zone |
| `locations/locations.json` | Indoor rooms and outdoor zones, with cover and sun exposure |
| `species/species.json` | Eight species with fully cited care profiles |
| `species/sources.json` | The source records those citations point at |
| `specimens/specimens.json` | Twelve specimens: indoor, outdoor, container, in-ground, a group |
| `members/members.json` | The household: one notified about everything, one about frost only, one not a recipient at all ([why](members/README.md)) |
| `weather/baseline_30d.json` | 30 days of ordinary observations, for history views, closing on a soaking |
| `scenarios/drought.json` | 21 rainless days; the deficit must cross threshold |
| `scenarios/storm.json` | Ten rainless days of July heat, broken on the last day by 38 mm; due waterings become "satisfied by rain" |
| `scenarios/frost.json` | A 72h cooling trend into −2 °C with an NWS advisory |

## Scenario format

```json
{
  "name": "drought",
  "site_id": "...",
  "start": "2026-06-01",
  "days": [{ "date": "...", "tmin_c": 0, "tmax_c": 0, "precip_mm": 0, "et0_mm": 0 }],
  "advisories": [],
  "expect": { "…": "assertions the engines must satisfy" }
}
```

The `expect` block is the contract: `tests/` asserts each one. An engine change
that breaks an expectation needs an ADR, not a fixture edit.

The reverse also happens, and did in S5: an expectation the engine's own
arithmetic refutes is the *fixture's* bug. `storm.json` claimed the in-ground
rose was satisfied by rain after six dry days, but a 60 mm soil profile at
`K_c 0.85` needs eight days of that heat to cross its threshold — so the rose
was never due, and a watering that was never owed cannot be settled. The dry
spell is ten days now and the claim is true. Read the engine before editing an
expectation; write the ADR when the engine is the thing that is wrong.

### Why a scenario ends on its wet day

`BalanceSeries.status` is the status of the series' **newest** day. A storm
whose rain falls in the middle and then runs on for three dry days reports `ok`
at the end, and the `satisfied` state — the one thing the scenario exists to
show — never reaches a screen. `storm.json` therefore ends on the soaking, and
`weather/baseline_30d.json` does too, so that the "settled without you" section
of Morning Rounds is populated in the default mock deployment rather than only
in a unit test. Workstream J raised that gap at the end of S4.

## Determinism

All ids are fixed UUIDs, all dates are absolute, and no fixture depends on the
current date. Tests freeze the clock to the scenario's `start`.
