# ADR 0016 — A local ET₀ fallback, so the water balance never simply stops

- **Status:** Accepted; amended 2026-09-23 by ADR 0018
- **Date:** 2026-09-21
- **Workstream:** A

> **Amendment (ADR 0018, §5).** This ADR named `climate_indices` as the
> implementation. Workstream E implemented FAO-56 Hargreaves as one pure
> function with the equations written out, which is the whole of what was
> needed, and the library is **not** a dependency. A self-hosted, offline-first
> app earns more from one fewer dependency than from importing a package for a
> single published formula. The function is the seam the library plugs into if
> that ever changes. The method, its inputs and its confidence cap are unchanged.

## Context

The water balance consumes ET₀ from Open-Meteo. If Open-Meteo is unreachable
there is currently **no fallback at all**: the deficit stops advancing and the
engine quietly stops deciding when to water. Under ADR 0010 nothing else is
watching the soil, so an outage does not degrade the feature — it silently
removes it, while the UI goes on looking healthy.

ADR 0009 already set the pattern for a hard dependency: record the failure, show
what is stale, and degrade to something honest rather than stalling.

## Decision

**Compute ET₀ locally by the Hargreaves method when the ingested value is
missing**, using `climate_indices` (BSD 3-Clause, pip-installable, maintained).

- Hargreaves needs daily minimum and maximum temperature and the site latitude.
  We already store all three (`weather_forecast.temp_min_c`, `temp_max_c`,
  `site.latitude`), so this adds no new data dependency.
- A locally computed ET₀ is **recorded as such** on the `water_balance` row, not
  silently mixed with ingested values. A day computed from a fallback is a
  different quality of input from a day measured, and the Almanac says so.
- Ingested ET₀ always wins when present. The fallback never overwrites it.
- Where neither is available, the day's deficit does not advance and that is
  shown — an unknown day is not a zero-evaporation day.

## Consequences

- Workstream E gains a dependency it did not have. Worth it: the alternative is
  a watering engine that fails closed and looks fine.
- The fallback is less accurate than Open-Meteo's ET₀, which is the point — it
  is a documented degradation, labelled, rather than a gap.
- `climate_indices` also implements SPI, SPEI and the Palmer indices. Those are
  out of scope for v1.0 and tempting; a drought index is not a watering
  decision, and adding one would widen S5 without improving a single plant's
  care.
