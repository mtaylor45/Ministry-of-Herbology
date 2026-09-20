"""Fixtures are contract too — every mock and every scenario test reads them.

Owner: Workstream L.
"""

import json
from datetime import date

import pytest

SCENARIOS = ["drought", "storm", "frost"]


def _load(repo_root, relative):
    with (repo_root / "fixtures" / relative).open() as fh:
        return json.load(fh)


def test_every_specimen_points_at_a_known_species_and_location(repo_root):
    species = {s["id"] for s in _load(repo_root, "species/species.json")}
    locations = {
        location["id"] for location in _load(repo_root, "locations/locations.json")
    }
    for specimen in _load(repo_root, "specimens/specimens.json"):
        assert specimen["species_id"] in species, specimen
        assert specimen["location_id"] in locations, specimen


def test_specimen_outdoor_flag_agrees_with_its_location(repo_root):
    """`specimen.is_outdoor` is denormalised for fast filters; it must not drift."""
    locations = {
        location["id"]: location
        for location in _load(repo_root, "locations/locations.json")
    }
    for specimen in _load(repo_root, "specimens/specimens.json"):
        assert (
            specimen["is_outdoor"] == locations[specimen["location_id"]]["is_outdoor"]
        ), specimen


def test_every_care_value_is_cited_or_marked_unknown(repo_root):
    """ADR 0004, in the fixture data the mocks serve."""
    sources = {s["id"] for s in _load(repo_root, "species/sources.json")}
    for species in _load(repo_root, "species/species.json"):
        for value in species["care_values"]:
            if value["source_id"] is None:
                assert value["confidence"] == "unknown", (
                    species["accepted_name"],
                    value,
                )
            else:
                assert value["source_id"] in sources, value
                assert value["confidence"] in {"high", "medium", "low"}


def test_species_with_a_frost_threshold_cite_it(repo_root):
    """The frost engine acts on `min_temp_c`; an uncited threshold moves plants wrongly."""
    for species in _load(repo_root, "species/species.json"):
        if species.get("min_temp_c") is None:
            continue
        cited = [v for v in species["care_values"] if v["field"] == "min_temp_c"]
        assert (
            cited
        ), f"{species['accepted_name']} has min_temp_c with no care_value row"


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_is_well_formed(repo_root, name):
    scenario = _load(repo_root, f"scenarios/{name}.json")
    assert scenario["name"] == name
    assert scenario["days"], "a scenario with no days tests nothing"
    assert scenario["expect"][
        "assertions"
    ], "a scenario with no expectations tests nothing"
    days = [date.fromisoformat(d["date"]) for d in scenario["days"]]
    assert days == sorted(days), "scenario days are out of order"
    assert days[0] == date.fromisoformat(scenario["start"])
    for day in scenario["days"]:
        assert day["tmin_c"] <= day["tmax_c"], day
        assert day["precip_mm"] >= 0 and day["et0_mm"] >= 0, day


def test_drought_scenario_never_rains(repo_root):
    scenario = _load(repo_root, "scenarios/drought.json")
    assert all(d["precip_mm"] == 0 for d in scenario["days"])


def test_storm_scenario_has_one_soaking(repo_root):
    scenario = _load(repo_root, "scenarios/storm.json")
    wet = [d for d in scenario["days"] if d["precip_mm"] > 0]
    assert len(wet) == 1 and wet[0]["precip_mm"] >= 25


def test_frost_scenario_crosses_freezing_and_carries_an_advisory(repo_root):
    scenario = _load(repo_root, "scenarios/frost.json")
    assert min(d["tmin_c"] for d in scenario["days"]) < 0
    assert scenario[
        "advisories"
    ], "a frost scenario with no NWS advisory misses half the engine"


def test_scenario_assertions_reference_real_specimens(repo_root):
    specimens = {s["id"] for s in _load(repo_root, "specimens/specimens.json")}
    for name in SCENARIOS:
        for assertion in _load(repo_root, f"scenarios/{name}.json")["expect"][
            "assertions"
        ]:
            if "specimen" in assertion:
                assert assertion["specimen"] in specimens, (name, assertion)
