# ADR 0007 — Free sources only; paid APIs and generated plates stay off

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A
- **Resolves:** open decision 1 in ADR 0006

## Context

Enrichment (D) and the Naturalist's Journal (K) could draw on paid services:
Perenual's care API, an image-generation API for Journal plates, and Google's
one-off Smart Device Management fee for direct Nest access. Each buys coverage
the free sources do not have.

## Decision

**Free and openly licensed sources only.** The maintainer has confirmed this.

- Enrichment uses POWO, GBIF, Wikipedia, Wikidata and USDA. Perenual stays
  behind the `MOH_PERENUAL_API_KEY` feature flag, disabled, and the free-source
  path must be complete on its own — not degraded-but-shipping.
- Journal plates come from the public domain: Biodiversity Heritage Library,
  Wikimedia Commons, plantillustrations.org. Generated plates stay behind a
  disabled flag.
- Nest is reached through Home Assistant, so the SDM fee does not arise. See
  open decision 2, still open, which this makes cheaper either way.

## Consequences

- Care coverage will be thinner for common houseplants, which is exactly where
  Perenual is strongest. That gap shows up honestly as `confidence: unknown`
  care values, which the UI already renders and the user can edit (ADR 0004).
  Workstream D must not paper over it.
- Some specimens will have no Journal plate. Workstream K designs the empty
  state as a first-class screen, not an error — "no plate has been drawn of
  this one yet" is a true and pleasant thing for a herbarium to say.
- Reversible: both paths exist behind flags. Turning either on is a
  configuration change, not a rewrite. That is why they are built as flags.
