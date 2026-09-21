# ADR 0014 — The botanical source roster, after reviewing the public APIs

- **Status:** Accepted
- **Date:** 2026-09-21
- **Workstream:** A
- **Amends:** nothing. ADR 0007 stands unchanged.

## Context

S2 exposed the coverage gap ADR 0007 predicted: free sources attest very little
about our plants. Three public APIs were reviewed against it — Trefle,
Perenual and Pl@ntNet — along with the remains of OpenFarm.

## Decisions

### Trefle is accepted. ADR 0007 needs no amendment for it.

Trefle publishes under **CC-BY-4.0** with a defined attribution string
(`Data: Trefle.io (CC-BY-4.0)`, linking to trefle.io) and its records retain
their upstream licences. It aggregates USDA, Kew, IPNI, Tropicos, Tela Botanica
and Wikimedia, **reconciled on the accepted scientific name** — the same key D
already resolves to. It is openly licensed, so ADR 0007 already permits it; this
is not a policy change.

Mapping rules, which matter more than the adoption:

- **`light`** → `light_label`, and `light_min_lux`/`light_max_lux`. Trefle
  documents the lux mapping for its 0–10 scale, so the conversion is cited
  rather than invented.
- **`minimum_temperature`, `ph_minimum`, `ph_maximum`** → map **only after D
  verifies the units against a live record.** The documentation does not settle
  whether the pH fields are real pH or an Ellenberg-style index, and publishing
  an index as a pH would be a fabricated value with a citation attached.
- **`atmospheric_humidity` must not be mapped to `humidity_min_pct`.** It is a
  0–10 ecology index, not a percentage. Converting it is the same error D
  already refused when it declined to turn USDA's *Moisture Use* adjective into
  a crop coefficient.
- **Confidence is capped at `medium`.** Trefle has an open issue about
  arbitrating its own ecology indices against another dataset — it is doing the
  same conflict resolution D does, and its values are contested upstream.

### Perenual stays off, and ADR 0007 stands

Perenual's free tier is 100 requests/day over species ids 1–3000,
**non-commercial use only**, with pH behind a $139.99/month tier. It has the
richest field match we found.

It is nonetheless **free of charge, not openly licensed**: no redistribution
rights, and caching terms unstated. ADR 0007 says "free *and* openly licensed",
and the maintainer chose to keep that as written rather than amend it. The flag
stays disabled.

The reason this is worth the coverage it costs: every value we store stays
redistributable, which is what makes an open export meaningful (see the export
note in S10). A care profile we cannot legally hand to the next tool is a
liability dressed as data.

### Pl@ntNet is not a care source

Pl@ntNet identifies plants from photographs and returns ranked candidate species
with scores. It publishes **no care data at all**, so it cannot address this
gap. It remains what ADR 0007 made it: the flagged-off photo-intake path, with
the typed-name path complete without it. All its documentation endpoints
returned HTTP 503 during this review, so its quotas and terms are unverified
here.

### OpenFarm: dead upstream, usable data

OpenFarm shut down in April 2025 and its repository is archived. **No connector
may be built against it.** Its data was CC0 and survives as a rescued
`crops.json` of 340 records, each carrying the Wayback capture URL it was
rebuilt from — an auditable provenance chain, which is rare and welcome.

It is accepted as an optional **seeded local dataset**, not a live source, with
its limits recorded honestly: it covers `sun`, spacing and companions; it has no
crop coefficient and no soil pH; `minimum_temperature` was on the original model
but does not appear in the rescued field list; and it is a *crop* database, so
it will hit basil and lemon and miss the ornamentals and houseplants that make
up most of the Register.

## Consequences

- D gains one real connector (Trefle) and one optional seed (OpenFarm rescue).
- `light_label` moves from unknown to attested for most species. Soil pH and
  minimum temperature move too, if the units check passes.
- `water_k_c` is **not** closed by any of this. ADR 0013 handles it.
- Attribution is now a shipping requirement: `Data: Trefle.io (CC-BY-4.0)` with
  a link must appear wherever Trefle-derived values are displayed. That is a UI
  obligation on J, not only a database field.
