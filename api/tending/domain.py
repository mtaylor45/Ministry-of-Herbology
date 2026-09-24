"""The scheduling engine: care rules in, dated occurrences out.

Nothing in this module reads a database, a fixture file or the clock. Every
input arrives as an argument, which is what lets the season, dormancy and
weather behaviour be tested against dates that are not today.

Three things here are load-bearing and are the reason the module exists at all.

**Identity is not the due date.** A task's identity is the *occurrence* a rule
generates — the nth cycle since an anchor — and not the day it currently sits
on. Stretch a winter watering by four days and it is the same occurrence, moved;
it must update the calendar event in place and bump ``SEQUENCE``. Deriving the
UID from the due date, as the S0 mock did, turns every reschedule into a second
event in somebody's calendar, and there is no way to take those back once a
feed is subscribed.

**The anchor is the last time the job was actually done.** Completion moves the
anchor, which retires the outstanding occurrence and starts a fresh cycle with
fresh identities. That is why a completed task is never regenerated and why
watering twice in a week does not leave a stale event behind.

**Dormancy suspends; it does not stretch.** A dormant plant is not on a longer
interval, it is off the schedule until it wakes. Stretching would still put a
watering in the calendar, in the month the plant least wants one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from tending.titles import TASK_TYPES, titles_for

#: Deterministic task ids. Regenerating the schedule must land on the same
#: uuid for the same occurrence, or every read would mint duplicate rows and
#: every duplicate row would be a duplicate calendar event.
TASK_NAMESPACE = uuid.UUID("2f4d9d8a-1c4c-4f0f-9f39-1a0b0c5e7d31")

#: The ICS UID suffix. It is a constant and must stay one: a UID that changes
#: is a new event to every calendar client alive.
ICS_DOMAIN = "herbology"

#: Occurrences are generated no further than this, whatever the rule says. A
#: misconfigured one-day interval over a long horizon should be dull, not a
#: denial of service.
MAX_OCCURRENCES = 120

#: The anchor for a plant with no completion history and no acquisition date.
#: Fixed, so identities do not move when the code is redeployed.
EPOCH = date(2024, 1, 1)

#: Routine all-day tasks are posted at this hour UTC so that ``due_at`` sorts
#: sensibly and a client rendering a time gets a morning rather than midnight.
ROUNDS_HOUR = 9

#: Task types the plan treats as urgent and timed rather than all-day: they are
#: due *by* a moment (sunset before a cold night), not on a day.
TIMED_TASK_TYPES = frozenset({"bring_indoors", "cover"})

#: Index 0 is reserved for the single state-driven occurrence a strategy such as
#: ``water_balance`` produces — "the outstanding one since the anchor". Scheduled
#: cycles are 1, 2, 3… so the two can never collide.
OUTSTANDING_INDEX = 0

SUSPENDED = "suspended"


# --------------------------------------------------------------------- inputs


@dataclass(frozen=True, slots=True)
class Subject:
    """One plant, as the scheduler needs it. Built by the stores, never here."""

    specimen_id: str
    display_name: str
    has_nickname: bool
    is_outdoor: bool
    in_container: bool
    location_id: str | None = None
    container_litres: float | None = None
    species_id: str | None = None
    dormancy_months: tuple[int, ...] = ()
    acquired_on: date | None = None
    thumb_url: str | None = None

    def is_dormant(self, on: date) -> bool:
        return on.month in self.dormancy_months


@dataclass(frozen=True, slots=True)
class Caveat:
    """One reason a task is worth less than it looks.

    The same shape as Workstream E's ``Degradation`` (ADR 0018) on purpose: a
    task built on a degraded input carries E's reasons through unchanged and
    adds its own beside them, rather than laundering either into a clean
    instruction.
    """

    code: str
    detail: str
    caps_at: str = "medium"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "caps_at": self.caps_at}


@dataclass(frozen=True, slots=True)
class Rule:
    """A ``care_rule`` row, as the frozen schema declares it."""

    id: str
    task_type: str
    strategy: str = "interval"
    base_interval_days: int | None = None
    amount_ml: int | None = None
    modifiers: dict[str, Any] = field(default_factory=dict)
    months: tuple[int, ...] = ()
    enabled: bool = True
    specimen_id: str | None = None
    species_id: str | None = None

    #: Not columns. What the interval this rule carries is actually worth, and
    #: why — ADR 0004 travelling with the number instead of behind it. A rule
    #: derived from an uncited care value says ``unknown`` here, and every task
    #: it generates says so where a reader will see it.
    interval_confidence: str = "medium"
    interval_caveats: tuple[Caveat, ...] = ()

    @property
    def scope(self) -> str:
        """Specimen rules beat species rules for the same task type."""
        return "specimen" if self.specimen_id else "species"


#: ADR 0004's four levels, best to worst.
CONFIDENCE_ORDER = ("high", "medium", "low", "unknown")


def weakest(*confidences: str) -> str:
    """The least confident of several claims, which is what a chain is worth."""
    ranks = [
        (
            CONFIDENCE_ORDER.index(c)
            if c in CONFIDENCE_ORDER
            else len(CONFIDENCE_ORDER) - 1
        )
        for c in confidences
        if c
    ]
    return CONFIDENCE_ORDER[max(ranks)] if ranks else "unknown"


@dataclass(frozen=True, slots=True)
class Environment:
    """What the world says about one plant today, from Workstream E.

    Everything here is *consumed*. This package computes no deficit, no ET₀ and
    no rain total; ADR 0018 put the confidence on E's answer and this carries it
    through. ``balance_status`` is E's word — ``due``, ``satisfied`` or ``ok`` —
    and ``satisfied_by`` is E's attribution for it.
    """

    applies: bool = False
    balance_status: str | None = None
    satisfied_by: str | None = None
    is_due: bool = False
    confidence: str = "unknown"
    degradations: tuple[Caveat, ...] = ()
    #: Newest day the balance actually covers. A series that stops short of the
    #: day it is being used to schedule is stale, and says so.
    newest_day: date | None = None
    #: Indoor relative humidity, when Workstream F has a reading for the room.
    #: ``None`` today for every plant, and the modifier simply does not apply.
    humidity_pct: float | None = None


# -------------------------------------------------------------------- seasons

#: Meteorological seasons, northern hemisphere. Shifted six months south.
_NORTHERN_SEASONS = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}


def season_for(on: date, latitude: float) -> str:
    """The season at the site, which is not the season in the code's timezone.

    A southern-hemisphere deployment watering on a northern winter multiplier
    would dial care back in the exact month the plant needs most.
    """
    month = on.month if latitude >= 0 else (on.month + 6 - 1) % 12 + 1
    return _NORTHERN_SEASONS[month]


# ------------------------------------------------------------------ intervals


def _as_factor(value: Any) -> float | None:
    """A modifier is a multiplier or it is nothing. Never a guess."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    factor = float(value)
    return factor if factor > 0 else None


