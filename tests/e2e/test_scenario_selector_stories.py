"""The whole app under ``storm`` and under ``drought``, driven by the fixtures.

Owner: Workstream L. **Skipped until Workstream E's scenario selector lands**
(``ws-e/s5-water-balance``). Nothing here is a second mechanism: the seam is
``workers.weather.world.weather_days(..., scenario=...)``, which already takes
the argument, lifted to a setting so the *running app* can be put under a
scenario instead of the baseline. This suite reads that setting off
``WeatherSettings`` and runs when it exists.

What it gains over the rest of the suite, which drives the same code paths on
the shipped baseline: the fixtures' ``expect`` blocks become executable.
``fixtures/README.md`` says the ``expect`` block is the contract and that
``tests/`` asserts each one — until the selector exists, only the engine-level
tests in ``tests/engines/`` can, and they assert arithmetic rather than screens.
These assert screens.

If Workstream E names the setting something other than ``scenario``, this file
is a one-line change (:data:`SCENARIO_SETTING`) and the skip disappears.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from conftest import (  # type: ignore[import-not-found]
    ics_events,
    load_fixture,
    subscribe,
    tasks_by_specimen,
)

#: The field this suite expects on ``workers.weather.settings.WeatherSettings``,
#: configured as ``MOH_SCENARIO`` like every other setting in the stack.
SCENARIO_SETTING = "scenario"


def _selector_has_landed() -> bool:
    from workers.weather.settings import WeatherSettings

    return SCENARIO_SETTING in WeatherSettings.model_fields


pytestmark = pytest.mark.skipif(
    not _selector_has_landed(),
    reason=(
        f"Workstream E's scenario selector has not landed: "
        f"`WeatherSettings.{SCENARIO_SETTING}` does not exist, so the running "
        "app cannot be put under a scenario and only the baseline weather can "
        "be driven end to end. The seam is "
        "`workers.weather.world.weather_days(..., scenario=...)`, which already "
        "takes the argument; E is lifting it to a setting on "
        "`ws-e/s5-water-balance`. Written against that seam and left skipped "
        "rather than routed around with a second mechanism."
    ),
)


@contextmanager
def under_scenario(name: str) -> Iterator[Any]:
    """Run the whole app on one scenario's weather, then put it back.

    Both settings objects and both fixture loaders are cached, so the caches
    are dropped on the way in and on the way out. Leaving one warm would let a
    scenario leak into the next test, which is the one failure mode a suite
    about determinism cannot have.
    """
    from app import fixtures as app_fixtures
    from app.main import app
    from app.settings import get_settings as app_settings
    from fastapi.testclient import TestClient
    from tending.fixture_repository import reset_fixture_repository

    from workers.weather import world
    from workers.weather.settings import get_settings as weather_settings

    def clear() -> None:
        weather_settings.cache_clear()
        app_settings.cache_clear()
        world._load.cache_clear()
        for loader in (
            app_fixtures.site,
            app_fixtures.locations,
            app_fixtures.species,
            app_fixtures.sources,
            app_fixtures.specimens,
            app_fixtures.scenario,
            app_fixtures.baseline_weather,
        ):
            loader.cache_clear()
        reset_fixture_repository()

    previous = os.environ.get("MOH_SCENARIO")
    os.environ["MOH_SCENARIO"] = name
    clear()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous is None:
            os.environ.pop("MOH_SCENARIO", None)
        else:
            os.environ["MOH_SCENARIO"] = previous
        clear()


def scenario_day(name: str, index: int) -> str:
    return str(load_fixture(f"scenarios/{name}.json")["days"][index]["date"])


def expectations(name: str) -> list[dict[str, Any]]:
    """The fixture's own ``expect.assertions``, as the README promises."""
    return [
        row
        for row in load_fixture(f"scenarios/{name}.json")["expect"]["assertions"]
        if "specimen" in row
    ]


# ------------------------------------------------------------------- storm


