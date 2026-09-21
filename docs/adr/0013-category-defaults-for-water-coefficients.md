# ADR 0013 — Cited category defaults for `water_k_c`

- **Status:** Accepted
- **Date:** 2026-09-21
- **Workstream:** A
- **Consequence of:** ADR 0004 (citations), ADR 0007 (free sources), ADR 0010 (no soil probes)

## Context

`water_k_c` is the plant water-need coefficient in the water balance. Under
ADR 0010 there is no soil-moisture hardware, so that balance is the **sole
authority** on when an outdoor plant is watered and nothing measures the soil to
catch it being wrong.

S2 established that no free source publishes it for our plants. USDA PLANTS
returns no measured characteristics for any of the eight fixture species.
Trefle has no crop coefficient at all — its precipitation fields describe a
climate envelope, not a demand coefficient. Perenual's free tier is closed to us
(ADR 0014). So the value that matters most is the one nobody attests.

Three ways out were considered: leave it uncited and lean on the warning UI;
require a per-plant value before the balance runs; or cite a published table by
vegetation category. The maintainer chose the third.

## Decision

**A `water_k_c` with no species-level source is filled from a published
coefficient table, keyed on vegetation category, and cited as a category
default.**

Three properties make this compatible with ADR 0004 rather than a violation of
it:

1. **The citation is real and auditable.** It points at a published table —
   FAO-56 (*Crop evapotranspiration: guidelines for computing crop water
   requirements*, FAO Irrigation and Drainage Paper 56) as the primary
   reference — with the table and category named, not at the species.
2. **The scope is explicit.** The `care_value` row records that the value
   describes a **category**, not this species, and the UI says so. "Typical for
   a broadleaf evergreen shrub" is a different claim from "measured for
   *Monstera deliciosa*", and the app must never present the first as the
   second.
3. **Confidence is capped at `medium`,** never `high`, and a species-level
   sourced value always outranks a category default. A user override outranks
   both (ADR 0004).

`water_k_c` therefore stops being `unknown` for most plants and becomes
*attested at category scope*. That is a smaller claim than a measurement and a
much larger one than a guess.

### For Workstream D and E to settle in implementation

- **FAO-56's tables are crop-oriented.** For ornamentals and houseplants the
  closer published analogue is **WUCOLS** (Water Use Classification of Landscape
  Species), which classifies landscape species by water use band. D should
  prefer whichever published table actually covers the plant, cite the one it
  used, and record the category in the note. Do not average two tables.
- **The category must be derived from attested botanical facts** — growth habit,
  leaf type, native range — not guessed from the name. A category assigned with
  no basis is the invented number this ADR is trying to avoid, wearing a
  citation.
- **No numbers are fixed in this ADR.** Putting a coefficient table in a
  decision record, unsourced, would be exactly the behaviour ADR 0004 forbids.
  The table belongs in `workers/botany/` with its citation attached.

## Consequences

- The engines get a defensible coefficient for every plant, so the water balance
  produces a real answer rather than resting on the fallback constant in
  `api/almanac` — which was never a fact about any plant.
- The UI's uncited-value warning does **not** disappear; it changes wording.
  A category default still needs to read as less certain than a measurement,
  and J's warning beside the watering recommendation stays.
- `confidence: unknown` remains reachable and must stay rendered: a plant whose
  category cannot be established honestly has no coefficient.
- Reversible. Removing the table returns those values to `unknown` with no
  migration, because the scope and source already live on the `care_value` row.
