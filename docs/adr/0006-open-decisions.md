# ADR 0006 — Open decisions

- **Status:** Resolved except decision 3 (survey format, wanted by S7)
- **Date:** 2026-09-20
- **Workstream:** A

These block specific sprints. Each becomes its own accepted ADR when answered.

| # | Question | Needed by | Default if unanswered |
| --- | --- | --- | --- |
| 1 | ~~Are paid APIs acceptable?~~ **Answered: free sources only.** See ADR 0007. | S2 | — |
| 2 | ~~Nest route: SDM API or Matter?~~ **Answered: neither — indoor conditions come from Home Assistant.** See ADR 0009. | S3 | — |
| 3 | Survey format: PDF plat, CAD file, or satellite image only? | S7 | Support a raster image (PNG/JPEG) plus two-point georeferencing; PDF is rasterised on upload; CAD is out. |
| 4 | ~~Separate logins per member, or a shared login with a member picker?~~ **Answered: shared login with a member picker.** See ADR 0008. | S4 | — |
| 5 | ~~Any irrigation hardware to control?~~ **Answered: none today, and no soil-moisture hardware either — keep the seams.** See ADR 0010. | S9 / v1.1 | — |

The defaults above are what the workstreams build against until told otherwise —
each is chosen to be the cheapest to reverse, not the most capable. Decisions 1
and 4 came back confirming their defaults (ADRs 0007 and 0008); decisions 2 and
5 came back narrower than their defaults (ADRs 0009 and 0010). Only decision 3
remains, and S7 is a long way off.
