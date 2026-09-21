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


#: What each source kind actually publishes. POWO and GBIF are nomenclatural
#: authorities — names, synonymy, distribution — and publish no care value at
#: all, so citing them for light or cold tolerance is a category error even
#: when the species matches. Aggregators and encyclopaedias cover many fields.
PUBLISHES = {
    "powo": set(),
    "gbif": set(),
    "usda": {
        "min_temp_c",
        "max_temp_c",
        "soil_ph_min",
        "soil_ph_max",
        "usda_zone_min",
        "usda_zone_max",
        "light_label",
        "toxic_to_pets",
        "toxic_to_children",
        "toxicity_note",
    },
    "wikipedia": {
        "light_label",
        "summary",
        "native_range",
        "toxic_to_pets",
        "toxic_to_children",
        "toxicity_note",
        "humidity_min_pct",
    },
    "wikidata": {"native_range", "summary"},
    "perenual": {
        "water_k_c",
        "water_interval_days",
        "light_label",
        "soil_ph_min",
        "soil_ph_max",
        "humidity_min_pct",
        "fertilizer_note",
    },
    "user": None,  # a user override may correct any field
}


def test_a_citation_names_the_species_it_is_cited_for(repo_root):
    """ADR 0004: a citation that does not support its value is not a citation.

    The S0 fixtures reused one species' source rows across seven others — the
    mandrake's `toxic_to_children` cited a Monstera article, which is the exact
    failure this rule exists to prevent, sitting in the seed data every test
    reads. A source whose title names a species must name *that* species.
    """
    sources = {s["id"]: s for s in _load(repo_root, "species/sources.json")}
    wrong = []
    for species in _load(repo_root, "species/species.json"):
        for value in species["care_values"]:
            if not value["source_id"]:
                continue
            title = sources[value["source_id"]]["title"]
            if "— " not in title:
                continue  # an aggregator or database covering many species
            if species["accepted_name"] not in title:
                wrong.append(
                    f"{species['accepted_name']} {value['field']} cites {title!r}"
                )
    assert not wrong, "citations naming the wrong species:\n  " + "\n  ".join(wrong)


def test_a_source_is_only_cited_for_fields_it_publishes(repo_root):
    """A taxonomic authority cannot attest a watering coefficient."""
    sources = {s["id"]: s for s in _load(repo_root, "species/sources.json")}
    wrong = []
    for species in _load(repo_root, "species/species.json"):
        for value in species["care_values"]:
            if not value["source_id"]:
                continue
            kind = sources[value["source_id"]]["kind"]
            allowed = PUBLISHES.get(kind, set())
            if allowed is None:
                continue
            if value["field"] not in allowed:
                wrong.append(
                    f"{species['accepted_name']} {value['field']} cites a {kind} source, "
                    f"which publishes {sorted(allowed) or 'no care values'}"
                )
    assert not wrong, "citations a source cannot support:\n  " + "\n  ".join(wrong)


#: Sources whose permalinks are built from the name, so the URL can be checked
#: against it. POWO and GBIF address records by opaque identifier — an LSID or a
#: numeric key — which is a perfectly auditable citation that simply cannot
#: carry the name, so those are excluded rather than exempted by special case.
NAME_ADDRESSED = {"wikipedia"}


def test_a_species_specific_source_url_points_at_that_species(repo_root):
    """An auditable citation: following the URL must reach the right plant."""
    checked = 0
    for source in _load(repo_root, "species/sources.json"):
        assert source["url"], f"a citation with no URL cannot be audited: {source}"
        if "— " not in source["title"] or source["kind"] not in NAME_ADDRESSED:
            continue
        name = source["title"].split("— ", 1)[1]
        slug = name.replace(" × ", "_×_").replace(" ", "_").lower()
        assert slug in source["url"].lower().replace(
            "%c3%97", "×"
        ), f"{source['title']} points at {source['url']}"
        checked += 1
    assert (
        checked >= 7
    ), "the fixtures should carry a per-species article for each species"
