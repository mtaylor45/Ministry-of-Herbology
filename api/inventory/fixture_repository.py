"""The Register, in memory, seeded from ``fixtures/``.

This is what ``MOH_MOCK_MODE=true`` serves, and rule 3 makes it load-bearing:
J, H and G build against it, and the scenario suite reads the same fixture
data, so the mocks and the tests cannot drift apart.

It is writable. A mock that can only be read stops being useful the moment the
feature under test is "add a plant", so creates, edits and archives all work
here — they just live for as long as the process does.
"""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app import fixtures
from inventory.domain import (
    ARCHIVED_STATUS,
    display_name,
    is_group_for,
    is_outdoor_for,
    normalise_sun_exposure,
    search_haystack,
)
from inventory.repository import (
    Record,
    SpecimenPage,
    SpecimenQuery,
    UnknownLocationError,
    UnknownSpeciesError,
)

_LOCK = threading.Lock()
_INSTANCE: FixtureRepository | None = None


def fixture_repository() -> FixtureRepository:
    """The process-wide mock store, so writes outlive the request that made them."""
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = FixtureRepository()
        return _INSTANCE


def reset_fixture_repository() -> FixtureRepository:
    """Reload from ``fixtures/``. For tests, and for a demo that wants a clean slate."""
    global _INSTANCE
    with _LOCK:
        _INSTANCE = FixtureRepository()
        return _INSTANCE


