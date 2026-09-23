"""Assembling engine inputs from whatever this deployment actually has.

The engines in ``tasks.py`` are pure functions over explicit inputs. Something
has to build those inputs, and in mock mode that something reads
``fixtures/``, which is why this module exists rather than the API doing it: a
specimen's cover factor and the confidence of its coefficient must be derived
the same way for the worker that writes ``water_balance`` rows and the endpoint
that serves them, or the two will disagree and only one of them will be right.

Nothing here decides anything. It reads, joins and converts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .ingest import Site
from .settings import WeatherSettings, get_settings
from .tasks import DayWeather, FrostNight, FrostSubject, WaterCoefficient, capacity_mm


@lru_cache(maxsize=32)
def _load(fixtures_dir: Path, relative: str) -> Any:
    path = fixtures_dir / relative
    return json.loads(path.read_text()) if path.exists() else []


def site(settings: WeatherSettings | None = None) -> Site:
    settings = settings or get_settings()
    return Site.from_fixture(_load(settings.fixtures_dir, "site.json"))


@dataclass(frozen=True, slots=True)
class SpecimenContext:
    """One plant, with everything both engines need about it."""

    specimen_id: str
    display_name: str
    is_outdoor: bool
    in_container: bool
    is_covered: bool
    capacity_mm: float
    k_c: WaterCoefficient
    min_temp_c: float | None
    min_temp_confidence: str
    #: No soil hardware exists (ADR 0010), so this is ``None`` for every plant
    #: today. It is carried anyway, because the day it stops being ``None`` the
    #: override has to already work.
    sensor_override_pct: float | None = None

    @property
    def cover_factor(self) -> float:
        """0 under a roof, 1 under open sky. The most-got-wrong term."""
        return 0.0 if self.is_covered else 1.0

    def frost_subject(self) -> FrostSubject:
        return FrostSubject(
            specimen_id=self.specimen_id,
            is_outdoor=self.is_outdoor,
            in_container=self.in_container,
            min_temp_c=self.min_temp_c,
            min_temp_confidence=self.min_temp_confidence,
            display_name=self.display_name,
        )


def specimen_contexts(
    settings: WeatherSettings | None = None,
) -> dict[str, SpecimenContext]:
    """Every specimen, joined to its species' care values and its location."""
    settings = settings or get_settings()
    fixtures_dir = settings.fixtures_dir
    species = {row["id"]: row for row in _load(fixtures_dir, "species/species.json")}
    locations = {row["id"]: row for row in _load(fixtures_dir, "locations/locations.json")}
    sources = {row["id"]: row for row in _load(fixtures_dir, "species/sources.json")}

    contexts: dict[str, SpecimenContext] = {}
    for specimen in _load(fixtures_dir, "specimens/specimens.json"):
        plant = species.get(specimen.get("species_id") or "") or {}
        location = locations.get(specimen.get("location_id") or "") or {}
        care_values = {row["field"]: row for row in plant.get("care_values") or []}

        k_c_row = care_values.get("water_k_c")
        k_c = WaterCoefficient.from_care_value(
            k_c_row, sources.get((k_c_row or {}).get("source_id") or "")
        )
        min_temp_row = care_values.get("min_temp_c") or {}

        contexts[specimen["id"]] = SpecimenContext(
            specimen_id=specimen["id"],
            display_name=_display_name(specimen, plant),
            is_outdoor=bool(specimen.get("is_outdoor")),
            in_container=bool(specimen.get("in_container")),
            is_covered=bool(location.get("is_covered")),
            capacity_mm=capacity_mm(
                bool(specimen.get("in_container")), specimen.get("container_litres")
            ),
            k_c=k_c,
            min_temp_c=_as_float(plant.get("min_temp_c")),
            min_temp_confidence=str(min_temp_row.get("confidence") or "unknown"),
        )
    return contexts


def weather_days(
    settings: WeatherSettings | None = None,
    *,
    scenario: str | None = None,
    limit: int | None = None,
) -> list[DayWeather]:
    """The site's daily weather, from a scenario or from the baseline."""
    settings = settings or get_settings()
    relative = f"scenarios/{scenario}.json" if scenario else "weather/baseline_30d.json"
    days = _load(settings.fixtures_dir, relative).get("days") or []
    if limit is not None:
        days = days[-limit:]
    return [
        DayWeather(
            day=date.fromisoformat(day["date"]),
            precip_mm=float(day.get("precip_mm") or 0.0),
            et0_mm=_as_float(day.get("et0_mm")),
            tmin_c=_as_float(day.get("tmin_c")),
            tmax_c=_as_float(day.get("tmax_c")),
        )
        for day in days
    ]


def frost_nights(
    settings: WeatherSettings | None = None, *, scenario: str | None = "frost"
) -> list[FrostNight]:
    return [
        FrostNight(day=day.day, low_c=day.tmin_c)
        for day in weather_days(settings, scenario=scenario)
        if day.tmin_c is not None
    ]


def scenario_advisories(
    settings: WeatherSettings | None = None, *, scenario: str = "frost"
) -> list[Any]:
    """The advisories a scenario declares, as ``sources.base.Advisory`` rows."""
    from .sources.base import Advisory, parse_time

    settings = settings or get_settings()
    payload = _load(settings.fixtures_dir, f"scenarios/{scenario}.json")
    return [
        Advisory(
            external_id=str(row.get("external_id") or ""),
            event=str(row.get("event") or ""),
            severity=row.get("severity"),
            onset=parse_time(row.get("onset")),
            expires=parse_time(row.get("expires")),
            headline=row.get("headline"),
        )
        for row in payload.get("advisories") or []
    ]


def _display_name(specimen: dict[str, Any], plant: dict[str, Any]) -> str:
    if specimen.get("nickname"):
        return str(specimen["nickname"])
    if plant.get("common_names"):
        return str(plant["common_names"][0]).capitalize()
    return str(plant.get("accepted_name") or "Unnamed specimen")


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
