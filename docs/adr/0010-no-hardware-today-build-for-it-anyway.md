# ADR 0010 — No irrigation or soil-moisture hardware today; keep the seams for it

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A
- **Resolves:** open decision 5 in ADR 0006, and narrows part of S5

## Context

The plan treats soil moisture sensors (Ecowitt, MiFlora via HA) as a watering
override, and lists irrigation hardware control as out of scope for v1.0
pending a decision.

The maintainer has confirmed: **there is currently no automated irrigation
equipment and no soil moisture monitoring hardware**, but the app should be
built as though both may be added later.

## Decision

1. **Irrigation control stays out of v1.0**, as the plan already says. Nothing
   is built to actuate a valve.
2. **Soil moisture sensors are supported but not present.** The schema, the
   contract and the engines keep the override path in full — `reading.metric`
   includes `soil_moisture_pct`, `water_balance.sensor_override_pct` exists,
   and `SUPPORTED_METRICS` in `workers/hub/tasks.py` lists it. None of it is
   removed, and none of it is a stub.
3. **The override path is exercised by fixtures, not by hardware.** Workstream
   L adds a scenario in which a soil probe contradicts the model, and the S5
   tests assert the sensor wins. That is how the code stays honest with no
   device to plug in.
4. **The model-only path is the shipping path.** Every engine must produce a
   complete, correct answer with zero sensor sources configured. A missing
   sensor is the normal case in v1.0, not a degraded one.

### S5 is narrowed accordingly

The plan's S5 deliverable "soil sensor override (F)" becomes: keep the
override in the engine, prove it against the fixture scenario, and leave the
adapter able to pick a probe up the day one is added. It is no longer a
hardware-integration task, and S5's exit criteria do not depend on a device.

## Consequences

- **The water balance is now the sole authority on outdoor watering.** Nothing
  measures the soil to catch it when it is wrong. That raises the stakes on
  `water_k_c`, and under ADR 0007 several of those values are uncited —
  `confidence: unknown` in the fixtures for the snake plant and the mandrake.
  Two things follow, both already required elsewhere and now load-bearing:
  the UI must show the confidence next to a watering recommendation derived
  from an unknown coefficient (ADR 0004), and the user's edit of a care value
  must win outright.
- Manual watering logging matters more than it would with probes: it is the
  only correction signal the model gets. `water_balance.irrigation_mm` is fed
  from logged completions, and Workstream G must make logging an amount easy
  rather than optional.
- Adding hardware later is additive: a new `sensor_source` row, and the
  override the engine already honours. No migration, no contract change.