class FixtureRepository:
    """An in-memory inventory. Ordering is fixture order, then order of arrival."""

    def __init__(self) -> None:
        # Deep copies: ``app.fixtures`` caches the parsed JSON, and a mock that
        # mutated it would rewrite the fixture data for every other reader.
        self._locations: list[Record] = copy.deepcopy(fixtures.locations())
        self._specimens: list[Record] = copy.deepcopy(fixtures.specimens())
        self._species: list[Record] = copy.deepcopy(fixtures.species())
        self._members: list[Record] = [
            {
                "id": "01890050-0000-7000-8000-000000000001",
                "name": "Keeper",
                "role": "keeper",
                "notify_prefs": {},
            },
        ]

    # ---------------------------------------------------------------- helpers

    def _species_by_id(self, species_id: str | None) -> Record | None:
        if not species_id:
            return None
        return next((s for s in self._species if s["id"] == str(species_id)), None)

    def _location_by_id(self, location_id: str | None) -> Record | None:
        if not location_id:
            return None
        return next((r for r in self._locations if r["id"] == str(location_id)), None)

    def _specimen_count(self, location_id: str) -> int:
        return sum(
            1
            for s in self._specimens
            if s.get("location_id") == location_id and not s.get("archived_at")
        )

    def _hydrate_location(self, row: Record) -> Record:
        return {**row, "specimen_count": self._specimen_count(row["id"])}

    def _hydrate(self, row: Record) -> Record:
        location = self._location_by_id(row.get("location_id"))
        return {
            **row,
            "location": self._hydrate_location(location) if location else None,
            "species": self._species_by_id(row.get("species_id")),
        }

    def _require_location(self, location_id: Any) -> Record:
        location = self._location_by_id(location_id)
        if location is None:
            raise UnknownLocationError(location_id)
        return location

    # -------------------------------------------------------------- specimens

    async def list_specimens(self, query: SpecimenQuery) -> SpecimenPage:
        rows = self._specimens
        # Archive, do not delete: archived plants stay in the record but leave
        # the Register, unless the Register is explicitly asked for them.
        if query.status != ARCHIVED_STATUS:
            rows = [r for r in rows if not r.get("archived_at")]
        if query.location_id:
            rows = [r for r in rows if r.get("location_id") == query.location_id]
        if query.outdoor is not None:
            rows = [r for r in rows if bool(r.get("is_outdoor")) is query.outdoor]
        if query.status:
            rows = [r for r in rows if r.get("status") == query.status]
        if query.toxic_to_pets is not None:
            rows = [
                r
                for r in rows
                if bool(
                    (self._species_by_id(r.get("species_id")) or {}).get(
                        "toxic_to_pets"
                    )
                )
                is query.toxic_to_pets
            ]
        if query.q:
            needle = query.q.casefold()
            rows = [r for r in rows if needle in self._haystack(r)]

        total = len(rows)
        window = rows[query.offset : query.offset + query.limit]
        end = query.offset + len(window)
        return SpecimenPage(
            items=[self._hydrate(r) for r in window],
            total=total,
            next_cursor=str(end) if end < total else None,
        )

    def _haystack(self, row: Record) -> str:
        species = self._species_by_id(row.get("species_id"))
        return search_haystack(display_name(row.get("nickname"), species), species)

    async def get_specimen(self, specimen_id: str) -> Record | None:
        row = next((r for r in self._specimens if r["id"] == specimen_id), None)
        return self._hydrate(row) if row else None

    async def create_specimen(self, data: dict[str, Any]) -> Record:
        location = (
            self._require_location(data["location_id"])
            if data.get("location_id")
            else None
        )
        species_id = data.get("species_id")
        if species_id and self._species_by_id(str(species_id)) is None:
            raise UnknownSpeciesError(species_id)

        count = int(data.get("count") or 1)
        row: Record = {
            "id": str(uuid.uuid4()),
            "species_id": str(species_id) if species_id else None,
            "nickname": data.get("nickname"),
            "cultivar": data.get("cultivar"),
            "is_group": is_group_for(count),
            "count": count,
            "location_id": location["id"] if location else None,
            "map_layer_id": None,
            "pin_px": None,
            "is_outdoor": is_outdoor_for(location),
            "in_container": bool(data.get("in_container", True)),
            "container_litres": data.get("container_litres"),
            "soil_note": None,
            "acquired_on": data.get("acquired_on"),
            "provenance": data.get("provenance"),
            "status": "thriving",
            "notes": None,
            "created_at": datetime.now(UTC),
            "archived_at": None,
        }
        self._specimens.append(row)
        return self._hydrate(row)

    async def update_specimen(
        self, specimen_id: str, changes: dict[str, Any]
    ) -> Record | None:
        row = next((r for r in self._specimens if r["id"] == specimen_id), None)
        if row is None:
            return None
        if "location_id" in changes:
            location = (
                self._require_location(changes["location_id"])
                if changes["location_id"]
                else None
            )
            row["location_id"] = location["id"] if location else None
            # The denormalised flag follows the move, always.
            row["is_outdoor"] = is_outdoor_for(location)
        for key, value in changes.items():
            if key == "location_id":
                continue
            row[key] = str(value) if isinstance(value, uuid.UUID) else value
        if "status" in changes:
            # Status and the archive date stay in step, in both directions:
            # archiving records the day, un-archiving returns it to the Register.
            if changes["status"] == ARCHIVED_STATUS:
                row["archived_at"] = row.get("archived_at") or datetime.now(UTC)
            else:
                row["archived_at"] = None
        return self._hydrate(row)

    async def archive_specimen(self, specimen_id: str) -> bool:
        row = next((r for r in self._specimens if r["id"] == specimen_id), None)
        if row is None:
            return False
        row.setdefault("archived_at", None)
        if not row["archived_at"]:
            row["archived_at"] = datetime.now(UTC)
        row["status"] = ARCHIVED_STATUS
        return True

    # -------------------------------------------------------------- locations

    async def list_locations(
        self, site_id: str | None = None, outdoor: bool | None = None
    ) -> list[Record]:
        rows = [r for r in self._locations if not r.get("archived_at")]
        if site_id:
            rows = [r for r in rows if r.get("site_id") == site_id]
        if outdoor is not None:
            rows = [r for r in rows if bool(r.get("is_outdoor")) is outdoor]
        return [self._hydrate_location(r) for r in rows]

    async def get_location(self, location_id: str) -> Record | None:
        row = self._location_by_id(location_id)
        return self._hydrate_location(row) if row else None

    async def create_location(self, data: dict[str, Any]) -> Record:
        if data.get("parent_id"):
            self._require_location(data["parent_id"])
        site_id = data.get("site_id") or fixtures.site()["id"]
        row: Record = {
            "id": str(uuid.uuid4()),
            "site_id": str(site_id),
            "parent_id": str(data["parent_id"]) if data.get("parent_id") else None,
            "name": data["name"],
            "kind": data["kind"],
            "is_outdoor": bool(data["is_outdoor"]),
            "is_covered": bool(data.get("is_covered", False)),
            "sun_exposure": normalise_sun_exposure(data.get("sun_exposure")),
            "map_layer_id": None,
            "boundary_px": None,
            "created_at": datetime.now(UTC),
            "archived_at": None,
        }
        self._locations.append(row)
        return self._hydrate_location(row)

    async def update_location(
        self, location_id: str, data: dict[str, Any]
    ) -> Record | None:
        row = self._location_by_id(location_id)
        if row is None:
            return None
        if data.get("parent_id"):
            self._require_location(data["parent_id"])
        row.update(
            {
                "name": data["name"],
                "kind": data["kind"],
                "is_outdoor": bool(data["is_outdoor"]),
                "is_covered": bool(data.get("is_covered", False)),
                "sun_exposure": normalise_sun_exposure(data.get("sun_exposure")),
            }
        )
        if data.get("site_id"):
            row["site_id"] = str(data["site_id"])
        if "parent_id" in data:
            row["parent_id"] = str(data["parent_id"]) if data["parent_id"] else None
        # Moving a porch indoors moves everything standing on it: the specimens'
        # denormalised flag is not allowed to lag behind their location's.
        for specimen in self._specimens:
            if specimen.get("location_id") == row["id"]:
                specimen["is_outdoor"] = row["is_outdoor"]
        return self._hydrate_location(row)

    # ---------------------------------------------------------------- members

    async def list_members(self) -> list[Record]:
        return [dict(m) for m in self._members]

    # ------------------------------------------------------------- resolution

    async def resolve_species_by_name(self, name: str) -> str | None:
        needle = name.casefold().strip()
        for row in self._species:
            if str(row.get("accepted_name", "")).casefold() == needle:
                return str(row["id"])
        for row in self._species:
            if any(str(c).casefold() == needle for c in row.get("common_names") or []):
                return str(row["id"])
        return None