def effective_interval(
    rule: Rule,
    *,
    season: str,
    dormant: bool,
    humidity_pct: float | None = None,
) -> int | str | None:
    """The rule's interval with its own modifiers applied.

    Returns the number of days, :data:`SUSPENDED` while a dormancy rule holds,
    or ``None`` when the rule declares no interval at all.

    Only modifiers the rule itself carries are applied. There is no ambient
    table of "what plants like in winter" here and there must not be one: rule 6
    forbids inventing a plant fact, and a multiplier nobody configured is
    exactly that, wearing arithmetic.
    """
    base = rule.base_interval_days
    if base is None or base <= 0:
        return None

    modifiers = rule.modifiers or {}

    if dormant:
        dormancy = modifiers.get("dormancy")
        if dormancy == "suspend":
            return SUSPENDED
        factor = _as_factor(dormancy)
        if factor is not None:
            base = max(1, round(base * factor))

    seasonal = modifiers.get("season")
    if isinstance(seasonal, dict):
        factor = _as_factor(seasonal.get(season))
        if factor is not None:
            base = max(1, round(base * factor))

    if humidity_pct is not None:
        low = modifiers.get("humidity_low")
        threshold = _as_factor(modifiers.get("humidity_low_below_pct")) or 40.0
        factor = _as_factor(low)
        if factor is not None and humidity_pct < threshold:
            base = max(1, round(base * factor))

    return max(1, int(base))


