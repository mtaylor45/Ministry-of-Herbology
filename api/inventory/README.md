# Inventory & Core API — Workstream C

Specimens, locations, zones, groups and household members. Implements the
`inventory` paths of `contracts/openapi/openapi.yaml`; the contract is frozen,
so nothing here changes a response shape.

## Layout

| Module | What it does |
| --- | --- |
| `router.py` | HTTP only. Validates, delegates, serialises. |
| `schemas.py` | The contract's request bodies, and the one place a row becomes a response. |
| `domain.py` | The invariants, independent of storage. |
| `repository.py` | The storage protocol, and which implementation answers. |
| `fixture_repository.py` | In-memory Register seeded from `fixtures/` — mock mode. |
| `database_repository.py` | SQLAlchemy Core on Postgres — live mode. |
| `tables.py` | Core table metadata mirroring `contracts/schema/001_init.sql`. |
| `db.py` | The lazily created async engine. |
| `enrichment.py` | Hands a new plant to Workstream D's queue without blocking on it. |

## Two modes, one protocol

`MOH_MOCK_MODE=true` (the default, ADR 0003) serves the whole API from
`fixtures/`, including writes — every other workstream runs the stack this way
and a create must work there too, or "add a plant" cannot be demonstrated
without a database. Set it false and `MOH_DATABASE_URL` and the same router
talks to Postgres. Both paths serialise through `schemas.py`, so they cannot
answer in different shapes.

Mock-mode writes live in the process. Restart the API and the Register is back
to the fixtures.

## The rules this code exists to keep

- **`specimen.is_outdoor` is derived, never supplied.** It comes from the
  specimen's location on create, is re-derived on a move, and is carried along
  when a location's own flag changes — in one transaction, so the two are never
  seen disagreeing. The frost guard reads it; a stale flag moves the wrong
  plants. `tests/contract/test_fixtures.py` asserts the same invariant on
  fixture data.
- **`is_covered` and `sun_exposure` are recorded, not inferred.** A covered
  outdoor zone collects no rain. A location that does not say gets
  `sun_exposure: unknown` rather than null.
- **A group is one specimen with a `count`.** A lavender hedge is tended once.
- **Archive, do not delete.** `DELETE /specimens/{id}` sets `archived_at` and
  `status: archived`. The row keeps its history; it leaves the Register unless
  asked for with `?status=archived`, and a PATCH back to another status
  restores it. `lost` and `given_away` are *not* archived — they stay listed.
- **Never block on enrichment.** A typed name is matched against the species
  already known and the rest is queued for Workstream D.

## Tests

They live in `tests/` inside this package, because rule 2 puts the repository's
top-level `tests/` in Workstream L's hands.

```
.venv/bin/python -m pytest api/inventory -q          # no database needed
```

The live-Postgres suite skips unless it is given a database it may create
tables in:

```
MOH_TEST_DATABASE_URL=postgresql+asyncpg://herbology@127.0.0.1:5432/herbology_test \
  .venv/bin/python -m pytest api/inventory -q
```

It cuts its tables out of `contracts/schema/001_init.sql` rather than retyping
them, so a column that moves in the frozen schema breaks the tests instead of
quietly passing them.