def test_the_storm_fixture_expectations_hold_on_the_running_app() -> None:
    """Every ``expect`` row in ``storm.json``, asserted against the API."""
    rows = expectations("storm")
    assert rows, "a scenario with no expectations tests nothing"

    with under_scenario("storm") as client:
        on = scenario_day("storm", -1)
        payload = client.get("/api/v1/tending/rounds", params={"on": on}).json()
        due = tasks_by_specimen(payload["due"])
        satisfied = tasks_by_specimen(payload["satisfied"])

        for row in rows:
            specimen_id = row["specimen"]
            expected = row["water_task_status"]
            note = row.get("note", "")
            balance = client.get(f"/api/v1/almanac/water-balance/{specimen_id}").json()

            if expected == "satisfied":
                assert specimen_id in satisfied, f"{specimen_id}: {note}"
                task = satisfied[specimen_id]
                assert task["status"] == "satisfied"
                assert task["satisfied_by"] == row.get("satisfied_by", "rain")
                assert specimen_id not in due
            elif expected == "due":
                assert specimen_id in due, f"{specimen_id}: {note}"
                assert due[specimen_id]["satisfied_by"] is None
                assert specimen_id not in satisfied
            elif expected == "ok":
                # Never owed, so never settled. "ok" is not "satisfied", and
                # the difference is the whole reason the section exists.
                assert balance["status"] == "ok", f"{specimen_id}: {note}"
                assert balance["satisfied_by"] is None
                assert specimen_id not in satisfied, f"{specimen_id}: {note}"
            else:  # pragma: no cover - a fixture that says something new
                raise AssertionError(f"unknown expectation {expected!r}: {row}")


def test_the_storm_cancels_its_settled_waterings_in_the_calendar() -> None:
    with under_scenario("storm") as client:
        on = scenario_day("storm", -1)
        payload = client.get("/api/v1/tending/rounds", params={"on": on}).json()
        events = ics_events(client.get(subscribe(client)).text)

        settled = payload["satisfied"]
        assert settled, "the storm settled nothing, so it is not a storm"
        for task in settled:
            uid = f"task-{task['id']}@herbology"
            assert uid in events, "a settled watering was dropped, not cancelled"
            assert events[uid]["STATUS"] == "CANCELLED"


# ----------------------------------------------------------------- drought


def test_the_drought_fixture_expectations_hold_on_the_running_app() -> None:
    """Every plant the drought fixture names comes due, and stays due."""
    rows = expectations("drought")
    assert rows

    with under_scenario("drought") as client:
        on = scenario_day("drought", -1)
        payload = client.get("/api/v1/tending/rounds", params={"on": on}).json()
        due = tasks_by_specimen(payload["due"])

        for row in rows:
            specimen_id = row["specimen"]
            assert row["water_task_status"] == "due", row
            assert specimen_id in due, f"{specimen_id}: {row.get('note', '')}"
            assert due[specimen_id]["status"] == "due"
            assert due[specimen_id]["satisfied_by"] is None


def test_a_drought_never_reports_a_watering_the_sky_did() -> None:
    """``satisfied_by_rain_count: 0`` — the fixture's own last assertion."""
    with under_scenario("drought") as client:
        on = scenario_day("drought", -1)
        payload = client.get("/api/v1/tending/rounds", params={"on": on}).json()
        assert payload["satisfied"] == [], (
            "no rain fell in three weeks, so nothing may be reported as "
            f"settled by the weather: {payload['satisfied']}"
        )
        for task in payload["due"]:
            assert task["satisfied_by"] is None


def test_a_drought_does_not_grow_more_certain_as_it_goes_on() -> None:
    """Three weeks of arithmetic about unmeasured soil is still arithmetic."""
    with under_scenario("drought") as client:
        on = scenario_day("drought", -1)
        payload = client.get("/api/v1/tending/rounds", params={"on": on}).json()
        for task in payload["due"]:
            assert task["confidence"] != "high", (
                f"{task['specimen']['display_name']} claims a measured "
                "certainty for a modelled deficit (ADR 0010)"
            )
