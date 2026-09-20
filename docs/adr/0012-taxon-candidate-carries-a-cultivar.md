# ADR 0012 — `TaxonCandidate` carries a cultivar

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A
- **Requested by:** Workstream D, in PR #5
- **Contract version:** 1.0.0 → 1.1.0

## Context

Intake resolves a typed name to an accepted scientific name **and a cultivar**
— that is in the plan's accepted additions, and `specimen.cultivar` exists in
the schema to hold it. But `TaxonCandidate`, the shape `POST /taxon/resolve`
returns, had nowhere to put one.

POWO and GBIF index species, not cultivars. So when someone types
`Lavandula angustifolia 'Hidcote'`, Workstream D must split `'Hidcote'` off
before querying, and then had no contractual way to hand it back — leaving the
caller to re-parse the string D had already parsed.

D shipped it as an additive field (the schema does not set
`additionalProperties: false`) and asserted in its own tests that `cultivar` is
the *only* extra key, rather than quietly widening the response. That is the
right way to raise it.

## Decision

Add to `TaxonCandidate`:

```yaml
cultivar: { type: [string, 'null'] }
```

Optional and nullable: most candidates have none. The contract version goes to
**1.1.0** — additive, so nothing that reads 1.0.0 breaks.

**Not** adding `matched_name`, which D also floated (so the UI can say "you
typed *Sansevieria*, this is *Dracaena*"). It is a good idea and it is a
different decision: it concerns how a resolution is *explained* rather than
what it *is*, and Workstream J has not yet built the screen that would use it.
It is deferred to S2, when J's intake flow exists and can say what it needs.

## Consequences

- No migration. `specimen.cultivar` already exists and is where this lands.
- Workstream C's `SpecimenCreate` already accepts a `cultivar`, so intake can
  now pass one straight through from resolution without re-parsing.
- The rule that made this cheap is worth repeating: an additive, nullable
  field on a response is the least disruptive contract change there is, and
  costs one ADR rather than a coordinated release.