# ------------------------------------------------------------------ occurrences


@dataclass(frozen=True, slots=True)
class Occurrence:
    """One dated instance of a rule, before it becomes a stored task."""

    rule: Rule
    subject: Subject
    index: int
    anchor: date
    due_on: date
    status: str = "due"
    satisfied_by: str | None = None
    amount_ml: int | None = None
    priority: str = "normal"
    confidence: str = "high"
    caveats: tuple[Caveat, ...] = ()

    @property
    def task_id(self) -> str:
        return str(
            task_id(self.subject.specimen_id, self.rule, self.anchor, self.index)
        )

    @property
    def all_day(self) -> bool:
        return self.rule.task_type not in TIMED_TASK_TYPES


def task_id(specimen_id: str, rule: Rule, anchor: date, index: int) -> uuid.UUID:
    """The stable identity of one occurrence.

    Deliberately free of the due date: a rescheduled occurrence keeps this id,
    keeps its ``ics_uid``, and updates the calendar event instead of adding one.
    """
    key = f"{specimen_id}|{rule.task_type}|{rule.id}|{anchor.isoformat()}|{index}"
    return uuid.uuid5(TASK_NAMESPACE, key)


def ics_uid(task_id_value: str) -> str:
    """The calendar identity of a task. Never derived from the due date.

    ``task-`` prefixed so that other event kinds this feed may carry later
    (a frost window, a site-wide note) cannot collide with a task's UID.
    """
    return f"task-{task_id_value}@{ICS_DOMAIN}"


def anchor_for(subject: Subject, last_completed_on: date | None) -> date:
    """Where this plant's cycle starts counting.

    The last time the job was actually done, else the day the plant arrived,
    else a fixed epoch — never "today", which would make every regeneration
    mint new identities and every regeneration a fresh pile of calendar events.
    """
    return last_completed_on or subject.acquired_on or EPOCH


def occurrence_dates(
    anchor: date,
    interval_days: int,
    *,
    today: date,
    until: date,
    months: tuple[int, ...] = (),
    limit: int = MAX_OCCURRENCES,
) -> list[tuple[int, date]]:
    """``(index, date)`` for the cycles worth materialising, anchor-numbered.

    Two rules, and the second one is easy to get wrong.

    An occurrence whose month the rule excludes is skipped *without* renumbering
    the ones after it. Renumbering would shift every later identity the moment a
    rule gained a month restriction, which is the same duplicate-event failure
    by a different route.

    And **only the most recent missed occurrence is emitted**, not every one
    since the plant arrived. A lemon acquired in 2022 on a three-week interval
    has had eighty waterings fall due; it is not eighty jobs behind, it is one.
    Numbering still counts from the anchor, so the identity of the outstanding
    occurrence is the same whether it is a day late or a fortnight.
    """
    if interval_days <= 0:
        return []
    overdue: tuple[int, date] | None = None
    future: list[tuple[int, date]] = []
    for index in range(1, limit + 1):
        day = anchor + timedelta(days=interval_days * index)
        if day > until:
            break
        if months and day.month not in months:
            continue
        if day <= today:
            overdue = (index, day)
        else:
            future.append((index, day))
    return ([overdue] if overdue else []) + future


def due_at_for(
    due_on: date, *, all_day: bool, sunset: datetime | None = None
) -> datetime:
    """When the task is due, as a timestamp.

    Routine work is an all-day event and is posted at the rounds hour. A timed
    task (bring indoors, cover) is due *by* sunset before the cold night, and
    falls back to the rounds hour when no sunset is known rather than inventing
    one.
    """
    from datetime import UTC

    if all_day or sunset is None:
        return datetime.combine(due_on, time(hour=ROUNDS_HOUR), tzinfo=UTC)
    return sunset


