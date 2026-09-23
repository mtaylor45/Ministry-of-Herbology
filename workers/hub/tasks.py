"""Home & IoT worker — Workstream F.

The Home Assistant adapter and the MQTT publish-back, as Arq jobs.

## What this file is responsible for

The sprint's exit criterion is **indoor and outdoor readings stored every 5–15
minutes**. Workstream E landed the outdoor half; :func:`poll_home_assistant` is
the indoor half, and under ADR 0009 it is the *only* route to indoor
conditions — there is no direct Nest integration and none is planned. If this
job stops, nothing else fills in behind it.

That makes one failure worse than being wrong: **being silent**. A job that
stops running leaves the last readings in place, the Almanac draws a line
through the gap, and a household sees a chart that looks like a steady 21 °C
room. So every run here leaves a mark whether it worked or not —
``integration.last_ok_at`` and ``integration.last_error`` for the current
state, ``job_run`` for the history — and every entity that was asked for and
did not produce a reading is *named* in the job's return value, with a reason.
Nothing is dropped quietly.

## Shape

Every job returns a plain dict rather than writing and staying silent, so a
run's outcome is visible in Arq's result store and in a test with no database
— the same rule Workstream E's jobs follow, and for the same reason: a job
that can only be observed by querying Postgres is a job nobody checks.

Where ``ctx`` carries a ``connection``, rows are persisted through
:mod:`workers.hub.store`; where it does not — mock mode, and every test — the
job still does the work and reports it.

## Cadence

``poll_home_assistant`` is scheduled every five minutes, the fast end of the
sprint's 5–15 minute band, and each ``sensor_source`` then decides for itself
whether it is due via its own ``poll_seconds``. A thermostat is not a soil
probe: the cron sets the *finest* cadence available, the row sets the one it
wants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from .entities import SOIL_METRICS, SUPPORTED_METRICS  # noqa: F401  (ADR 0010)
from .health import IntegrationHealth, SourceHealth, health_report, redact
from .mapping import SensorSource, pollable, validation_errors
from .mqtt import (  # noqa: F401  — the topic layout is contract, re-exported
    DISCOVERY_PREFIX,
    MQTT_PREFIX,
    MemoryPublisher,
    availability,
    discovery_messages,
    discovery_topic,
    frost_messages,
    object_id_for,
    publish_all,
    rounds_messages,
    specimen_messages,
    state_topic,
)
from .settings import HubSettings, get_settings
from .sources.base import HOME_ASSISTANT, HubUnavailable, PollResult

#: The ``integration`` row this worker keeps. ``kind`` is from the schema's
#: CHECK constraint; ``name`` is what the Ministry Office prints.
HA_INTEGRATION = (HOME_ASSISTANT, "Home Assistant")
MQTT_INTEGRATION = ("mqtt", "MQTT broker")


def _settings(ctx: dict[str, Any]) -> HubSettings:
    settings = ctx.get("settings")
    return settings if isinstance(settings, HubSettings) else get_settings()


def _secrets(settings: HubSettings) -> tuple[str, ...]:
    """The values :func:`~workers.hub.health.redact` must remove literally."""
    return tuple(
        value
        for value in (
            settings.ha_token.get_secret_value(),
            settings.mqtt_password.get_secret_value(),
        )
        if value
    )


async def _sources_for(ctx: dict[str, Any]) -> list[SensorSource]:
    """The configured sources: from ``ctx``, then the database, then the mock.

    The ``ctx`` override exists for the API, which may already hold them, and
    for tests. Everything else is the ordinary path.
    """
    provided = ctx.get("sources")
    if provided is not None:
        return [
            item if isinstance(item, SensorSource) else SensorSource.from_row(item)
            for item in provided
        ]
    connection = ctx.get("connection")
    if connection is not None:
        from . import store

        rows = await store.read_sensor_sources(connection)
        return [SensorSource.from_row(dict(row)) for row in rows]
    from . import world

    return world.sensor_sources(_settings(ctx))


async def poll_home_assistant(
    ctx: dict[str, Any], source_id: str | None = None
) -> dict[str, Any]:
    """Read every due sensor source and store what came back.

    ``source_id`` polls one row regardless of whether it is due — what the
    "test this sensor" button in the Ministry Office needs, and what someone
    debugging a mapping wants.

    The return value is the whole story of the run: what was polled, what was
    stored, and every entity that was asked for and did not answer, with a
    reason each. That list is the point of this job as much as the readings
    are.
    """
    from . import store
    from .factory import get_source

    settings = _settings(ctx)
    started_at = datetime.now(UTC)
    secrets = _secrets(settings)

    sources = await _sources_for(ctx)
    problems: list[str] = []
    for source in sources:
        problems.extend(validation_errors(source))

    candidates = pollable(sources)
    if source_id:
        due = [source for source in candidates if source.id == source_id]
        if not due:
            return _report(
                started_at,
                ok=False,
                error=f"no enabled Home Assistant source with id {source_id}",
                sources=len(sources),
            )
    else:
        due = [source for source in candidates if source.is_due(started_at)]

    if not due:
        # Not an error and not a success: nothing was asked of Home Assistant,
        # so nothing was learned about it. Stamping `last_ok_at` here would
        # make a deployment with every source disabled look healthy forever.
        return _report(
            started_at,
            ok=True,
            sources=len(sources),
            polled=0,
            skipped_sources=[source.name for source in candidates],
            problems=problems,
            note="no source was due",
        )

    source_api = ctx.get("source") or get_source()
    result: PollResult = await source_api.poll(due, now=started_at)

    connection = ctx.get("connection")
    stored = 0
    if connection is not None and result.readings:
        stored = await store.write_readings(connection, result.readings)
        touched = sorted({reading.time.date() for reading in result.readings})
        await store.refresh_aggregates(connection, touched[0], touched[-1])

    error = _error_for(result, due, problems, secrets)
    finished_at = datetime.now(UTC)
    detail = result.to_dict()
    if connection is not None:
        kind, name = HA_INTEGRATION
        if result.ok:
            await store.record_ok(connection, kind, name, finished_at)
        if error:
            await store.record_error(connection, kind, name, error)
        await store.record_job_run(
            connection,
            "poll_home_assistant",
            started_at=started_at,
            finished_at=finished_at,
            ok=result.ok and not error,
            detail=detail,
        )

    return _report(
        started_at,
        ok=result.ok and not error,
        error=error,
        sources=len(sources),
        polled=len(due),
        stored=stored,
        problems=problems,
        finished_at=finished_at,
        # ``ok`` and ``error`` are decided above, over the whole run rather
        # than over the fetch alone: a hub that answered and produced nothing
        # is a failure the fetch does not know about.
        **{k: v for k, v in detail.items() if k not in {"ok", "error"}},
    )


def _error_for(
    result: PollResult,
    due: list[SensorSource],
    problems: list[str],
    secrets: tuple[str, ...],
) -> str | None:
    """What belongs on ``integration.last_error`` after this run.

    Three cases, in order of how much they tell an operator:

    1. Home Assistant could not be reached — say that, and nothing else.
    2. It answered and **not one** mapped entity produced a reading. That is
       a working hub and a broken configuration, and it is the case that would
       otherwise pass as success: the job ran, no exception was raised, and
       the hypertable stayed empty.
    3. Some entities were refused, or a row is misconfigured. Named, because a
       partly-working mapping is the one people never get round to fixing.

    The result is always redacted. This string is rendered in the Ministry
    Office, and a Home Assistant error can quote a URL somebody put
    credentials in.
    """
    if result.error:
        return redact(result.error, secrets)
    reasons: list[str] = list(problems)
    if due and not result.readings:
        detail = ", ".join(
            sorted({f"{item.entity_id}: {item.reason}" for item in result.skipped})
        )
        reasons.insert(
            0,
            "Home Assistant answered, but no mapped entity produced a reading"
            + (f" ({detail})" if detail else ""),
        )
    elif result.skipped:
        detail = ", ".join(
            sorted({f"{item.entity_id}: {item.reason}" for item in result.skipped})
        )
        reasons.append(f"some entities produced no reading ({detail})")
    return redact("; ".join(reasons), secrets) if reasons else None


async def check_home_assistant(ctx: dict[str, Any]) -> dict[str, Any]:
    """Ask Home Assistant whether it is there, and record the answer.

    Separate from the poll on purpose. A deployment with no sources configured
    yet still needs the Ministry Office to say whether the hub is reachable —
    that is the screen someone looks at *while* setting it up, and a health
    check that only runs when there is something to poll is a health check
    that is absent exactly when it is wanted.
    """
    from . import store
    from .factory import get_source

    settings = _settings(ctx)
    started_at = datetime.now(UTC)
    source_api = ctx.get("source") or get_source()
    connection = ctx.get("connection")
    kind, name = HA_INTEGRATION

    if not settings.is_configured and not settings.mock_mode:
        return {
            "job": "check_home_assistant",
            "ok": False,
            "status": "unconfigured",
            "error": "MOH_HA_BASE_URL and MOH_HA_TOKEN are not set",
        }

    try:
        message = await source_api.probe()
    except HubUnavailable as exc:
        error = redact(str(exc), _secrets(settings)) or str(exc)
        if connection is not None:
            await store.record_error(connection, kind, name, error)
        return {
            "job": "check_home_assistant",
            "ok": False,
            "status": "down",
            "error": error,
        }

    finished_at = datetime.now(UTC)
    if connection is not None:
        await store.record_ok(connection, kind, name, finished_at)
    return {
        "job": "check_home_assistant",
        "ok": True,
        "status": "ok",
        "message": message,
        "took_ms": round((finished_at - started_at).total_seconds() * 1000, 1),
        "is_mock": getattr(source_api.fetcher, "is_mock", False),
    }


async def hub_health(ctx: dict[str, Any]) -> dict[str, Any]:
    """What the Ministry Office screen shows: is the hub actually answering?

    The report distinguishes four things a single "is it up" boolean cannot:
    an integration nobody has configured, one that is configured and failing,
    one that has not been *heard from* — no error, no recent success, which is
    what a stopped worker looks like — and a source that is configured, fine
    as far as the hub is concerned, and has not produced a reading in hours.
    """
    from . import store, world

    settings = _settings(ctx)
    now = datetime.now(UTC)
    connection = ctx.get("connection")

    if connection is not None:
        rows = await store.read_integrations(connection)
        integrations = [IntegrationHealth.from_row(dict(row)) for row in rows]
    else:
        integrations = world.integrations(settings)

    sources = await _sources_for(ctx)
    return health_report(
        integrations,
        [SourceHealth.from_source(source) for source in sources],
        now=now,
        floor_s=settings.source_stale_after_s,
    )


async def publish_to_mqtt(ctx: dict[str, Any]) -> dict[str, Any]:
    """Publish the Ministry's state back into Home Assistant over MQTT.

    ``contracts/events/mqtt.md`` is the contract: retained discovery configs,
    retained state, one availability topic that everything hangs off. Every
    message goes through :func:`~workers.hub.mqtt.guard`, which refuses a
    payload carrying anything credential-shaped — the contract's "nothing
    secret goes in a payload", enforced rather than remembered.

    The live transport is not built: ``api/pyproject.toml`` carries no MQTT
    client and Workstream F does not own it (rule 2), so adding ``aiomqtt`` is
    a request to A and B and is in this sprint's pull request. With no
    publisher in ``ctx`` this job builds every message, guards it, and reports
    what it *would* send — which is what the tests assert, and which is the
    useful half anyway: the bytes on the topic, not the library that carried
    them.
    """
    rounds = ctx.get("rounds") or {}
    frost = ctx.get("frost") or {}
    specimens = ctx.get("specimens") or []
    version = str(ctx.get("sw_version") or "1.0.0")

    messages = [availability(True)]
    messages += discovery_messages(
        specimen_ids=[
            str(row.get("specimen_id") or row.get("id")) for row in specimens
        ],
        sw_version=version,
    )
    messages += rounds_messages(
        due=int(rounds.get("due") or 0),
        overdue=int(rounds.get("overdue") or 0),
        tasks=rounds.get("tasks") or (),
    )
    messages += frost_messages(
        active=bool(frost.get("active")),
        night=frost.get("night"),
        low_c=frost.get("low_c"),
        specimens=frost.get("specimens") or (),
        next_frost=frost.get("next"),
    )
    for row in specimens:
        messages += specimen_messages(
            str(row.get("specimen_id") or row.get("id")),
            water_due=bool(row.get("water_due")),
            deficit_mm=row.get("deficit_mm"),
        )

    publisher = ctx.get("publisher") or MemoryPublisher()
    sent = await publish_all(publisher, messages)
    return {
        "job": "publish_to_mqtt",
        "ok": True,
        "published": len(sent),
        "retained": sum(1 for message in sent if message.retain),
        "topics": [message.topic for message in sent],
        "transport": type(publisher).__name__,
    }


def _report(
    started_at: datetime,
    *,
    ok: bool,
    error: str | None = None,
    finished_at: datetime | None = None,
    **extra: Any,
) -> dict[str, Any]:
    finished = finished_at or datetime.now(UTC)
    return {
        "job": "poll_home_assistant",
        "ok": ok,
        "error": error,
        "started_at": started_at.isoformat(),
        "took_ms": round((finished - started_at).total_seconds() * 1000, 1),
        **extra,
    }


class WorkerSettings:
    """Arq entrypoint.

    The schedules follow the sprint's exit criterion — indoor readings stored
    every 5–15 minutes. Five for the poll, which is the finest cadence any row
    asks for; five for the health check, offset by two minutes so the Ministry
    Office learns the hub is down from a cheap ``GET /api/`` rather than from
    a poll that had to time out first.
    """

    functions: ClassVar[list] = [
        poll_home_assistant,
        check_home_assistant,
        hub_health,
        publish_to_mqtt,
    ]

    cron_jobs: ClassVar[list] = []


def _build_cron_jobs() -> list[Any]:
    """Built lazily so importing this module never requires Arq to be installed.

    :data:`SUPPORTED_METRICS` and the topic helpers are imported by other
    workstreams and by the mocks, neither of which runs jobs. A missing
    scheduler dependency must not take the adapter's constants down with it.
    """
    try:
        from arq import cron
    except ImportError:  # pragma: no cover - arq is a declared dependency
        return []

    return [
        cron(poll_home_assistant, minute=set(range(0, 60, 5)), run_at_startup=True),
        cron(
            check_home_assistant,
            minute={2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57},
            run_at_startup=True,
        ),
        # After the poll and after G's rules have run for the morning.
        cron(publish_to_mqtt, minute={10, 40}),
    ]


WorkerSettings.cron_jobs = _build_cron_jobs()
