"""``POST /taxon/resolve`` on the wire, checked against the frozen contract."""

import pytest
from botany.router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

CONTRACT_PATH = "/taxon/resolve"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def candidate_schema(spec):
    return spec["components"]["schemas"]["TaxonCandidate"]


def test_a_typed_name_comes_back_as_ranked_candidates(client):
    response = client.post("/api/v1/taxon/resolve", json={"name": "Monstera deliciosa"})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["accepted_name"] == "Monstera deliciosa"
    assert body[0]["confidence"] == "high"
    assert body[0]["source"]["kind"] == "powo"


def test_every_candidate_validates_against_the_contract_schema(
    client, candidate_schema, spec
):
    jsonschema = pytest.importorskip("jsonschema")
    resolver = {"components": spec["components"]}
    for name in (
        "Monstera deliciosa",
        "snake plant",
        "mandrake",
        "Sansevieria trifasciata",
    ):
        for candidate in client.post(
            "/api/v1/taxon/resolve", json={"name": name}
        ).json():
            jsonschema.validate(
                candidate, {**candidate_schema, "components": resolver["components"]}
            )


def test_the_required_fields_are_always_present(client, candidate_schema):
    assert set(candidate_schema["required"]) == {"accepted_name", "confidence"}
    for candidate in client.post(
        "/api/v1/taxon/resolve", json={"name": "mandrake"}
    ).json():
        assert candidate["accepted_name"]
        assert candidate["confidence"] in {"high", "medium", "low", "unknown"}


def test_the_only_field_outside_the_contract_is_the_cultivar(client, candidate_schema):
    """Flagged for Workstream A: ``TaxonCandidate`` has nowhere to put a cultivar.

    POWO and GBIF index species; ``'Hidcote'`` is split off the typed name and has
    to reach the caller somehow, because ``specimen.cultivar`` is where it lands.
    The schema does not forbid extra properties, so this is additive.
    """
    body = client.post(
        "/api/v1/taxon/resolve", json={"name": "Lavandula angustifolia 'Hidcote'"}
    ).json()
    extra = set(body[0]) - set(candidate_schema["properties"])
    assert extra == {"cultivar"}
    assert body[0]["cultivar"] == "Hidcote"


def test_a_name_nobody_knows_is_an_empty_list_not_an_error(client):
    response = client.post("/api/v1/taxon/resolve", json={"name": "zzqqx frobnicata"})
    assert response.status_code == 200
    assert response.json() == []


def test_an_empty_request_is_rejected(client):
    assert client.post("/api/v1/taxon/resolve", json={}).status_code == 422
    assert client.post("/api/v1/taxon/resolve", json={"name": "   "}).status_code == 422


def test_a_photo_alone_says_plantnet_is_off_rather_than_guessing(client):
    response = client.post("/api/v1/taxon/resolve", json={"image_key": "uploads/x.jpg"})
    assert response.status_code == 501
    assert "Pl@ntNet" in response.json()["detail"]


def test_a_photo_beside_a_name_still_resolves_the_name(client):
    response = client.post(
        "/api/v1/taxon/resolve",
        json={"name": "Monstera deliciosa", "image_key": "x.jpg"},
    )
    assert response.status_code == 200
    assert response.json()[0]["accepted_name"] == "Monstera deliciosa"


def test_every_source_being_down_is_a_503_not_an_empty_list(client, monkeypatch):
    from botany import factory
    from botany.names import parse_name
    from botany.resolve import Resolution, TaxonResolver

    class DownResolver(TaxonResolver):
        async def resolve(self, name):
            return Resolution(
                query=name,
                parsed=parse_name(name),
                errors={"powo": "down", "gbif": "down"},
            )

    monkeypatch.setattr(factory, "get_resolver", lambda: DownResolver([]))
    monkeypatch.setattr("botany.router.get_resolver", lambda: DownResolver([]))
    response = client.post("/api/v1/taxon/resolve", json={"name": "Monstera deliciosa"})
    assert response.status_code == 503


def test_the_route_is_exactly_the_one_the_contract_declares(client, spec):
    """Mounting this must not add a path outside the frozen contract."""
    served = {
        (method, path.removeprefix("/api/v1"))
        for path, item in client.app.openapi()["paths"].items()
        for method in item
    }
    assert served == {("post", CONTRACT_PATH)}
    assert CONTRACT_PATH in spec["paths"]
    assert spec["paths"][CONTRACT_PATH]["post"]["x-workstream"] == "D"


def test_the_contract_still_lists_this_route_as_unimplemented(repo_root):
    """Landing it needs three one-line changes in three other workstreams' files.

    ``api/app/main.py`` (A) mounts the router, ``infra/docker/api.Dockerfile`` (B)
    ships ``workers/`` into the API image, and the exemption below (L) goes. Rule
    2 says D may not make any of those edits, so this test states the handoff
    rather than pretending it happened.
    """
    text = (repo_root / "tests" / "contract" / "test_api_matches_spec.py").read_text()
    assert '("post", "/taxon/resolve"): "S1 (D)"' in text
