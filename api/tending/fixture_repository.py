"""The schedule in memory, seeded from ``fixtures/`` — mock mode.

Writes live in the process: complete a task here and it stays completed until
the API restarts, which is what lets Morning Rounds, batch completion and a
subscribable calendar be demonstrated end to end with no database attached
(ADR 0003, rule 3). It is not a read-only stub, because an S4 exit criterion
that only works against Postgres cannot be shown at the sprint demo.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, date, datetime
from typing import Any

from app import fixtures
from tending import environment as env
from tending import tokens
from tending.defaults import default_rules
from tending.domain import Rule, Subject
from tending.repository import (
    Completion,
    Record,
    SchedulingInputs,
    TaskQuery,
    UnknownFeedError,
    UnknownSpecimenError,
)

#: The household's single member in the fixtures, matching Workstream C's
#: ``FixtureRepository``. ADR 0008: one shared login, a member picker.
KEEPER_ID = "01890050-0000-7000-8000-000000000001"

#: Deterministic id for the feed every fresh install gets, so that restarting
#: the mock does not orphan a subscription somebody just added. The *token* is
#: minted fresh each boot and is never this predictable.
DEFAULT_FEED_ID = "01890060-0000-7000-8000-000000000001"


def _terminal(status: str) -> bool:
    return status in {"done", "cancelled", "skipped"}


class FixtureRepository:
    """An in-memory schedule. Ordering is fixture order, then order of arrival."""

    def __init__(self) -> None:
        # Deep copies: ``app.fixtures`` caches the parsed JSON, and a store that
        # mutated it would rewrite the fixture data for every other reader.
        self._specimens: list[Record] = copy.deepcopy(fixtures.specimens())
        self._species: list[Record] = copy.deepcopy(fixtures.species())
        self._locations: list[Record] = copy.deepcopy(fixtures.locations())
        self._tasks: dict[str, Record] = {}
        self._events: list[Record] = []
        self._rules: list[Record] = []
        self._feeds: list[Record] = [self._default_feed()]
        # Mirrors Workstream C's fixture Register, which is the household this
        # mock schedules for. Completion is attributed to a member or it is not
        # history, only a checkbox.
        self._members: list[Record] = [
            {"id": KEEPER_ID, "name": "Keeper", "role": "keeper", "notify_prefs": {}},
        ]

    # ---------------------------------------------------------------- helpers

    def _default_feed(self) -> Record:
        return {
            "id": DEFAULT_FEED_ID,
            "member_id": KEEPER_ID,
            "name": "All rounds",
            "token": tokens.mint(),
            "filters": {},
            "push_target": "none",
            "push_config": {},
            "last_rendered_at": None,
            "revoked_at": None,
            "created_at": datetime.now(UTC),
        }

    def _species_for(self, specimen: Record) -> Record:
        species_id = specimen.get("species_id") or ""
        return next((s for s in self._species if s["id"] == species_id), {})

    def _location_for(self, specimen: Record) -> Record:
        location_id = specimen.get("location_id") or ""
        return next((row for row in self._locations if row["id"] == location_id), {})

    def _subject(self, specimen: Record) -> Subject:
        species = self._species_for(specimen)
        acquired = specimen.get("acquired_on")
        return Subject(
            specimen_id=str(specimen["id"]),
            display_name=fixtures.display_name(specimen),
            has_nickname=bool(specimen.get("nickname")),
            is_outdoor=bool(specimen.get("is_outdoor")),
            in_container=bool(specimen.get("in_container")),
            location_id=specimen.get("location_id"),
            container_litres=specimen.get("container_litres"),
            species_id=specimen.get("species_id"),
            dormancy_months=tuple(species.get("dormancy_months") or ()),
            acquired_on=date.fromisoformat(acquired) if acquired else None,
        )

    def _stored_rules_for(self, specimen_id: str, species_id: str | None) -> list[Rule]:
        out: list[Rule] = []
        for row in self._rules:
            if row.get("specimen_id") == specimen_id or (
                row.get("species_id") and row.get("species_id") == species_id
            ):
                out.append(_rule_from_record(row))
        return out

    # ------------------------------------------------------------- scheduling

    async def scheduling_inputs(self) -> SchedulingInputs:
        inputs = SchedulingInputs(latitude=float(fixtures.site()["latitude"]))
        for specimen in self._specimens:
            if specimen.get("archived_at"):
                continue
            subject = self._subject(specimen)
            species = self._species_for(specimen)
            derived, reasons = default_rules(
                subject,
                species.get("care_values") or [],
                species.get("water_interval_days"),
            )
            stored = self._stored_rules_for(subject.specimen_id, subject.species_id)
            inputs.subjects.append(subject)
            # Stored rules come last so ``resolve_rules`` lets a specimen-scoped
            # rule the household wrote win over the one this package derived.
            inputs.rules[subject.specimen_id] = derived + stored
            if reasons and not stored:
                inputs.unscheduled[subject.specimen_id] = reasons

        inputs.environments = env.fixture_environments(
            [subject.specimen_id for subject in inputs.subjects]
        )
        inputs.last_completed = self._last_completed()
        return inputs

    def _last_completed(self) -> dict[tuple[str, str], date]:
        out: dict[tuple[str, str], date] = {}
        for row in self._tasks.values():
            if row.get("status") != "done" or not row.get("completed_at"):
                continue
            key = (str(row["specimen_id"]), str(row["task_type"]))
            day = row["completed_at"].date()
            if key not in out or day > out[key]:
                out[key] = day
        return out

    async def upsert_tasks(self, rows: list[Record]) -> None:
        """Insert generated tasks, or move the ones that have been rescheduled.

        A task a member has already acted on is never rewritten. A task whose
        due date has moved keeps its id and its ``ics_uid`` and gains a
        ``SEQUENCE``, which is the whole reason the id is not the date.
        """
        for row in rows:
            existing = self._tasks.get(row["id"])
            if existing is None:
                self._tasks[row["id"]] = dict(row)
                self._events.append(_event(row["id"], "created"))
                continue
            if _terminal(str(existing.get("status"))) or existing.get("completed_at"):
                continue
            moved = existing["due_at"] != row["due_at"]
            existing.update(
                {
                    key: row[key]
                    for key in (
                        "due_at",
                        "all_day",
                        "status",
                        "satisfied_by",
                        "amount_ml",
                        "priority",
                        "title",
                        "plain_title",
                        "detail",
                        "confidence",
                        "degraded",
                        "degradations",
                    )
                }
            )
            if moved:
                existing["ics_sequence"] = int(existing.get("ics_sequence") or 0) + 1
                self._events.append(_event(row["id"], "rescheduled"))

    # ------------------------------------------------------------------ tasks

    async def tasks(self, query: TaskQuery) -> list[Record]:
        rows = [dict(row) for row in self._tasks.values()]
        if query.status:
            rows = [row for row in rows if row["status"] == query.status]
        if query.specimen_id:
            rows = [row for row in rows if row["specimen_id"] == query.specimen_id]
        if query.due_before:
            rows = [row for row in rows if row["due_at"] < query.due_before]
        if query.due_after:
            rows = [row for row in rows if row["due_at"] >= query.due_after]
        rows.sort(key=lambda row: (row["due_at"], row["task_type"]))
        return [self._hydrate(row) for row in rows]

    async def task(self, task_id: str) -> Record | None:
        row = self._tasks.get(task_id)
        return self._hydrate(dict(row)) if row else None

    def _hydrate(self, row: Record) -> Record:
        specimen = next(
            (s for s in self._specimens if s["id"] == row["specimen_id"]), None
        )
        row["specimen"] = {
            "id": row["specimen_id"],
            "display_name": (
                fixtures.display_name(specimen) if specimen else "Unnamed specimen"
            ),
            "is_outdoor": bool(specimen.get("is_outdoor")) if specimen else False,
            "thumb_url": None,
        }
        # Not part of the contract's ``Task``; carried on the stored row so a
        # feed's ``location_ids`` filter has something to read.
        row["location_id"] = specimen.get("location_id") if specimen else None
        row["completed_by"] = self._member(row.get("completed_by"))
        return row

    def _member(self, member_id: Any) -> Record | None:
        if not member_id:
            return None
        if isinstance(member_id, dict):
            return member_id
        return next((dict(m) for m in self._members if m["id"] == str(member_id)), None)

    async def complete(
        self, task_ids: list[str], completion: Completion
    ) -> list[Record]:
        """Tick tasks off, log who did it, and retire the cycle they belonged to.

        The history is the point: people want to know when the lemon was last
        fed, so every completion writes a ``task_event`` rather than only
        stamping the task.
        """
        now = datetime.now(UTC)
        completed: list[Record] = []
        for task_id in task_ids:
            row = self._tasks.get(task_id)
            if row is None or _terminal(str(row.get("status"))):
                continue
            row["status"] = "done"
            row["completed_at"] = now
            row["completed_by"] = completion.completed_by or KEEPER_ID
            if completion.amount_ml is not None:
                row["amount_ml"] = completion.amount_ml
            if completion.notes:
                row["notes"] = completion.notes
            row["ics_sequence"] = int(row.get("ics_sequence") or 0) + 1
            data: dict[str, Any] = {}
            if completion.amount_ml is not None:
                data["amount_ml"] = completion.amount_ml
            if completion.new_location_id:
                # Sprint 6 turns this into an actual move (Workstream C owns the
                # write). Recording it now means the relocation is not lost
                # between sprints, and the history reads correctly either way.
                data["new_location_id"] = completion.new_location_id
            self._events.append(
                _event(
                    task_id,
                    "completed",
                    by_member=row["completed_by"],
                    data=data,
                    at=now,
                )
            )
            self._retire_cycle(row, now)
            completed.append(self._hydrate(dict(row)))
        return completed

    def _retire_cycle(self, done: Record, now: datetime) -> None:
        """Cancel what the old cycle had scheduled, so the calendar lets go.

        Completion moves the anchor, so every occurrence counted from the old
        one is now fiction. Left alone they would sit in a subscriber's calendar
        as events for waterings that will never be asked for; cancelled, the
        feed removes them by UID on its next fetch.
        """
        for row in self._tasks.values():
            if row["id"] == done["id"]:
                continue
            if row["specimen_id"] != done["specimen_id"]:
                continue
            if row["task_type"] != done["task_type"]:
                continue
            if _terminal(str(row.get("status"))):
                continue
            row["status"] = "cancelled"
            row["ics_sequence"] = int(row.get("ics_sequence") or 0) + 1
            self._events.append(_event(row["id"], "cancelled", at=now))

    # ------------------------------------------------------------- care rules

    async def care_rules(self, specimen_id: str | None = None) -> list[Record]:
        inputs = await self.scheduling_inputs()
        out: list[Record] = []
        for subject in inputs.subjects:
            if specimen_id and subject.specimen_id != specimen_id:
                continue
            for rule in inputs.rules.get(subject.specimen_id, []):
                out.append(_rule_record(rule))
        return out

    async def create_care_rule(self, record: Record) -> Record:
        specimen_id = record.get("specimen_id")
        if specimen_id and not any(s["id"] == specimen_id for s in self._specimens):
            raise UnknownSpecimenError(str(specimen_id))
        stored = dict(record)
        stored.setdefault("id", str(uuid.uuid4()))
        stored.setdefault("created_at", datetime.now(UTC))
        self._rules.append(stored)
        return dict(stored)

    # ------------------------------------------------------------------ feeds

    async def feeds(self) -> list[Record]:
        return [dict(row) for row in self._feeds]

    async def create_feed(self, record: Record) -> Record:
        stored = dict(record)
        stored.setdefault("id", str(uuid.uuid4()))
        # One feed, one token: revoking a phone's subscription must not disturb
        # anybody else's, so no token is ever shared between two feeds.
        stored["token"] = tokens.mint()
        stored.setdefault("created_at", datetime.now(UTC))
        stored.setdefault("last_rendered_at", None)
        stored.setdefault("revoked_at", None)
        self._feeds.append(stored)
        return dict(stored)

    async def revoke_feed(self, feed_id: str) -> Record:
        for row in self._feeds:
            if row["id"] == feed_id:
                row["revoked_at"] = datetime.now(UTC)
                # Rotated as well as marked: a token that stays valid in the
                # database after a revoke is a revoke that did not happen.
                row["token"] = tokens.mint()
                return dict(row)
        raise UnknownFeedError(feed_id)

    async def feed_by_token(self, token: str) -> Record | None:
        for row in self._feeds:
            if row.get("revoked_at"):
                continue
            if tokens.matches(token, str(row["token"])):
                return dict(row)
        return None

    async def touch_feed(self, feed_id: str) -> None:
        for row in self._feeds:
            if row["id"] == feed_id:
                row["last_rendered_at"] = datetime.now(UTC)

    # ------------------------------------------------------------ environment

    async def members(self) -> list[Record]:
        return [dict(row) for row in self._members]

    async def frost_alerts(self) -> list[Record]:
        return env.fixture_frost_alerts()

    async def weather_today(self) -> Record | None:
        return env.fixture_weather_today()


def _event(
    task_id: str,
    kind: str,
    *,
    by_member: str | None = None,
    data: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> Record:
    return {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "at": at or datetime.now(UTC),
        "kind": kind,
        "by_member": by_member,
        "data": data or {},
    }


def _rule_from_record(row: Record) -> Rule:
    return Rule(
        id=str(row["id"]),
        task_type=str(row["task_type"]),
        strategy=str(row.get("strategy") or "interval"),
        base_interval_days=row.get("base_interval_days"),
        amount_ml=row.get("amount_ml"),
        modifiers=dict(row.get("modifiers") or {}),
        months=tuple(row.get("months") or ()),
        enabled=bool(row.get("enabled", True)),
        specimen_id=row.get("specimen_id"),
        species_id=row.get("species_id"),
    )


def _rule_record(rule: Rule) -> Record:
    return {
        "id": rule.id,
        "species_id": rule.species_id,
        "specimen_id": rule.specimen_id,
        "task_type": rule.task_type,
        "strategy": rule.strategy,
        "base_interval_days": rule.base_interval_days,
        "amount_ml": rule.amount_ml,
        "modifiers": rule.modifiers,
        "months": list(rule.months),
        "enabled": rule.enabled,
    }


_INSTANCE: FixtureRepository | None = None


def fixture_repository() -> FixtureRepository:
    """One store per process, so a completion survives the next request."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = FixtureRepository()
    return _INSTANCE


def reset_fixture_repository() -> None:
    """Drop the in-memory schedule. For tests, which must not share state."""
    global _INSTANCE
    _INSTANCE = None
