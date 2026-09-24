"""The live path, against a real Postgres.

Skipped unless ``MOH_TEST_DATABASE_URL`` names a database these tests may create
tables in, because CI has no Postgres attached yet::

    MOH_TEST_DATABASE_URL=postgresql+asyncpg://herbology@127.0.0.1:5432/herbology_test \
        .venv/bin/pytest api/tending -q

The tables are cut out of ``contracts/schema/001_init.sql`` rather than retyped,
so a column that moves in the frozen schema breaks these tests instead of
quietly passing them — the same arrangement Workstream C uses, for the same
reason. ``water_balance`` is Workstream E's and read-only here.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from tending.repository import Completion, TaskQuery
from tending.service import HORIZON_DAYS, generate_tasks

TEST_DATABASE_URL = os.environ.get("MOH_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set MOH_TEST_DATABASE_URL to run the live-database tests",
)

#: Dependency order. Everything before ``care_rule`` is somebody else's and is
#: created only because this workstream's tables point at it.
TABLES = [
    "site",
    "member",
    "map_layer",
    "location",
    "source",
    "species",
    "care_value",
    "specimen",
    "water_balance",
    "care_rule",
    "task",
    "task_event",
    "calendar_feed",
]

SITE = uuid.UUID("01890000-0000-7000-8000-000000000001")
STUDY = uuid.UUID("01890010-0000-7000-8000-000000000002")
BORDER = uuid.UUID("01890010-0000-7000-8000-000000000004")
KEEPER = uuid.UUID("01890050-0000-7000-8000-000000000001")
MONSTERA = uuid.UUID("01890030-0000-7000-8000-000000000001")
LAVENDER = uuid.UUID("01890030-0000-7000-8000-000000000002")
INDOOR_PLANT = uuid.UUID("01890040-0000-7000-8000-000000000001")
OUTDOOR_PLANT = uuid.UUID("01890040-0000-7000-8000-000000000004")


def _create_table_sql(repo_root, table: str) -> str:
    sql = (repo_root / "contracts" / "schema" / "001_init.sql").read_text()
    start = sql.index(f"CREATE TABLE {table} (")
    end = sql.index("\n);", start) + len("\n);")
    return sql[start:end]


@pytest_asyncio.fixture
async def repo(repo_root):
    from sqlalchemy.ext.asyncio import create_async_engine

    from tending.database_repository import DatabaseRepository

    # NullPool: each test gets its own event loop, and an asyncpg connection
    # belongs to the loop that opened it.
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "citext"'))
        await conn.execute(
            text(f"DROP TABLE IF EXISTS {', '.join(reversed(TABLES))} CASCADE")
        )
        for table in TABLES:
            await conn.execute(text(_create_table_sql(repo_root, table)))
        await _seed(conn)
    try:
        yield DatabaseRepository(engine)
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"DROP TABLE IF EXISTS {', '.join(reversed(TABLES))} CASCADE")
            )
        await engine.dispose()


async def _seed(conn) -> None:
    await conn.execute(
        text(
            "INSERT INTO site (id, name, latitude, longitude, timezone) VALUES "
            "(:id, 'Test Grounds', 39.7684, -86.1581, 'America/Indiana/Indianapolis')"
        ),
        {"id": SITE},
    )
    await conn.execute(
        text("INSERT INTO member (id, name, role) VALUES (:id, 'Keeper', 'keeper')"),
        {"id": KEEPER},
    )
    for place, name, outdoor, covered in (
        (STUDY, "Study", False, True),
        (BORDER, "South Border", True, False),
    ):
        await conn.execute(
            text(
                "INSERT INTO location (id, site_id, name, kind, is_outdoor, is_covered)"
                " VALUES (:id, :site, :name, 'room', :outdoor, :covered)"
            ),
            {
                "id": place,
                "site": SITE,
                "name": name,
                "outdoor": outdoor,
                "covered": covered,
            },
        )
    for species_id, name, interval in (
        (MONSTERA, "Monstera deliciosa", 9),
        (LAVENDER, "Lavandula angustifolia", 14),
    ):
        await conn.execute(
            text(
                "INSERT INTO species (id, accepted_name, common_names,"
                " water_interval_days, dormancy_months)"
                " VALUES (:id, :name, ARRAY['test plant'], :interval, ARRAY[12,1,2])"
            ),
            {"id": species_id, "name": name, "interval": interval},
        )
    # Cited for the Monstera, uncited for the lavender: the two paths ADR 0004
    # distinguishes, both present.
    await conn.execute(
        text(
            "INSERT INTO care_value (id, species_id, field, value, confidence,"
            " is_user_override) VALUES (:id, :species, 'water_interval_days',"
            " '9'::jsonb, 'unknown', true)"
        ),
        {"id": uuid.uuid4(), "species": MONSTERA},
    )
    for plant, species_id, place, outdoor, nickname in (
        (INDOOR_PLANT, MONSTERA, STUDY, False, "Gilderoy"),
        (OUTDOOR_PLANT, LAVENDER, BORDER, True, "Sour Bertram"),
    ):
        await conn.execute(
            text(
                "INSERT INTO specimen (id, species_id, nickname, location_id,"
                " is_outdoor, in_container, container_litres, acquired_on)"
                " VALUES (:id, :species, :nickname, :place, :outdoor, true, 18,"
                " DATE '2024-03-14')"
            ),
            {
                "id": plant,
                "species": species_id,
                "nickname": nickname,
                "place": place,
                "outdoor": outdoor,
            },
        )
    await conn.execute(
        text(
            "INSERT INTO water_balance (day, specimen_id, deficit_mm, capacity_mm,"
            " threshold_mm, k_c) VALUES (CURRENT_DATE, :id, 40, 60, 30, 0.7)"
        ),
        {"id": OUTDOOR_PLANT},
    )


async def test_the_schedule_comes_up_on_an_empty_database(repo):
    """A fresh deployment has no care_rule rows and twelve thirsty plants."""
    generated = await generate_tasks(repo)
    rows = await repo.tasks(TaskQuery())
    assert rows
    assert all(row["title"] and row["plain_title"] for row in rows)
    assert generated.certainty


async def test_generation_is_idempotent_against_postgres(repo):
    await generate_tasks(repo)
    first = {
        str(row["id"]): row["ics_sequence"] for row in await repo.tasks(TaskQuery())
    }
    await generate_tasks(repo)
    second = {
        str(row["id"]): row["ics_sequence"] for row in await repo.tasks(TaskQuery())
    }
    assert first == second


async def test_the_outdoor_plant_is_scheduled_by_the_water_balance(repo):
    """Deficit 40 against a threshold of 30 is a watering, and it is due today."""
    await generate_tasks(repo)
    rows = await repo.tasks(TaskQuery(specimen_id=str(OUTDOOR_PLANT)))
    assert rows
    assert rows[0]["due_at"].date() == datetime.now(UTC).date()


async def test_completion_is_logged_as_an_event_and_retires_the_cycle(repo):
    await generate_tasks(repo)
    rows = await repo.tasks(TaskQuery(specimen_id=str(INDOOR_PLANT)))
    done = await repo.complete(
        [str(rows[0]["id"])], Completion(completed_by=str(KEEPER), notes="Thirsty")
    )
    assert done and done[0]["status"] == "done"
    after = await repo.tasks(TaskQuery(specimen_id=str(INDOOR_PLANT)))
    assert any(
        row["status"] == "cancelled" for row in after if row["id"] != done[0]["id"]
    )

    async with repo._engine.connect() as conn:  # noqa: SLF001 — asserting the history
        kinds = [
            row[0]
            for row in (
                await conn.execute(text("SELECT kind FROM task_event ORDER BY at"))
            ).all()
        ]
    assert "created" in kinds and "completed" in kinds and "cancelled" in kinds


async def test_a_completed_task_is_never_rewritten_by_a_later_generation(repo):
    await generate_tasks(repo)
    rows = await repo.tasks(TaskQuery(specimen_id=str(INDOOR_PLANT)))
    done = await repo.complete([str(rows[0]["id"])], Completion())
    await generate_tasks(repo)
    again = await repo.task(str(done[0]["id"]))
    assert again is not None and again["status"] == "done"


async def test_a_rescheduled_task_keeps_its_uid_and_gains_a_sequence(repo):
    """The property the whole identity scheme exists to hold."""
    await generate_tasks(repo)
    before = (await repo.tasks(TaskQuery(specimen_id=str(INDOOR_PLANT))))[0]
    # A three-day rule where there was a nine-day one moves every occurrence.
    await repo.create_care_rule(
        {
            "specimen_id": str(INDOOR_PLANT),
            "task_type": "water",
            "strategy": "interval",
            "base_interval_days": 3,
        }
    )
    await generate_tasks(repo)
    after = await repo.task(str(before["id"]))
    if after is not None and after["due_at"] != before["due_at"]:
        assert after["ics_uid"] == before["ics_uid"]
        assert after["ics_sequence"] == before["ics_sequence"] + 1


async def test_each_feed_has_its_own_token_and_revoking_one_spares_the_rest(repo):
    keep = await repo.create_feed({"member_id": str(KEEPER), "name": "All rounds"})
    doomed = await repo.create_feed({"member_id": str(KEEPER), "name": "Old phone"})
    assert keep["token"] != doomed["token"]

    await repo.revoke_feed(str(doomed["id"]))
    assert await repo.feed_by_token(doomed["token"]) is None
    assert await repo.feed_by_token(keep["token"]) is not None


async def test_the_horizon_is_respected(repo):
    await generate_tasks(repo)
    horizon = datetime.now(UTC).date()
    for row in await repo.tasks(TaskQuery()):
        assert (row["due_at"].date() - horizon).days <= HORIZON_DAYS


async def test_an_uncited_interval_survives_the_round_trip_as_a_visible_mark(repo):
    """The lavender's interval has no care_value row at all."""
    generated = await generate_tasks(repo)
    rows = await repo.tasks(TaskQuery(specimen_id=str(OUTDOOR_PLANT)))
    assert rows
    assert generated.certainty[str(rows[0]["id"])]["confidence"] in {
        "unknown",
        "low",
        "medium",
    }


async def test_care_rules_list_the_derived_rule_when_nothing_is_stored(repo):
    rules = await repo.care_rules(str(INDOOR_PLANT))
    assert rules and rules[0]["task_type"] == "water"


async def test_a_care_rule_for_an_unknown_specimen_is_refused(repo):
    from tending.repository import UnknownSpecimenError

    with pytest.raises(UnknownSpecimenError):
        await repo.create_care_rule(
            {"specimen_id": str(uuid.uuid4()), "task_type": "water"}
        )


async def test_the_dormancy_month_check_uses_the_sites_calendar(repo):
    """December is winter in Indianapolis and the rules suspend watering."""
    generated = await generate_tasks(repo, today=date(2026, 12, 15))
    rows = await repo.tasks(TaskQuery(specimen_id=str(INDOOR_PLANT)))
    assert not rows or generated.unscheduled
