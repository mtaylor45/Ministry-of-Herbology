"""The one place this package asks Workstream E what the world is doing.

The plan's handoff is "E → G: daily deficit and frost flags feed task
generation". This module is that handoff and nothing else lives in it, so the
scheduling engine stays a pure function of its arguments and there is exactly
one import of somebody else's module to review.

Nothing here computes a deficit, an ET₀ figure or a rain total. ADR 0018 made
E's answers carry their own confidence precisely so that a consumer could pass
it on; a second, quieter copy of the water-balance equation in this package
would be the failure that ADR warns about, built on purpose.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tending.domain import Caveat, Environment


def _caveats(payload: dict[str, Any]) -> tuple[Caveat, ...]:
    return tuple(
        Caveat(
            code=str(row.get("code") or "unknown"),
            detail=str(row.get("detail") or ""),
            caps_at=str(row.get("caps_at") or "medium"),
        )
        for row in payload.get("degradations") or []
    )


def _newest_day(payload: dict[str, Any]) -> date | None:
    days = payload.get("days") or []
    if not days:
        return None
    try:
        return date.fromisoformat(str(days[-1]["day"]))
    except (KeyError, TypeError, ValueError):
        return None


def from_water_balance(payload: dict[str, Any] | None) -> Environment:
    """E's ``WaterBalance`` response, as the scheduler's view of one plant.

    ``applies`` is E's own word for "this engine has an opinion here": an indoor
    pot gets a deficit for reference only, and scheduling a watering from it
    would be inventing weather in a study.
    """
    if not payload:
        return Environment()
    return Environment(
        applies=bool(payload.get("applies")),
        balance_status=payload.get("status"),
        satisfied_by=payload.get("satisfied_by"),
        is_due=bool(payload.get("is_due")),
        confidence=str(payload.get("confidence") or "unknown"),
        degradations=_caveats(payload),
        newest_day=_newest_day(payload),
    )


def fixture_environments(specimen_ids: list[str]) -> dict[str, Environment]:
    """Mock mode: ask the Almanac, which reads the same fixtures everyone does.

    Wrapped in a broad ``except`` on purpose. E's engine deciding it cannot
    answer for one plant must leave that plant unscheduled and the other eleven
    scheduled — not take Morning Rounds down for the household.
    """
    from almanac import service as almanac

    out: dict[str, Environment] = {}
    for specimen_id in specimen_ids:
        try:
            payload = almanac.water_balance(specimen_id)
        except Exception:  # noqa: BLE001 — one plant's engine, not the app's
            payload = None
        out[specimen_id] = from_water_balance(payload)
    return out


def fixture_frost_alerts() -> list[dict[str, Any]]:
    """Open frost alerts, for the ``alerts`` half of Morning Rounds.

    Read, not raised: the frost *engine* is E's and the bring-indoors task it
    justifies is Sprint 6's. Morning Rounds shows what E already knows today.
    """
    from almanac import service as almanac

    try:
        return list(almanac.frost())
    except Exception:  # noqa: BLE001
        return []


def fixture_weather_today() -> dict[str, Any] | None:
    """The day's forecast point, as the contract's ``ForecastPoint``."""
    from almanac import service as almanac

    try:
        days = almanac.forecast("", "daily")
    except Exception:  # noqa: BLE001
        return None
    return days[0] if days else None


def from_balance_row(row: Any, *, today: date) -> Environment:
    """Live mode: one ``water_balance`` row, which is all the table can say.

    The table stores the deficit and the threshold. It does **not** store the
    confidence or the degradations ADR 0018 put on the API response, so this
    path cannot pass through what it cannot read — it reports a modelled
    deficit at ``medium``, which is what ``workers/weather/quality.py`` itself
    calls a modelled figure worth, and adds the staleness it *can* verify.

    That gap is real and is raised with Workstream A in the pull request: the
    honest fix is columns on ``water_balance``, not a guess here.
    """
    if row is None:
        return Environment()
    deficit = float(row.deficit_mm)
    threshold = float(row.threshold_mm)
    override = row.sensor_override_pct
    # A probe outranks the model (ADR 0010). No hardware drives this today.
    is_due = float(override) < 30.0 if override is not None else deficit >= threshold
    return Environment(
        applies=True,
        balance_status="due" if is_due else "ok",
        satisfied_by=None,
        is_due=is_due,
        confidence="medium",
        degradations=(),
        newest_day=row.day if isinstance(row.day, date) else today,
    )
