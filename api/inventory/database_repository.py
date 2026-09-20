"""The live Register, on Postgres.

Same protocol as the fixture store, so the router is unchanged between mock and
live mode. Reads hydrate a page of specimens with two extra queries — one for
locations, one for species — rather than one per row; writes run in a single
transaction so the ``is_outdoor`` invariant cannot be observed half-applied.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from inventory.domain import (
    ARCHIVED_STATUS,
    is_group_for,
    is_outdoor_for,
    normalise_sun_exposure,
)
from inventory.repository import (
    Record,
    SpecimenPage,
    SpecimenQuery,
    UnknownLocationError,
    UnknownSpeciesError,
)
from inventory.tables import (
    SPECIMEN_WRITABLE,
    location,
    member,
    site,
    species,
    specimen,
)


class NoSiteError(LookupError):
    """A location was created before any site existed. The router answers 422."""

    def __init__(self) -> None:
        super().__init__("No site exists yet; create one before adding locations.")


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


#: A location's live specimen count, excluding archived plants. Correlated so it
#: rides along with whichever locations the outer query selected.
_SPECIMEN_COUNT = (
    select(func.count())
    .select_from(specimen)
    .where(specimen.c.location_id == location.c.id, specimen.c.archived_at.is_(None))
    .correlate(location)
    .scalar_subquery()
    .label("specimen_count")
)


class DatabaseRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    # ---------------------------------------------------------------- reading

    async def _locations_by_id(
        self, conn: AsyncConnection, ids: set[Any]
    ) -> dict[Any, Record]:
        if not ids:
            return {}
        rows = await conn.execute(
            select(location, _SPECIMEN_COUNT).where(location.c.id.in_(ids))
        )
        return {r.id: dict(r._mapping) for r in rows}

    async def _species_by_id(
        self, conn: AsyncConnection, ids: set[Any]
    ) -> dict[Any, Record]:
        if not ids:
            return {}
        rows = await conn.execute(select(species).where(species.c.id.in_(ids)))
        return {r.id: dict(r._mapping) for r in rows}

    async def _hydrate(self, conn: AsyncConnection, rows: list[Record]) -> list[Record]:
        locations = await self._locations_by_id(
            conn, {r["location_id"] for r in rows if r.get("location_id")}
        )
        taxa = await self._species_by_id(
            conn, {r["species_id"] for r in rows if r.get("species_id")}
        )
        return [
            {
                **row,
                "location": locations.get(row.get("location_id")),
                "species": taxa.get(row.get("species_id")),
            }
            for row in rows
        ]

    def _filtered(self, query: SpecimenQuery) -> Select[Any]:
        stmt = select(specimen).select_from(
            specimen.outerjoin(species, specimen.c.species_id == species.c.id)
        )
        conditions: list[Any] = []
        # Archive, do not delete: archived plants leave the Register unless the
        # Register asks for them by status.
        if query.status != ARCHIVED_STATUS:
            conditions.append(specimen.c.archived_at.is_(None))
        if query.location_id:
            conditions.append(specimen.c.location_id == _as_uuid(query.location_id))
        if query.outdoor is not None:
            conditions.append(specimen.c.is_outdoor.is_(query.outdoor))
        if query.status:
            conditions.append(specimen.c.status == query.status)
        if query.toxic_to_pets is not None:
            # An unresolved species is not evidence of safety, but it is not a
            # toxicity claim either: it answers "no" and stays visible to "all".
            conditions.append(
                func.coalesce(species.c.toxic_to_pets, False).is_(query.toxic_to_pets)
            )
        if query.q:
            needle = f"%{query.q}%"
            conditions.append(
                or_(
                    specimen.c.nickname.ilike(needle),
                    species.c.accepted_name.ilike(needle),
                    func.array_to_string(species.c.common_names, " ").ilike(needle),
                )
            )
        return stmt.where(and_(*conditions)) if conditions else stmt

    async def list_specimens(self, query: SpecimenQuery) -> SpecimenPage:
        stmt = self._filtered(query)
        async with self._engine.connect() as conn:
            total = await conn.scalar(select(func.count()).select_from(stmt.subquery()))
            rows = await conn.execute(
                stmt.order_by(specimen.c.created_at, specimen.c.id)
                .offset(query.offset)
                .limit(query.limit)
            )
            items = await self._hydrate(conn, [dict(r._mapping) for r in rows])
        end = query.offset + len(items)
        return SpecimenPage(
            items=items,
            total=int(total or 0),
            next_cursor=str(end) if end < int(total or 0) else None,
        )

    async def get_specimen(self, specimen_id: str) -> Record | None:
        key = _as_uuid(specimen_id)
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(select(specimen).where(specimen.c.id == key))
            ).first()
            if row is None:
                return None
            return (await self._hydrate(conn, [dict(row._mapping)]))[0]

    # ---------------------------------------------------------------- writing

    async def _require_location(
        self, conn: AsyncConnection, location_id: Any
    ) -> Record:
        row = (
            await conn.execute(
                select(location, _SPECIMEN_COUNT).where(
                    location.c.id == _as_uuid(location_id)
                )
            )
        ).first()
        if row is None:
            raise UnknownLocationError(location_id)
        return dict(row._mapping)

    async def create_specimen(self, data: dict[str, Any]) -> Record:
        async with self._engine.begin() as conn:
            place = (
                await self._require_location(conn, data["location_id"])
                if data.get("location_id")
                else None
            )
            species_id = _as_uuid(data.get("species_id"))
            if species_id is not None:
                known = await conn.scalar(
                    select(species.c.id).where(species.c.id == species_id)
                )
                if known is None:
                    raise UnknownSpeciesError(species_id)

            count = int(data.get("count") or 1)
            values = {
                "id": uuid.uuid4(),
                "species_id": species_id,
                "nickname": data.get("nickname"),
                "cultivar": data.get("cultivar"),
                "is_group": is_group_for(count),
                "count": count,
                "location_id": place["id"] if place else None,
                "is_outdoor": is_outdoor_for(place),
                "in_container": bool(data.get("in_container", True)),
                "container_litres": data.get("container_litres"),
                "acquired_on": data.get("acquired_on"),
                "provenance": data.get("provenance"),
                "status": "thriving",
            }
            row = (
                await conn.execute(
                    specimen.insert().values(**values).returning(specimen)
                )
            ).one()
            return (await self._hydrate(conn, [dict(row._mapping)]))[0]

    async def update_specimen(
        self, specimen_id: str, changes: dict[str, Any]
    ) -> Record | None:
        key = _as_uuid(specimen_id)
        async with self._engine.begin() as conn:
            exists = await conn.scalar(
                select(specimen.c.id).where(specimen.c.id == key)
            )
            if exists is None:
                return None

            values: dict[str, Any] = {
                k: v for k, v in changes.items() if k in SPECIMEN_WRITABLE
            }
            if "location_id" in changes:
                place = (
                    await self._require_location(conn, changes["location_id"])
                    if changes["location_id"]
                    else None
                )
                values["location_id"] = place["id"] if place else None
                # The denormalised flag follows the move, always.
                values["is_outdoor"] = is_outdoor_for(place)
            if values.get("status") == ARCHIVED_STATUS:
                values["archived_at"] = func.coalesce(
                    specimen.c.archived_at, func.now()
                )
            elif "status" in values:
                # Moving a plant off "archived" brings it back to the Register.
                values["archived_at"] = None
            values["updated_at"] = func.now()

            row = (
                await conn.execute(
                    specimen.update()
                    .where(specimen.c.id == key)
                    .values(**values)
                    .returning(specimen)
                )
            ).one()
            return (await self._hydrate(conn, [dict(row._mapping)]))[0]

    async def archive_specimen(self, specimen_id: str) -> bool:
        key = _as_uuid(specimen_id)
        async with self._engine.begin() as conn:
            row = (
                await conn.execute(
                    specimen.update()
                    .where(specimen.c.id == key)
                    .values(
                        # Idempotent: re-archiving does not rewrite the date it
                        # was lost on.
                        archived_at=func.coalesce(specimen.c.archived_at, func.now()),
                        status=ARCHIVED_STATUS,
                        updated_at=func.now(),
                    )
                    .returning(specimen.c.id)
                )
            ).first()
        return row is not None

    # -------------------------------------------------------------- locations

    async def list_locations(
        self, site_id: str | None = None, outdoor: bool | None = None
    ) -> list[Record]:
        stmt = select(location, _SPECIMEN_COUNT).where(location.c.archived_at.is_(None))
        if site_id:
            stmt = stmt.where(location.c.site_id == _as_uuid(site_id))
        if outdoor is not None:
            stmt = stmt.where(location.c.is_outdoor.is_(outdoor))
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                stmt.order_by(location.c.created_at, location.c.id)
            )
            return [dict(r._mapping) for r in rows]

    async def get_location(self, location_id: str) -> Record | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    select(location, _SPECIMEN_COUNT).where(
                        location.c.id == _as_uuid(location_id)
                    )
                )
            ).first()
            return dict(row._mapping) if row else None

    async def _resolve_site(self, conn: AsyncConnection, site_id: Any) -> uuid.UUID:
        if site_id:
            resolved = _as_uuid(site_id)
            if resolved is not None:
                return resolved
        # One household, one site (v1.0 is explicitly not multi-household).
        found = await conn.scalar(
            select(site.c.id).order_by(site.c.created_at, site.c.id).limit(1)
        )
        if found is None:
            raise NoSiteError()
        return uuid.UUID(str(found))

    async def create_location(self, data: dict[str, Any]) -> Record:
        async with self._engine.begin() as conn:
            if data.get("parent_id"):
                await self._require_location(conn, data["parent_id"])
            values = {
                "id": uuid.uuid4(),
                "site_id": await self._resolve_site(conn, data.get("site_id")),
                "parent_id": _as_uuid(data.get("parent_id")),
                "name": data["name"],
                "kind": data["kind"],
                "is_outdoor": bool(data["is_outdoor"]),
                "is_covered": bool(data.get("is_covered", False)),
                "sun_exposure": normalise_sun_exposure(data.get("sun_exposure")),
            }
            row = (
                await conn.execute(
                    location.insert().values(**values).returning(location)
                )
            ).one()
            return {**dict(row._mapping), "specimen_count": 0}

    async def update_location(
        self, location_id: str, data: dict[str, Any]
    ) -> Record | None:
        key = _as_uuid(location_id)
        async with self._engine.begin() as conn:
            exists = await conn.scalar(
                select(location.c.id).where(location.c.id == key)
            )
            if exists is None:
                return None
            if data.get("parent_id"):
                await self._require_location(conn, data["parent_id"])

            values: dict[str, Any] = {
                "name": data["name"],
                "kind": data["kind"],
                "is_outdoor": bool(data["is_outdoor"]),
                "is_covered": bool(data.get("is_covered", False)),
                "sun_exposure": normalise_sun_exposure(data.get("sun_exposure")),
            }
            if data.get("site_id"):
                values["site_id"] = _as_uuid(data["site_id"])
            if "parent_id" in data:
                values["parent_id"] = _as_uuid(data["parent_id"])

            await conn.execute(
                location.update().where(location.c.id == key).values(**values)
            )
            # Moving a porch indoors moves everything standing on it. Same
            # transaction, so the two flags are never seen disagreeing.
            await conn.execute(
                specimen.update()
                .where(specimen.c.location_id == key)
                .values(is_outdoor=values["is_outdoor"], updated_at=func.now())
            )
            row = (
                await conn.execute(
                    select(location, _SPECIMEN_COUNT).where(location.c.id == key)
                )
            ).one()
            return dict(row._mapping)

    # ---------------------------------------------------------------- members

    async def list_members(self) -> list[Record]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                select(member)
                .where(member.c.archived_at.is_(None))
                .order_by(member.c.created_at, member.c.id)
            )
            return [dict(r._mapping) for r in rows]

    # ------------------------------------------------------------- resolution

    async def resolve_species_by_name(self, name: str) -> str | None:
        needle = name.strip()
        async with self._engine.connect() as conn:
            found = await conn.scalar(
                select(species.c.id).where(
                    func.lower(species.c.accepted_name) == needle.lower()
                )
            )
            if found is None:
                found = await conn.scalar(
                    text(
                        "SELECT id FROM species WHERE EXISTS ("
                        " SELECT 1 FROM unnest(common_names) AS c"
                        " WHERE lower(c) = lower(:name)) LIMIT 1"
                    ),
                    {"name": needle},
                )
        return str(found) if found else None
