# ADR 0009 — Home Assistant is the only route to indoor conditions

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A
- **Resolves:** open decision 2 in ADR 0006

## Context

The plan called for indoor temperature and humidity from Home Assistant, Google
Home (a Nest 4th-gen Learning Thermostat) and Apple HomeKit. The open question
was how to reach the Nest: Google's Smart Device Management API directly, or
Matter, or through Home Assistant's own Nest integration.

## Decision

**There is no direct Nest integration. Indoor temperature and humidity are read
from Home Assistant**, which is already the hub for everything else. The
maintainer has confirmed this, and may revisit it later to add routes.

- Workstream F builds one adapter, against Home Assistant's REST and WebSocket
  APIs, addressing devices by **HA entity id**. It contains no Nest-specific,
  HomeKit-specific or Matter-specific code.
- Whatever HA exposes, the Ministry can read. How HA came by it — Nest via
  SDM, HomeKit, Matter, Zigbee, ESPHome — is HA's problem and not ours.
- The one-off Google SDM fee does not arise, which is consistent with ADR 0007.
- `sensor_source.adapter` keeps its full enum (`nest`, `homekit`, `ecowitt`,
  `miflora`, …). In v1.0 only `home_assistant` and `manual` are used. The other
  values stay as a label for where a reading ultimately came from, and as the
  hook a future direct adapter would use. No migration is needed to add one.

## Consequences

- **Home Assistant becomes a hard dependency for indoor conditions.** If HA is
  down, indoor readings stop. F must record that on
  `integration.last_error` so the Ministry Office shows it plainly, and the
  Almanac must render "no recent reading" rather than drawing a flat line
  through a gap.
- Indoor care rules — the interval rules adjusted by indoor humidity — have to
  degrade sensibly when readings are absent, falling back to the plain seasonal
  interval rather than stalling.
- This is the cheapest decision to reverse of the three routes: adding a direct
  adapter later means a new `sensor_source.adapter` value and a new poller,
  with no change to the schema, the contract or the engines.
