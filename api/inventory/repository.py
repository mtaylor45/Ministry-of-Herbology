"""The storage seam.

Two implementations answer the same protocol: ``FixtureRepository`` keeps the
whole Register in memory seeded from ``fixtures/`` (``MOH_MOCK_MODE=true``, how
every other workstream runs the stack), and ``DatabaseRepository`` talks to
Postgres. The router knows only this interface, so neither path can quietly
grow behaviour the other lacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.settings import get_settings

#: A stored row, hydrated with its joined records. Specimens carry ``location``
#: and ``species``; locations carry ``specimen_count``.
Record = dict[str, Any]


class UnknownLocationError(LookupError):
    """A write referenced a location that does not exist. The router answers 422."""

    def __init__(self, location_id: Any) -> None:
        super().__init__(f"No such location: {location_id}")
        self.location_id = str(location_id)


class UnknownSpeciesError(LookupError):
    """A create named a ``species_id`` nothing matches. The router answers 422."""

    def __init__(self, species_id: Any) -> None:
        super().__init__(f"No such species: {species_id}")
        self.species_id = str(species_id)


@dataclass(frozen=True, slots=True)
class SpecimenQuery:
    """The Register's filters, as the contract declares them on ``GET /specimens``."""

    q: str | None = None
    location_id: str | None = None
    outdoor: bool | None = None
    status: str | None = None
    toxic_to_pets: bool | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class SpecimenPage:
    items: list[Record] = field(default_factory=list)
    total: int = 0
    next_cursor: str | None = None


class InventoryRepository(Protocol):
    """Everything the inventory router needs from storage."""

    async def list_specimens(self, query: SpecimenQuery) -> SpecimenPage: ...

    async def get_specimen(self, specimen_id: str) -> Record | None: ...

    async def create_specimen(self, data: dict[str, Any]) -> Record: ...

    async def update_specimen(
        self, specimen_id: str, changes: dict[str, Any]
    ) -> Record | None: ...

    async def archive_specimen(self, specimen_id: str) -> bool: ...

    async def list_locations(
        self, site_id: str | None = None, outdoor: bool | None = None
    ) -> list[Record]: ...

    async def get_location(self, location_id: str) -> Record | None: ...

    async def create_location(self, data: dict[str, Any]) -> Record: ...

    async def update_location(
        self, location_id: str, data: dict[str, Any]
    ) -> Record | None: ...

    async def list_members(self) -> list[Record]: ...

    async def resolve_species_by_name(self, name: str) -> str | None: ...


async def get_repository() -> InventoryRepository:
    """FastAPI dependency: fixtures when mocking, Postgres when not.

    Mock mode is the default (ADR 0003) and stays a complete, writable API —
    ``POST /specimens`` works there too, so the Register can be demonstrated
    end to end without a database attached.
    """
    if get_settings().mock_mode:
        from inventory.fixture_repository import fixture_repository

        return fixture_repository()

    from inventory.database_repository import DatabaseRepository
    from inventory.db import get_engine

    return DatabaseRepository(get_engine())
