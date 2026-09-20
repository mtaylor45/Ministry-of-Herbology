"""Specimens, locations and members.

Owner: Workstream C. This is the S0 mock: it answers the contract from
``fixtures/`` so that J, H and G can build against a real HTTP surface. C
replaces the bodies with database-backed ones in S1; the response shapes are
fixed by ``contracts/openapi/openapi.yaml`` and must not change here.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import fixtures

router = APIRouter(tags=["inventory"])


def _location_out(row: dict[str, Any]) -> dict[str, Any]:
    count = sum(1 for s in fixtures.specimens() if s.get("location_id") == row["id"])
    return {**row, "specimen_count": count}


def _species_brief(species_id: str | None) -> dict[str, Any] | None:
    sp = fixtures.by_id(fixtures.species(), species_id or "")
    if not sp:
        return None
    return {
        "id": sp["id"],
        "accepted_name": sp["accepted_name"],
        "common_name": (sp.get("common_names") or [None])[0],
        "family": sp.get("family"),
    }


def _specimen_out(row: dict[str, Any]) -> dict[str, Any]:
    location = fixtures.by_id(fixtures.locations(), row.get("location_id") or "")
    return {
        "id": row["id"],
        "display_name": fixtures.display_name(row),
        "nickname": row.get("nickname"),
        "cultivar": row.get("cultivar"),
        "species": _species_brief(row.get("species_id")),
        "is_group": row.get("is_group", False),
        "count": row.get("count", 1),
        "location": _location_out(location) if location else None,
        "map_layer_id": row.get("map_layer_id"),
        "pin_px": row.get("pin_px"),
        "is_outdoor": row.get("is_outdoor", False),
        "in_container": row.get("in_container", True),
        "container_litres": row.get("container_litres"),
        "soil_note": row.get("soil_note"),
        "acquired_on": row.get("acquired_on"),
        "provenance": row.get("provenance"),
        "status": row.get("status", "thriving"),
        "primary_photo_url": None,
        "next_task": None,
        "created_at": "2026-09-20T00:00:00Z",
    }


@router.get("/specimens")
async def list_specimens(
    q: str | None = None,
    location_id: str | None = None,
    outdoor: bool | None = None,
    status: str | None = None,
    toxic_to_pets: bool | None = None,
    limit: int = Query(50, le=200),
) -> dict[str, Any]:
    rows = fixtures.specimens()
    if location_id:
        rows = [r for r in rows if r.get("location_id") == location_id]
    if outdoor is not None:
        rows = [r for r in rows if r.get("is_outdoor") is outdoor]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if toxic_to_pets is not None:

        def _toxic(r: dict[str, Any]) -> bool:
            sp = fixtures.by_id(fixtures.species(), r.get("species_id") or "")
            return bool(sp and sp.get("toxic_to_pets"))

        rows = [r for r in rows if _toxic(r) is toxic_to_pets]
    if q:
        needle = q.casefold()
        rows = [r for r in rows if needle in fixtures.display_name(r).casefold()]
    items = [_specimen_out(r) for r in rows[:limit]]
    return {"items": items, "next_cursor": None, "total": len(rows)}


@router.get("/specimens/{specimen_id}")
async def get_specimen(specimen_id: str) -> dict[str, Any]:
    row = fixtures.by_id(fixtures.specimens(), specimen_id)
    if not row:
        raise HTTPException(status_code=404, detail="No such specimen")
    return _specimen_out(row)


@router.get("/specimens/{specimen_id}/photos")
async def list_photos(specimen_id: str) -> list[dict[str, Any]]:
    return []


@router.get("/specimens/{specimen_id}/log")
async def list_log_entries(specimen_id: str) -> list[dict[str, Any]]:
    return []


@router.get("/locations")
async def list_locations(
    site_id: str | None = None, outdoor: bool | None = None
) -> list[dict[str, Any]]:
    rows = fixtures.locations()
    if site_id:
        rows = [r for r in rows if r.get("site_id") == site_id]
    if outdoor is not None:
        rows = [r for r in rows if r.get("is_outdoor") is outdoor]
    return [_location_out(r) for r in rows]


@router.get("/members")
async def list_members() -> list[dict[str, Any]]:
    return [
        {
            "id": "01890050-0000-7000-8000-000000000001",
            "name": "Keeper",
            "role": "keeper",
            "notify_prefs": {},
        },
    ]


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
