# ADR 0005 — Wizarding botany, no franchise assets

- **Status:** Accepted
- **Date:** 2026-09-20
- **Workstream:** A

## Context

The app's personality is a Ministry of Herbology: a wizarding-botanical
institution. The obvious reference points are someone else's intellectual
property.

## Decision

The theme is **original wizarding botany**: greenhouses, quills, owls, parchment,
herbariums, apothecary cabinets, botanical plates, ministerial bureaucracy.

Not permitted anywhere in the product, including in generated plates and copy:

- crests, house names, house colours as a system;
- character, creature or place names from any franchise;
- film or book typefaces, or close imitations of them;
- spell names or invented-Latin catchphrases taken from a franchise.

Two further rules:

1. **Every themed string is paired with a plain one.** `title` is themed,
   `plain_title` is literal, and both are in the schema. The plain string is what
   a screen reader announces first and what appears in a calendar event body.
2. **Whimsy at moments, not throughout.** Completion, rain-satisfaction and frost
   alerts get an animation; nothing else does. All of it honours
   `prefers-reduced-motion`.

Typography uses openly licensed display faces in the right register (IM Fell
English, Cinzel) for headings only, with a readable serif for body text.

## Consequences

Copy review is part of PR review for any workstream that writes user-facing
strings. Workstream K's plate generation prompts are reviewed for the same
reasons. The paired-string rule costs a column and pays for accessibility.