# ------------------------------------------------------------------ generation


def _balance_caveats(environment: Environment, on: date) -> tuple[list[Caveat], str]:
    """E's reasons, plus this package's own, plus the confidence they cap at."""
    caveats = list(environment.degradations)
    confidence = environment.confidence or "unknown"

    newest = environment.newest_day
    if newest is not None and newest < on:
        stale_days = (on - newest).days
        if stale_days > 1:
            caveats.append(
                Caveat(
                    code="balance_not_current",
                    detail=(
                        f"The water balance this task was built from ends "
                        f"{stale_days} days before it is due. Nothing has advanced "
                        "the deficit since, so the plant is drier than this says."
                    ),
                    caps_at="low",
                )
            )
            confidence = weakest(confidence, "low")
    return caveats, confidence


def generate(
    subject: Subject,
    rules: list[Rule],
    *,
    today: date,
    horizon_days: int,
    latitude: float,
    environments: dict[str, Environment] | None = None,
    last_completed: dict[str, date] | None = None,
    sunsets: dict[date, datetime] | None = None,
) -> list[Occurrence]:
    """Every occurrence one plant owes between its anchor and the horizon.

    Idempotent: the same arguments produce the same occurrences with the same
    ids, which is what lets generation run on every read without a worker (see
    the README — the scheduled job belongs to ``workers/`` and is escalated, not
    reached into).
    """
    environments = environments or {}
    last_completed = last_completed or {}
    sunsets = sunsets or {}
    until = today + timedelta(days=horizon_days)
    out: list[Occurrence] = []

    for rule in resolve_rules(rules):
        anchor = anchor_for(subject, last_completed.get(rule.task_type))
        environment = environments.get(rule.task_type, Environment())

        if rule.strategy == "water_balance" and environment.applies:
            # The model is the authority here, and it is the *only* one: under
            # ADR 0010 nothing measures the soil. Running the interval as well
            # would put a second, unattested watering in the calendar beside a
            # deficit that says the plant is comfortable.
            occurrence = _balance_occurrence(
                subject, rule, anchor=anchor, today=today, environment=environment
            )
            if occurrence is not None:
                out.append(occurrence)
            continue
        # No model answer for this plant — an indoor pot, or an outdoor one the
        # engine declined to judge. Fall through to the rule's interval if it
        # declares one, and otherwise generate nothing at all rather than a task
        # nobody can justify.

        interval = effective_interval(
            rule,
            season=season_for(today, latitude),
            dormant=subject.is_dormant(today),
            humidity_pct=environment.humidity_pct,
        )
        if interval is None or interval == SUSPENDED:
            continue

        for index, due_on in occurrence_dates(
            anchor, int(interval), today=today, until=until, months=rule.months
        ):
            out.append(
                Occurrence(
                    rule=rule,
                    subject=subject,
                    index=index,
                    anchor=anchor,
                    due_on=due_on,
                    amount_ml=rule.amount_ml
                    or (
                        water_amount_ml(subject) if rule.task_type == "water" else None
                    ),
                    priority=(
                        "urgent" if rule.task_type in TIMED_TASK_TYPES else "normal"
                    ),
                    # An interval rule is a schedule, not a measurement. It is
                    # only ever as good as the interval it was configured with,
                    # and that came from a cited care value or it did not.
                    confidence=rule.interval_confidence,
                    caveats=rule.interval_caveats,
                )
            )

    out.sort(key=lambda occurrence: (occurrence.due_on, occurrence.rule.task_type))
    return out


