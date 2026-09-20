"""Request bodies and response shaping for the inventory API.

The request models are the contract's ``SpecimenCreate``, ``SpecimenUpdate``
and ``LocationCreate``, field for field. The serialisers below are the only
place a stored row becomes a contract response, so the mock path and the live
path cannot answer in different shapes — which is the whole point of the
fixture stack other workstreams build against.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from inventory.domain import display_name, normalise_sun_exposure

LocationKind = Literal["area", "zone", "bed", "room", "shelf"]
SunExposure = Literal["full_sun", "part_sun", "part_shade", "full_shade", "unknown"]
SpecimenStatus = Literal[
    "thriving",
    "struggling",
    "dormant",
    "overwintering",
    "lost",
    "given_away",
    "archived",
]

#: What the S0 mock reported for rows that predate real timestamps. Fixture
#: specimens keep it so the Register does not appear to have been created today.
FIXTURE_CREATED_AT = "2026-09-20T00:00:00Z"


class SpecimenCreate(BaseModel):
    """Adding a plant: a name, optionally a confirmed match, optionally a pin.

    ``name`` is what the keeper typed. Resolution to a species is Workstream D's
    job and runs in the background — a create never waits on it.
    """

    name: str = Field(min_length=1, max_length=200)
    species_id: UUID | None = None
    image_key: str | None = None
    nickname: str | None = None
    cultivar: str | None = None
    location_id: UUID | None = None
    in_container: bool = True
    container_litres: float | None = Field(default=None, gt=0)
    count: int = Field(default=1, ge=1)
    acquired_on: date | None = None

    @field_validator("name", "nickname", "cultivar", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class SpecimenUpdate(BaseModel):
    """Every field optional, and ``None`` means "clear it", not "leave it".

    The router reads this with ``exclude_unset=True`` so an omitted field and an
    explicit null are told apart.
    """

    nickname: str | None = None
    cultivar: str | None = None
    location_id: UUID | None = None
    in_container: bool | None = None
    container_litres: float | None = Field(default=None, gt=0)
    soil_note: str | None = None
    status: SpecimenStatus | None = None
    notes: str | None = None
    water_k_c_override: float | None = None
    water_interval_days_override: int | None = None
    min_temp_c_override: float | None = None

    @field_validator("nickname", "cultivar", "soil_note", "notes", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class LocationCreate(BaseModel):
    """Also the PATCH body — the contract points both operations at this schema.

    ``is_covered`` is what makes rain stop at a porch roof and ``is_outdoor`` is
    what keeps a houseplant out of the frost alerts, so both are stated rather
    than guessed.
    """

    site_id: UUID | None = None
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    kind: LocationKind
    is_outdoor: bool
    is_covered: bool = False
    sun_exposure: SunExposure | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return (
            value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
    if isinstance(value, date):
        return value.isoformat()
    return value


def location_out(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """A stored location as the contract's ``Location``."""
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "site_id": str(row["site_id"]) if row.get("site_id") else None,
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "name": row["name"],
        "kind": row["kind"],
        "is_outdoor": bool(row.get("is_outdoor", False)),
        "is_covered": bool(row.get("is_covered", False)),
        "sun_exposure": normalise_sun_exposure(row.get("sun_exposure")),
        "map_layer_id": str(row["map_layer_id"]) if row.get("map_layer_id") else None,
        "boundary_px": row.get("boundary_px"),
        "specimen_count": int(row.get("specimen_count", 0)),
    }


def species_brief(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """A stored species as the contract's ``SpeciesBrief``."""
    if row is None:
        return None
    common = row.get("common_names") or []
    return {
        "id": str(row["id"]),
        "accepted_name": row["accepted_name"],
        "common_name": (common[0] if common else row.get("common_name")),
        "family": row.get("family"),
    }


def specimen_out(row: dict[str, Any]) -> dict[str, Any]:
    """A stored specimen, its location and its species, as ``Specimen``.

    ``row`` carries the joined ``location`` and ``species`` records; the
    repositories hydrate them so the shape is built in one pass here.
    """
    species = row.get("species")
    return {
        "id": str(row["id"]),
        "display_name": display_name(row.get("nickname"), species),
        "nickname": row.get("nickname"),
        "cultivar": row.get("cultivar"),
        "species": species_brief(species),
        "is_group": bool(row.get("is_group", False)),
        "count": int(row.get("count", 1)),
        "location": location_out(row.get("location")),
        "map_layer_id": str(row["map_layer_id"]) if row.get("map_layer_id") else None,
        "pin_px": row.get("pin_px"),
        "is_outdoor": bool(row.get("is_outdoor", False)),
        "in_container": bool(row.get("in_container", True)),
        "container_litres": row.get("container_litres"),
        "soil_note": row.get("soil_note"),
        "acquired_on": _iso(row.get("acquired_on")),
        "provenance": row.get("provenance"),
        "status": row.get("status", "thriving"),
        "primary_photo_url": row.get("primary_photo_url"),
        "next_task": row.get("next_task"),
        "created_at": _iso(row.get("created_at")) or FIXTURE_CREATED_AT,
    }
