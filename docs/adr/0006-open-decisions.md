# ADR 0006 — Open decisions

- **Status:** Partially resolved — decisions 1 and 4 answered; 2, 3 and 5 still open
- **Date:** 2026-09-20
- **Workstream:** A

These block specific sprints. Each becomes its own accepted ADR when answered.

| # | Question | Needed by | Default if unanswered |
| --- | --- | --- | --- |
| 1 | ~~Are paid APIs acceptable?~~ **Answered: free sources only.** See ADR 0007. | S2 | — |
| 2 | Nest route: Home Assistant's Nest integration (SDM API) or Matter? | S3 | Build the HA adapter generically against HA entity ids, so either route works without a code change. |
| 3 | Survey format: PDF plat, CAD file, or satellite image only? | S7 | Support a raster image (PNG/JPEG) plus two-point georeferencing; PDF is rasterised on upload; CAD is out. |
| 4 | ~~Separate logins per member, or a shared login with a member picker?~~ **Answered: shared login with a member picker.** See ADR 0008. | S4 | — |
| 5 | Any irrigation hardware to control (e.g. Rachio via HA)? | S9 / v1.1 | Out of scope for v1.0, as the plan states. |

The defaults above are what the workstreams build against until told otherwise —
each is chosen to be the cheapest to reverse, not the most capable. Decisions 1
and 4 came back confirming their defaults, which are now ADRs 0007 and 0008.
