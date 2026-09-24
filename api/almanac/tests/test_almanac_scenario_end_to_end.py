"""The whole chain, through the running app — Workstream E, S5.

The sprint's exit criterion is *rain visibly clears due waterings*, and on
``main`` ``GET /api/v1/tending/rounds`` returned ``satisfied: []`` against every
fixture. The engine was not the reason: replayed directly, it marked the storm's
rain day ``satisfied`` exactly as ``fixtures/scenarios/storm.json`` expects. The
reason was that the *running app* could not be put under a scenario at all, so
the only weather it ever saw was ``weather/baseline_30d.json``, whose closing
fortnight has no downpour big enough to clear anybody's deficit.

This file drives the same path an operator does — environment variables, then
HTTP — across all four links:

    rainfall  →  water balance  →  ``status: satisfied`` / ``satisfied_by: rain``
              →  ``api/tending/domain.py``  →  the ``satisfied`` section of the round

It is deliberately an end-to-end test rather than four unit tests. Each link
was individually sound on ``main`` and the chain still produced nothing, which
is precisely the class of defect a unit test cannot see.

``tests/`` and ``fixtures/`` are Workstream L's and are not touched here; this
is E's own suite, reading the frozen scenario L already owns.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from workers.weather.settings import get_settings as weather_settings

#: The day of ``storm`` on which 38 mm of rain falls. The recording runs three
#: days past it; a balance replayed to the end honestly reports the deficit that
#: has rebuilt since, which is the right answer to a question nobody asked.
STORM_RAIN_DAY = "2026-07-07"

LEMON_ON_TERRACE = "01890040-0000-7000-8000-000000000004"  # 45 L, open sky
LEMON_ON_PORCH = "01890040-0000-7000-8000-000000000005"  # 25 L, under a roof


@pytest.fixture
def under_storm(monkeypatch: pytest.MonkeyPatch):
    """The app as an operator running the storm demo would have it.

    Set through the environment rather than by handing a settings object
    around, because the environment is the only route a deployment has (ADR
    0019) and a demo that works only from Python has not been demonstrated.
    """
    from app.main import app

    monkeypatch.setenv("MOH_WEATHER_SCENARIO", "storm")
    monkeypatch.setenv("MOH_WEATHER_SCENARIO_DAY", STORM_RAIN_DAY)
    weather_settings.cache_clear()
    yield TestClient(app)
    weather_settings.cache_clear()


@pytest.fixture
def unset(monkeypatch: pytest.MonkeyPatch):
    """The shipped default: no scenario, the baseline recording."""
    from app.main import app

    monkeypatch.delenv("MOH_WEATHER_SCENARIO", raising=False)
    monkeypatch.delenv("MOH_WEATHER_SCENARIO_DAY", raising=False)
    weather_settings.cache_clear()
    yield TestClient(app)
    weather_settings.cache_clear()


def rounds(client: TestClient) -> dict:
    response = client.get("/api/v1/tending/rounds")
    assert response.status_code == 200
    return response.json()


def balance(client: TestClient, specimen_id: str) -> dict:
    response = client.get(f"/api/v1/almanac/water-balance/{specimen_id}")
    assert response.status_code == 200
    return response.json()


def test_rain_clears_a_due_watering_all_the_way_to_morning_rounds(under_storm):
    """The exit criterion, end to end and on the wire."""
    settled = rounds(under_storm)["satisfied"]

    assert settled, "38 mm of rain settled nothing that the round shows"
    assert all(task["status"] == "satisfied" for task in settled)
    assert {task["satisfied_by"] for task in settled} == {"rain"}
    assert LEMON_ON_TERRACE in {task["specimen"]["id"] for task in settled}


def test_the_settled_watering_keeps_its_place_rather_than_vanishing(under_storm):
    """The plan is explicit: the task must not simply disappear overnight.

    Somebody who saw "water the lemon" yesterday needs to be told the sky did
    it, not left wondering whether they imagined the task.
    """
    settled = next(
        task
        for task in rounds(under_storm)["satisfied"]
        if task["specimen"]["id"] == LEMON_ON_TERRACE
    )
    assert settled["task_type"] == "water"
    assert settled["plain_title"], "the plain-language equivalent, always (rule 7)"
    assert settled["id"] and settled["due_at"]


def test_the_balance_underneath_it_attributes_the_rain(under_storm):
    """The link G reads. ``status`` and ``satisfied_by`` are E's words for it."""
    payload = balance(under_storm, LEMON_ON_TERRACE)
    assert payload["status"] == "satisfied"
    assert payload["satisfied_by"] == "rain"
    assert payload["is_due"] is False
    assert payload["deficit_mm"] == 0.0

    rain_day = payload["days"][-1]
    assert rain_day["day"] == STORM_RAIN_DAY
    assert rain_day["status"] == "satisfied"
    assert rain_day["precip_mm"] == 38.0


def test_a_plant_under_a_roof_is_not_watered_by_rain_it_never_saw(under_storm):
    """``f_cover`` is the most commonly got-wrong term in the equation.

    The same downpour, the same site, the same day: a lemon on the covered
    porch still owes a watering, and the scenario says so in its own words.
    """
    payload = balance(under_storm, LEMON_ON_PORCH)
    assert payload["cover_factor"] == 0.0
    assert payload["status"] == "due"
    assert payload["satisfied_by"] is None

    due = {task["specimen"]["id"] for task in rounds(under_storm)["due"]}
    assert LEMON_ON_PORCH in due


def test_the_almanac_shows_the_same_week_the_balance_ran_on(under_storm):
    """One deployment, one weather. Two loaders is how those come apart."""
    forecast = under_storm.get(
        "/api/v1/almanac/forecast", params={"site_id": "x", "horizon": "daily"}
    ).json()
    assert forecast[0]["time"].startswith(STORM_RAIN_DAY)
    assert forecast[0]["precip_mm"] == 38.0

    history = under_storm.get(
        "/api/v1/almanac/history", params={"window": "7d", "metric": "precip_mm"}
    ).json()
    assert history["values"][-1] == 38.0


def test_the_certainty_survives_the_trip_to_the_instruction(under_storm):
    """ADR 0020: the task a person acts on carries the doubt, not just the API.

    A watering settled by a modelled deficit is still a modelled deficit, and
    nothing measures the soil (ADR 0010).
    """
    settled = next(
        task
        for task in rounds(under_storm)["satisfied"]
        if task["specimen"]["id"] == LEMON_ON_TERRACE
    )
    assert settled["confidence"] in {"high", "medium", "low", "unknown"}
    assert settled["confidence"] != "high", "nothing measured this soil"
    assert "degraded" in settled and "degradations" in settled


def test_an_unset_scenario_leaves_the_deployment_exactly_as_it_was(unset):
    """The switch is opt-in. A deployment that sets nothing sees no change."""
    payload = balance(unset, LEMON_ON_TERRACE)
    assert payload["days"][-1]["day"] == "2026-05-30", "the baseline recording"
    assert payload["status"] == "due"

    day = rounds(unset)
    assert day["satisfied"] == []
    assert len(day["due"]) == 9
