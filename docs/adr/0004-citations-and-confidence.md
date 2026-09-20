# ADR 0004 — No invented plant facts: citations and confidence

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

The app tells people how to keep living things alive. A plausible-sounding but
invented watering interval or frost threshold kills plants. Enrichment draws on
POWO, GBIF, Wikipedia, Wikidata, USDA and Perenual — sources of very uneven
quality — and on an LLM to synthesise prose.

## Decision

Every care value is stored twice: as a typed column on `species` for the engines
to use, and as a row in `care_value` recording **where it came from** and **how
much to trust it**.

- `care_value.source_id` points at the `source` row, which keeps the URL, licence,
  retrieval time and the raw payload.
- `care_value.confidence` is one of `high | medium | low | unknown`.
- A value with no source must be `confidence: unknown`, enforced by a database
  `CHECK`. The only exception is a user override.
- The UI shows the source and confidence next to every care value, and every
  value is editable. A user edit becomes a `care_value` row with
  `is_user_override: true` and wins over all sources.
- The synthesis step may **rank and select** among sourced values and may write
  prose for the Compendium. It may not originate a number.
- Generated Journal plates are labelled `origin: generated` and are never
  presented as botanical illustration of record.

## Consequences

Enrichment can legitimately come back with "we don't know", and the UI has to
render that state well rather than hide it. Workstream D's synthesis is a
selection problem, not a generation problem, which also makes it testable against
fixtures.