def _balance_occurrence(
    subject: Subject,
    rule: Rule,
    *,
    anchor: date,
    today: date,
    environment: Environment,
) -> Occurrence | None:
    """The single outstanding watering the water balance currently justifies.

    One occurrence, at index 0, held at the same identity for as long as it goes
    undone — so a deficit that crosses on Tuesday and is still unmet on Friday
    moves one calendar event rather than leaving three.

    Future waterings are deliberately *not* projected here. Working out which
    day a deficit will next cross a threshold is Workstream E's engine and
    Sprint 5's job; guessing at it in this package would be a plant fact nobody
    attested, which is exactly what rule 6 forbids.
    """
    status = environment.balance_status
    if status not in {"due", "satisfied"} and not environment.is_due:
        return None

    caveats, confidence = _balance_caveats(environment, today)
    satisfied_by = None
    if status == "satisfied":
        # E attributes it to rain or to logged irrigation; the contract's
        # vocabulary calls a person with a watering can "manual".
        satisfied_by = "rain" if environment.satisfied_by == "rain" else "manual"

    return Occurrence(
        rule=rule,
        subject=subject,
        index=OUTSTANDING_INDEX,
        anchor=anchor,
        due_on=today,
        status="satisfied" if status == "satisfied" else "due",
        satisfied_by=satisfied_by,
        amount_ml=rule.amount_ml or water_amount_ml(subject),
        confidence=confidence,
        caveats=tuple(caveats),
    )


def resolve_rules(rules: list[Rule]) -> list[Rule]:
    """One rule per task type: the specimen's own beats the species default."""
    chosen: dict[str, Rule] = {}
    for rule in rules:
        if not rule.enabled or rule.task_type not in TASK_TYPES:
            continue
        existing = chosen.get(rule.task_type)
        if existing is None or (
            existing.scope == "species" and rule.scope == "specimen"
        ):
            chosen[rule.task_type] = rule
    return [chosen[key] for key in sorted(chosen)]


def water_amount_ml(subject: Subject) -> int | None:
    """A watering volume for a container, from the container's own size.

    Roughly a quarter of the pot's volume, which is the usual "until it runs
    from the base" quantity, clamped to something a person can carry. It is a
    fact about the *pot*, not about the plant, so it needs no citation — and a
    plant in the ground gets no figure at all rather than a made-up one.
    """
    if not subject.in_container or not subject.container_litres:
        return None
    return int(min(2000, max(100, round(subject.container_litres * 25))))


def caveat_note(caveats: tuple[Caveat, ...], confidence: str) -> str | None:
    """The plain-language warning that rides on ``task.detail``.

    ``detail`` is in the frozen contract, so this reaches a client that knows
    nothing about the structured fields beside it. ADR 0004 requires an uncited
    value to be *visibly* marked, and a field no released client reads would not
    be visible to anybody.
    """
    if not caveats:
        return None
    lead = (
        "This is a guess, not a measurement."
        if confidence == "unknown"
        else f"Confidence: {confidence}."
    )
    return " ".join([lead, *(caveat.detail for caveat in caveats)])


def task_row(occurrence: Occurrence) -> dict[str, Any]:
    """An occurrence as a ``task`` row, titles and ICS identity included."""
    themed, plain = titles_for(
        occurrence.rule.task_type,
        occurrence.subject.display_name,
        has_nickname=occurrence.subject.has_nickname,
        amount_ml=occurrence.amount_ml,
    )
    identity = occurrence.task_id
    return {
        "id": identity,
        "specimen_id": occurrence.subject.specimen_id,
        "care_rule_id": occurrence.rule.id,
        "task_type": occurrence.rule.task_type,
        "due_at": due_at_for(occurrence.due_on, all_day=occurrence.all_day),
        "all_day": occurrence.all_day,
        "status": occurrence.status,
        "satisfied_by": occurrence.satisfied_by,
        "amount_ml": occurrence.amount_ml,
        "priority": occurrence.priority,
        "title": themed,
        "plain_title": plain,
        "detail": caveat_note(occurrence.caveats, occurrence.confidence),
        "completed_at": None,
        "completed_by": None,
        "notes": None,
        "ics_uid": ics_uid(identity),
        "ics_sequence": 0,
        # Additive beyond contract 1.2.0, and escalated to Workstream A in the
        # pull request: ADR 0018 put these on E's answers for exactly this
        # reason, and a task built from a degraded input must not arrive
        # looking like a clean one.
        "confidence": occurrence.confidence,
        "degraded": bool(occurrence.caveats),
        "degradations": [caveat.to_dict() for caveat in occurrence.caveats],
    }
