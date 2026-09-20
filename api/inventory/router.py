"""Specimens, locations and members.

Owner: Workstream C. S1 made this database-backed: the handlers below are thin,
and the work happens in ``inventory.repository`` — ``FixtureRepository`` when
``MOH_MOCK_MODE=true``, ``DatabaseRepository`` when a Postgres is attached. Both
answer the same protocol and both serialise through ``inventory.schemas``, so
the shapes the contract fixes in ``contracts/openapi/openapi.yaml`` are built in
exactly one place.

The ``/species`` endpoints at the foot of the file belong to Workstream D
(``x-workstream: D``); they are still the S0 fixture mock and are left alone.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app import fixtures
from inventory import enrichment
from inventory.repository import (
    InventoryRepository,
    SpecimenQuery,
    UnknownLocationError,
    UnknownSpeciesError,
    get_repository,
)
from inventory.schemas import (
    LocationCreate,
    SpecimenCreate,
    SpecimenUpdate,
    location_out,
    specimen_out,
)

router = APIRouter(tags=["inventory"])

Repo = Depends(get_repository)


def _offset_from(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(cursor)
    except ValueError:
        raise HTTPException(status_code=422, detail="Malformed cursor") from None
    if offset < 0:
        raise HTTPException(status_code=422, detail="Malformed cursor")
    return offset


# ------------------------------------------------------------------ specimens


@router.get("/specimens")
async def list_specimens(
    q: str | None = None,
    location_id: str | None = None,
    outdoor: bool | None = None,
    status_: str | None = Query(default=None, alias="status"),
    toxic_to_pets: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    repo: InventoryRepository = Repo,
) -> dict[str, Any]:
    """The Register. Archived plants are kept out unless asked for by status."""
    page = await repo.list_specimens(
        SpecimenQuery(
            q=q,
            location_id=location_id,
            outdoor=outdoor,
            status=status_,
            toxic_to_pets=toxic_to_pets,
            limit=limit,
            offset=_offset_from(cursor),
        )
    )
    return {
        "items": [specimen_out(row) for row in page.items],
        "next_cursor": page.next_cursor,
        "total": page.total,
    }


@router.post("/specimens", status_code=status.HTTP_201_CREATED)
async def create_specimen(
    body: SpecimenCreate,
    repo: InventoryRepository = Repo,
) -> dict[str, Any]:
    """Add a plant by name.

    The typed name is matched against the species already known; if nothing
    matches, the name becomes the specimen's nickname so it appears in the
    Register under what the keeper actually typed, and resolution is left to
    Workstream D's queue. The response never waits on that.
    """
    species_id: str | None = str(body.species_id) if body.species_id else None
    if species_id is None:
        species_id = await repo.resolve_species_by_name(body.name)

    data = body.model_dump(exclude={"name", "image_key"})
    data["species_id"] = species_id
    # An unmatched name has nowhere else to live in the frozen schema; see the
    # PR notes. A matched one leaves the nickname empty so the display name
    # falls through to the common name, as the contract describes.
    data["nickname"] = body.nickname or (None if species_id else body.name)

    try:
        row = await repo.create_specimen(data)
    except UnknownLocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnknownSpeciesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await enrichment.queue(
        enrichment.EnrichmentRequest(
            specimen_id=str(row["id"]),
            typed_name=body.name,
            species_id=species_id,
            image_key=body.image_key,
            queued_at=datetime.now(UTC),
        )
    )
    return specimen_out(row)


@router.get("/specimens/{specimen_id}")
async def get_specimen(
    specimen_id: str, repo: InventoryRepository = Repo
) -> dict[str, Any]:
    row = await repo.get_specimen(specimen_id)
    if not row:
        raise HTTPException(status_code=404, detail="No such specimen")
    return specimen_out(row)


@router.patch("/specimens/{specimen_id}")
async def update_specimen(
    specimen_id: str,
    body: SpecimenUpdate,
    repo: InventoryRepository = Repo,
) -> dict[str, Any]:
    """Edit a plant. Omitted fields are left alone; an explicit null clears one.

    Moving a specimen to another location re-derives ``is_outdoor`` from it, so
    a plant brought in for the winter leaves the frost alerts the moment it is
    moved on the Register rather than the next time something recomputes.
    """
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        row = await repo.get_specimen(specimen_id)
        if not row:
            raise HTTPException(status_code=404, detail="No such specimen")
        return specimen_out(row)

    try:
        row = await repo.update_specimen(specimen_id, changes)
    except UnknownLocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="No such specimen")
    return specimen_out(row)


@router.delete("/specimens/{specimen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_specimen(
    specimen_id: str, repo: InventoryRepository = Repo
) -> Response:
    """Archive, do not delete. A lost plant is part of the record.

    The row keeps its logs, its photos and its history; it simply stops being
    listed by the Register unless asked for with ``?status=archived``.
    """
    if not await repo.archive_specimen(specimen_id):
        raise HTTPException(status_code=404, detail="No such specimen")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/specimens/{specimen_id}/photos")
async def list_photos(specimen_id: str) -> list[dict[str, Any]]:
    """S2 (C): the growth log. Empty until then."""
    return []


@router.get("/specimens/{specimen_id}/log")
async def list_log_entries(specimen_id: str) -> list[dict[str, Any]]:
    """S2 (C): growth, pest, disease and repotting entries. Empty until then."""
    return []


# ------------------------------------------------------------------ locations


@router.get("/locations")
async def list_locations(
    site_id: str | None = None,
    outdoor: bool | None = None,
    repo: InventoryRepository = Repo,
) -> list[dict[str, Any]]:
    rows = await repo.list_locations(site_id=site_id, outdoor=outdoor)
    return [out for out in (location_out(r) for r in rows) if out is not None]


@router.post("/locations", status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate, repo: InventoryRepository = Repo
) -> dict[str, Any]:
    """Add a place: a room, a shelf, a bed, or a zone drawn on a plan.

    ``is_outdoor`` and ``is_covered`` are the two flags the weather engines
    read — a covered outdoor zone collects no rain, an indoor one raises no
    frost alerts — so both are recorded here rather than inferred later.
    """
    try:
        row = await repo.create_location(body.model_dump())
    except (UnknownLocationError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    out = location_out(row)
    assert out is not None
    return out


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: str,
    body: LocationCreate,
    repo: InventoryRepository = Repo,
) -> dict[str, Any]:
    """Edit a place.

    Changing ``is_outdoor`` carries every specimen standing in this location
    with it, in one transaction: the denormalised flag on a specimen may never
    disagree with its location's.
    """
    try:
        row = await repo.update_location(location_id, body.model_dump())
    except UnknownLocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="No such location")
    out = location_out(row)
    assert out is not None
    return out


# -------------------------------------------------------------------- members


@router.get("/members")
async def list_members(repo: InventoryRepository = Repo) -> list[dict[str, Any]]:
    rows = await repo.list_members()
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "role": row["role"],
            "notify_prefs": row.get("notify_prefs") or {},
        }
        for row in rows
    ]


# ------------------------------------------- species (Workstream D's, S0 mock)


@router.get("/species")
async def list_species(q: str | None = None) -> list[dict[str, Any]]:
    rows = fixtures.species()
    if q:
        needle = q.casefold()
        rows = [
            r
            for r in rows
            if needle in r["accepted_name"].casefold()
            or any(needle in c.casefold() for c in r.get("common_names", []))
        ]
    return [_species_out(r) for r in rows]


@router.get("/species/{species_id}")
async def get_species(species_id: str) -> dict[str, Any]:
    row = fixtures.by_id(fixtures.species(), species_id)
    if not row:
        raise HTTPException(status_code=404, detail="No such species")
    return _species_out(row)


@router.get("/species/{species_id}/care-values")
async def list_care_values(species_id: str) -> list[dict[str, Any]]:
    row = fixtures.by_id(fixtures.species(), species_id)
    if not row:
        raise HTTPException(status_code=404, detail="No such species")
    out = []
    for cv in row.get("care_values", []):
        source = fixtures.by_id(fixtures.sources(), cv.get("source_id") or "")
        out.append(
            {
                "field": cv["field"],
                "value": cv["value"],
                "unit": cv.get("unit"),
                "source": source,
                "confidence": cv["confidence"],
                "is_user_override": False,
                "note": cv.get("note"),
            }
        )
    return out


def _species_out(row: dict[str, Any]) -> dict[str, Any]:
    cited = {cv.get("source_id") for cv in row.get("care_values", [])} - {None}
    return {
        **{k: v for k, v in row.items() if k != "care_values"},
        "common_name": (row.get("common_names") or [None])[0],
        "sources": [s for s in fixtures.sources() if s["id"] in cited],
    }
