"""What the tending endpoints do, between the router and the stores.

Generation runs **on read**. Every call that needs today's schedule materialises
it first, and because every task id is a pure function of its occurrence
(``tending.domain.task_id``), running it twice writes nothing the first run did
not. That is a deliberate shape, not a shortcut: the natural home for a nightly
rule evaluation is an Arq job, and ``workers/`` belongs to another workstream.
Reaching in to add one would have broken rule 2, so the scheduled job is
escalated in the pull request and the API stays correct without it in the
meantime.

The cost is honest and worth writing down: Morning Rounds does the generation
work on the request, which is fine for one household's dozen plants and is not
fine for a thousand. The seam is :func:`generate_tasks` — a worker calls the
same function on a schedule, and these endpoints become pure reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from tending import ics, schemas
from tending.domain import Environment, generate, task_row
from tending.repository import Completion, Record, TaskQuery, TendingRepository

#: How far ahead the calendar is filled. Far enough that a subscriber sees next
#: month, short enough that a rule edit is reflected within one refresh.
HORIZON_DAYS = 30

#: How far back a feed carries completed and cancelled events. A cancellation
#: has to stay in the feed long enough for every subscriber to fetch it, or the
#: event it cancels lives on in their calendar forever.
FEED_LOOKBACK_DAYS = 14


@dataclass(slots=True)
class Generated:
    """What one generation pass produced besides the stored rows.

    ``certainty`` exists because the frozen ``task`` table has nowhere to keep
    it. ADR 0018 put ``confidence``, ``degraded`` and ``degradations`` on
    Workstream E's *responses*; the schema behind them was never given the same
    columns, so a task's certainty cannot survive a round trip through Postgres.
    Generation runs on every read anyway, so the freshly computed values are
    carried across and merged onto the rows before they are serialised — the
    same in both stores, so neither can drift.

    The honest fix is three columns on ``task``, and it is asked of Workstream A
    in the pull request rather than worked around any further than this.
    """

    unscheduled: dict[str, list[str]] = field(default_factory=dict)
    certainty: dict[str, dict[str, Any]] = field(default_factory=dict)

    def merge_into(self, rows: list[Record]) -> list[Record]:
        for row in rows:
            known = self.certainty.get(str(row["id"]))
            if known:
                row.update(known)
        return rows


def _day_bounds(on: date) -> tuple[datetime, datetime]:
    start = datetime.combine(on, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def generate_tasks(
    repo: TendingRepository, *, today: date | None = None
) -> Generated:
    """Materialise every occurrence due between each plant's anchor and the horizon.

    Returns the plants that could not be scheduled, and why — never an empty
    silence. A plant that drops off the rounds because nobody cited a watering
    interval looks exactly like a plant that needs nothing, and that is the
    failure mode ADR 0018 exists to name in the weather engines.
    """
    today = today or datetime.now(UTC).date()
    inputs = await repo.scheduling_inputs()

    rows: list[Record] = []
    unscheduled = dict(inputs.unscheduled)
    for subject in inputs.subjects:
        rules = inputs.rules.get(subject.specimen_id) or []
        if not rules:
            continue
        environment = inputs.environments.get(subject.specimen_id, Environment())
        occurrences = generate(
            subject,
            rules,
            today=today,
            horizon_days=HORIZON_DAYS,
            latitude=inputs.latitude,
            environments={"water": environment},
            last_completed={
                task_type: day
                for (specimen_id, task_type), day in inputs.last_completed.items()
                if specimen_id == subject.specimen_id
            },
        )
        rows.extend(task_row(occurrence) for occurrence in occurrences)
        if not occurrences and subject.is_dormant(today):
            months = ", ".join(str(month) for month in sorted(subject.dormancy_months))
            unscheduled.setdefault(subject.specimen_id, []).append(
                f"Dormant this month (months {months}). Its care rule suspends "
                "watering rather than stretching it, so nothing is scheduled "
                "until it wakes."
            )

    await repo.upsert_tasks(rows)
    return Generated(
        unscheduled=unscheduled,
        certainty={
            str(row["id"]): {
                "confidence": row["confidence"],
                "degraded": row["degraded"],
                "degradations": row["degradations"],
            }
            for row in rows
        },
    )


async def morning_rounds(
    repo: TendingRepository, on: date | None = None
) -> dict[str, Any]:
    """``GET /tending/rounds`` — today, grouped the way the screen reads it."""
    day = on or datetime.now(UTC).date()
    generated = await generate_tasks(repo, today=day)
    _, end = _day_bounds(day)

    rows = generated.merge_into(await repo.tasks(TaskQuery(due_before=end)))
    due = [schemas.task_out(row) for row in rows if row["status"] == "due"]
    satisfied = [
        schemas.task_out(row)
        for row in rows
        if row["status"] == "satisfied" and row["due_at"] >= _day_bounds(day)[0]
    ]

    return {
        "date": day.isoformat(),
        "greeting": greeting(len(due)),
        "due": due,
        "satisfied": satisfied,
        "alerts": await repo.frost_alerts(),
        "weather": await repo.weather_today(),
        # Additive, and the point of the exercise: the plants this round could
        # not speak for, each with the reason. Requested of Workstream A in the
        # pull request alongside the certainty fields on ``Task``.
        "unscheduled": [
            {"specimen_id": specimen_id, "reason": reason}
            for specimen_id, reasons in sorted(generated.unscheduled.items())
            for reason in reasons
        ],
    }


def greeting(due_count: int) -> str:
    """Themed, and plain in the same breath — rule 7 applies to prose too."""
    if due_count == 0:
        return "Good morning. The greenhouse is settled — nothing is due today."
    plants = "1 task is" if due_count == 1 else f"{due_count} tasks are"
    return f"Good morning. The greenhouse is stirring — {plants} due today."


async def list_tasks(repo: TendingRepository, query: TaskQuery) -> list[dict[str, Any]]:
    generated = await generate_tasks(repo)
    rows = generated.merge_into(await repo.tasks(query))
    return [schemas.task_out(row) for row in rows]


async def complete(
    repo: TendingRepository, task_ids: list[str], completion: Completion
) -> list[dict[str, Any]]:
    """One tap or a whole batch — the same path, so they cannot diverge.

    Morning Rounds sends a batch; the Tending facet sends one. A batch that took
    a different route would eventually log its events differently, and the
    history is the feature.
    """
    generated = await generate_tasks(repo)
    rows = generated.merge_into(await repo.complete(task_ids, completion))
    return [schemas.task_out(row) for row in rows]


# ----------------------------------------------------------------- feed


def matches_filters(row: Record, filters: dict[str, Any]) -> bool:
    """A feed's filter set, applied to one stored task.

    An absent filter means "everything"; an empty list means the same, because a
    feed whose ``task_types: []`` rendered nothing would look broken rather than
    unfiltered.

    Applied to the stored row rather than the serialised one: the contract's
    ``SpecimenBrief`` carries no location, and inventing a field on the response
    so that a filter could read it would be a contract change by the back door.
    """
    outdoor = filters.get("outdoor")
    specimen = row.get("specimen") or {}
    if outdoor is not None and bool(specimen.get("is_outdoor")) is not bool(outdoor):
        return False
    task_types = filters.get("task_types") or []
    if task_types and row["task_type"] not in task_types:
        return False
    location_ids = filters.get("location_ids") or []
    return not (location_ids and row.get("location_id") not in location_ids)


async def render_feed(
    repo: TendingRepository, token: str, *, base_url: str, now: datetime | None = None
) -> str | None:
    """The ICS document for one token, or ``None`` if the token is not a feed.

    ``None`` covers both "no such feed" and "revoked", and the router answers
    404 to both without distinguishing them: telling an unauthenticated caller
    that a token *used* to work is telling them the token was real.
    """
    feed = await repo.feed_by_token(token)
    if feed is None:
        return None

    now = now or datetime.now(UTC)
    generated = await generate_tasks(repo, today=now.date())
    horizon = now + timedelta(days=HORIZON_DAYS + 1)
    since = now - timedelta(days=FEED_LOOKBACK_DAYS)

    rows = generated.merge_into(
        await repo.tasks(TaskQuery(due_after=since, due_before=horizon))
    )
    filters = feed.get("filters") or {}
    events = [schemas.ics_task(row) for row in rows if matches_filters(row, filters)]
    document = ics.render(
        events,
        name=f"The Ministry of Herbology — {feed['name']}",
        base_url=base_url,
        now=now,
    )
    await repo.touch_feed(str(feed["id"]))
    return document
