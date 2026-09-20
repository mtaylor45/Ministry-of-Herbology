# Fixtures — frozen as of S0

Shared, deterministic sample data. Every mock is driven by these files, and the
weather scenarios are the acceptance tests for the water-balance and frost
engines. **Only Workstream A changes these files (proposals from L via ADR).**

| File | Contents |
| --- | --- |
| `site.json` | One site with coordinates, timezone and NWS zone |
| `locations/locations.json` | Indoor rooms and outdoor zones, with cover and sun exposure |
| `species/species.json` | Eight species with fully cited care profiles |
| `species/sources.json` | The source records those citations point at |
| `specimens/specimens.json` | Twelve specimens: indoor, outdoor, container, in-ground, a group |
| `weather/baseline_30d.json` | 30 days of ordinary observations, for history views |
| `scenarios/drought.json` | 14 rainless days; the deficit must cross threshold |
| `scenarios/storm.json` | A dry spell broken by 38 mm of rain; due waterings become "satisfied by rain" |
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

## Determinism

All ids are fixed UUIDs, all dates are absolute, and no fixture depends on the
current date. Tests freeze the clock to the scenario's `start`.
