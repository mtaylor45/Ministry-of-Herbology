# ADR 0006 — Open decisions

- **Status:** Proposed — awaiting the maintainer
- **Date:** 2026-09-20
- **Workstream:** A

These block specific sprints. Each becomes its own accepted ADR when answered.

| # | Question | Needed by | Default if unanswered |
| --- | --- | --- | --- |
| 1 | Are paid APIs acceptable? Perenual tier, image generation, the one-time Google SDM fee (~$5). | S2 | Free tiers and public-domain sources only; Perenual and generated plates are disabled behind a feature flag. |
| 2 | Nest route: Home Assistant's Nest integration (SDM API) or Matter? | S3 | Build the HA adapter generically against HA entity ids, so either route works without a code change. |
| 3 | Survey format: PDF plat, CAD file, or satellite image only? | S7 | Support a raster image (PNG/JPEG) plus two-point georeferencing; PDF is rasterised on upload; CAD is out. |
| 4 | Separate logins per household member, or one shared login with a member picker? | S4 | One shared session with a member picker for attribution, which is reversible; per-member auth is additive later. |
| 5 | Any irrigation hardware to control (e.g. Rachio via HA)? | S9 / v1.1 | Out of scope for v1.0, as the plan states. |

The defaults above are what the workstreams build against until told otherwise —
each is chosen to be the cheapest to reverse, not the most capable.
