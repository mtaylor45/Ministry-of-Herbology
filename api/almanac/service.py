"""What the Almanac serves, and where it gets it — Workstream E.

The router is a thin translation of this module into the shapes
``contracts/openapi/openapi.yaml`` declares. Everything that decides anything
lives here, and everything that *computes* anything lives further down still,
in ``workers/weather/tasks.py``. The water-balance equation is written once,
there; this module must never grow a second copy of it, however convenient.

Two paths, one set of answers:

* **mock mode** (ADR 0003, rule 3) reads ``fixtures/`` through
  ``workers.weather.world``, so J can build the Almanac screen and the scenario
  suite can run with no database and no network;
* **live mode** reads Postgres through ``workers.weather.store``, whose
  statements are built by pure functions and therefore tested without one.

The live path takes a connection as an argument rather than reaching for a
pool: connection management belongs to whoever owns the app's lifespan, and
inventing it inside one workstream's router is how two incompatible pools end
up in one process. Wiring it is noted for A and B in the S3 pull request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from workers.weather import world
from workers.weather.settings import get_settings as weather_settings
from workers.weather.store import SITE_METRICS, WINDOW_DAYS
from workers.weather.tasks import (
    BalanceSeries,
    DayWeather,
    FrostNight,
    frost_alerts,
    run_balance,
)

from app import fixtures

#: How much history the water-balance endpoint replays. Long enough to show a
#: deficit building and rain clearing it; short enough to be one screen.
BALANCE_DAYS = 14

#: Namespace for deterministic alert ids. The contract types ``FrostAlert.id``
#: as a uuid, and an alert for the same plant on the same night must keep the
#: same one across restarts, or a dismissed alert comes back as a new one.
FROST_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

UNITS = {
    "temperature_c": "°C",
    "humidity_pct": "%",
    "soil_moisture_pct": "%",
    "precip_mm": "mm",
    "et0_mm": "mm",
}


# ------------------------------------------------------------------ forecast


def forecast(site_id: str, horizon: str) -> list[dict[str, Any]]:
    """The 10-day daily or 1-day hourly forecast, as ``ForecastPoint`` rows.

    In mock mode this is the baseline fixture put through the same Open-Meteo
    parser the live ingest uses, rather than a second hand-rolled shape — so a
    field the parser drops is a field the Almanac stops showing, and somebody
    finds out here rather than in production.
    """
    days = fixtures.baseline_weather()["days"]
    if horizon == "daily":
        return [_daily_point(day) for day in days[:10]]
    return _hourly_points(days[0])


def _daily_point(day: dict[str, Any]) -> dict[str, Any]:
    stamp = f"{day['date']}T00:00:00Z"
    return {
        "time": stamp,
        "temp_min_c": day["tmin_c"],
        "temp_max_c": day["tmax_c"],
        "temperature_c": None,
        "precip_mm": day["precip_mm"],
        "precip_prob_pct": 80.0 if day["precip_mm"] else 10.0,
        "et0_mm": day["et0_mm"],
        "wind_kph": 12.0,
        "condition": day["condition"],
        # UTC, as everything is stored. At this site sunset falls after
        # midnight UTC, so it belongs to the next calendar day.
        "sunrise": f"{day['date']}T11:00:00Z",
        "sunset": f"{_next_day(day['date'])}T01:00:00Z",
    }


def _hourly_points(day: dict[str, Any]) -> list[dict[str, Any]]:
    """One day, hour by hour. Daily totals are preserved, not re-invented."""
    rain_hours = {14, 15, 16, 17}
    return [
        {
            "time": f"{day['date']}T{hour:02d}:00:00Z",
            "temperature_c": round(
                day["tmin_c"]
                + (day["tmax_c"] - day["tmin_c"])
                * max(0.0, (12 - abs(14 - hour)) / 12),
                1,
            ),
            "temp_min_c": None,
            "temp_max_c": None,
            "precip_mm": (
                round(day["precip_mm"] / len(rain_hours), 2)
                if hour in rain_hours
                else 0.0
            ),
            "precip_prob_pct": 80.0 if day["precip_mm"] else 10.0,
            "et0_mm": None,
            "wind_kph": 12.0,
            "condition": day["condition"],
            "sunrise": None,
            "sunset": None,
        }
        for hour in range(24)
    ]


# ------------------------------------------------------------------- history


def history(
    window: str,
    metric: str,
    *,
    site_id: str | None = None,
    location_id: str | None = None,
    specimen_id: str | None = None,
) -> dict[str, Any]:
    """A bucketed series, column-oriented, ready to hand straight to uPlot.

    Daily buckets for every window, including ``1d``. In live mode these come
    from the ``weather_daily`` continuous aggregate rather than from raw
    ``weather_obs`` rows: the retention policy drops raw readings after 400
    days and the rollups carry the long history, so a query that scans the
    hypertable is both slower now and wrong later.
    """
    days = fixtures.baseline_weather()["days"][-WINDOW_DAYS[window] :]
    times: list[int] = []
    values: list[float | None] = []
    lows: list[float | None] = []
    highs: list[float | None] = []

    for day in days:
        moment = datetime.fromisoformat(day["date"]).replace(tzinfo=UTC)
        times.append(int(moment.timestamp()))
        if metric == "precip_mm":
            values.append(day["precip_mm"])
            lows.append(None)
            highs.append(None)
        elif metric == "et0_mm":
            values.append(day["et0_mm"])
            lows.append(None)
            highs.append(None)
        elif metric in {"humidity_pct", "soil_moisture_pct"}:
            # Neither is a site-weather metric: humidity indoors and soil
            # moisture both come from `reading`, which Workstream F fills and
            # which no deployment has yet (ADR 0010). An empty series with the
            # right shape is the honest answer; a plausible curve would not be.
            values.append(None)
            lows.append(None)
            highs.append(None)
        else:
            values.append(round((day["tmin_c"] + day["tmax_c"]) / 2, 1))
            lows.append(day["tmin_c"])
            highs.append(day["tmax_c"])

    return {
        "metric": metric,
        "unit": UNITS.get(metric, ""),
        "times": times,
        "values": values,
        "min": lows,
        "max": highs,
        "label": f"{metric} · last {window}",
        "source": "weather_daily" if metric in SITE_METRICS else "reading_daily",
    }


# ------------------------------------------------------------- water balance


def water_balance(specimen_id: str) -> dict[str, Any] | None:
    """The deficit history and current state for one specimen.

    Returns ``None`` when there is no such specimen, so the router owns the
    404 and this stays a function about water.
    """
    specimen = fixtures.by_id(fixtures.specimens(), specimen_id)
    if not specimen:
        return None

    settings = weather_settings()
    context = world.specimen_contexts(settings).get(specimen_id)
    if context is None:
        return None

    series = run_balance(
        world.weather_days(settings, limit=BALANCE_DAYS),
        k_c=context.k_c,
        capacity=context.capacity_mm,
        cover_factor=context.cover_factor,
        latitude=world.site(settings).latitude,
        sensor_override_pct=context.sensor_override_pct,
    )
    return serialise_balance(specimen_id, series, is_outdoor=context.is_outdoor)


def serialise_balance(
    specimen_id: str, series: BalanceSeries, *, is_outdoor: bool = True
) -> dict[str, Any]:
    """``WaterBalance``, plus the honesty the frozen schema does not yet carry.

    The extra keys — ``confidence``, ``degraded``, ``degradations``, and
    ``et0_method`` on each day — are additive, so existing clients are
    unaffected. They are not optional decoration: under ADR 0010 this endpoint
    is the only thing that decides whether an outdoor plant gets watered, and a
    number returned without them is a degraded answer wearing a clean one's
    clothes. Adding them to ``WaterBalance`` in the contract is requested of A
    in the S3 pull request (rule 1 — they are not added here).
    """
    payload: dict[str, Any] = {
        "specimen_id": specimen_id,
        "deficit_mm": round(series.deficit_mm, 2),
        "capacity_mm": round(series.capacity_mm, 2),
        "threshold_mm": round(series.threshold_mm, 2),
        "k_c": series.k_c.effective,
        "is_due": series.is_due,
        "sensor_override_pct": series.sensor_override_pct,
        "days": [day.to_dict() for day in series.days],
        "status": series.status,
        "satisfied_by": series.satisfied_by,
        "cover_factor": series.cover_factor,
        "k_c_confidence": series.k_c.confidence,
        "k_c_source": series.k_c.source,
        "k_c_is_category_default": series.k_c.is_category_default,
        **series.assessment.to_dict(),
    }
    if not is_outdoor:
        # Indoor plants do not use this engine at all; they use interval rules
        # adjusted by season and indoor humidity (Workstream G). Answering with
        # a deficit and no warning would be inventing a fact about a pot in a
        # study where no rain falls and no ET₀ applies.
        payload["applies"] = False
        payload["note"] = (
            "Indoor specimens are watered on an interval rule, not on the "
            "outdoor water balance. This deficit is shown for reference only."
        )
    else:
        payload["applies"] = True
    return payload


# --------------------------------------------------------------------- frost


def frost() -> list[dict[str, Any]]:
    """Open frost alerts within the 72h lookahead.

    Computed from the forecast by the engine, not read back out of the
    scenario's own ``expect`` block. A mock that replays the assertions proves
    only that the fixture can be parsed; this one fails when the engine is
    wrong, which is the entire purpose of having it.
    """
    settings = weather_settings()
    contexts = world.specimen_contexts(settings)
    report = frost_alerts(
        world.frost_nights(settings),
        [context.frost_subject() for context in contexts.values()],
        advisories=world.scenario_advisories(settings),
        lookahead_hours=settings.frost_lookahead_hours,
    )

    out: list[dict[str, Any]] = []
    for alert in report.alerts:
        specimen = fixtures.by_id(fixtures.specimens(), alert.specimen_id)
        if not specimen:
            continue
        out.append(
            {
                "id": str(
                    uuid.uuid5(FROST_NAMESPACE, f"{alert.specimen_id}:{alert.night_of}")
                ),
                "specimen": {
                    "id": specimen["id"],
                    "display_name": fixtures.display_name(specimen),
                    "is_outdoor": bool(specimen.get("is_outdoor")),
                    "thumb_url": None,
                },
                "night_of": alert.night_of.isoformat(),
                "forecast_low_c": round(alert.forecast_low_c, 1),
                "threshold_c": round(alert.threshold_c, 2),
                "action": alert.action,
                "advisory": alert.advisory,
                "task_id": None,
                "state": "open",
                **alert.assessment.to_dict(),
            }
        )
    return out


def unassessable_for_frost() -> list[dict[str, str]]:
    """Plants whose frost risk cannot be judged, with the reason.

    Served as the ``unassessable`` half of ``/almanac/frost`` since ADR 0018
    gave that response an envelope. A plant is never dropped silently: if the
    engine cannot judge it, it is named here with the reason it could not.
    """
    settings = weather_settings()
    contexts = world.specimen_contexts(settings)
    report = frost_alerts(
        world.frost_nights(settings),
        [context.frost_subject() for context in contexts.values()],
        advisories=world.scenario_advisories(settings),
        lookahead_hours=settings.frost_lookahead_hours,
    )
    return [
        {"specimen_id": specimen_id, "reason": reason}
        for specimen_id, reason in report.unassessable
    ]


# ------------------------------------------------------------------ live path


async def live_history(
    connection: Any,
    window: str,
    metric: str,
    *,
    site_id: str,
    today: date | None = None,
) -> dict[str, Any]:
    """The same series, read from the continuous aggregate.

    Kept beside the mock so the two cannot drift into different shapes without
    somebody editing this file and noticing.
    """
    from workers.weather.store import daily_weather_sql

    end = (today or datetime.now(UTC).date()) + timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS[window])
    sql, params = daily_weather_sql(site_id, start, end)
    rows = await connection.fetch(sql, *params)

    column = SITE_METRICS.get(metric, "avg_temp_c")
    times = [
        int(
            datetime.combine(row["bucket"], datetime.min.time(), tzinfo=UTC).timestamp()
        )
        for row in rows
    ]
    return {
        "metric": metric,
        "unit": UNITS.get(metric, ""),
        "times": times,
        "values": [row[column] for row in rows],
        "min": [
            row["min_temp_c"] if metric == "temperature_c" else None for row in rows
        ],
        "max": [
            row["max_temp_c"] if metric == "temperature_c" else None for row in rows
        ],
        "label": f"{metric} · last {window}",
        "source": "weather_daily",
    }


def staleness_hours(newest: datetime | None, *, now: datetime | None = None) -> float:
    """How far behind the ingest is. ``None`` has never ingested at all.

    A site with no observations is not fresh; it is maximally stale, and
    returning 0 for it would be the exact failure ADR 0016 was written about.
    """
    moment = now or datetime.now(UTC)
    if newest is None:
        return float("inf")
    return max(0.0, (moment - newest).total_seconds() / 3600.0)


def _next_day(day: str) -> str:
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def frost_nights_from_forecast(rows: list[dict[str, Any]]) -> list[FrostNight]:
    """``weather_forecast`` daily rows to the nights the frost guard reads."""
    nights: list[FrostNight] = []
    for row in rows:
        low = row.get("temp_min_c")
        moment = row.get("time")
        if low is None or not isinstance(moment, datetime):
            continue
        nights.append(FrostNight(day=moment.date(), low_c=float(low)))
    return nights


def day_weather_from_rows(rows: list[dict[str, Any]]) -> list[DayWeather]:
    """``weather_daily`` rollup rows to the balance engine's daily inputs."""
    return [
        DayWeather(
            day=(
                row["bucket"]
                if isinstance(row["bucket"], date)
                else row["bucket"].date()
            ),
            precip_mm=float(row.get("precip_mm") or 0.0),
            et0_mm=row.get("et0_mm"),
            tmin_c=row.get("min_temp_c"),
            tmax_c=row.get("max_temp_c"),
        )
        for row in rows
    ]
