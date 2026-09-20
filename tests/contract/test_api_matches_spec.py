"""The running API must implement the frozen contract.

Owner: Workstream L. Every path in ``openapi.yaml`` that a workstream has
claimed must exist on the app with the declared methods, and must not 404 on
the contract's own example arguments. Unimplemented paths are listed explicitly
below, so adding one is a deliberate act with a sprint attached.
"""

#: Paths the contract declares but no workstream has built yet. Each entry names
#: the sprint that removes it. Shrinking this list is how S0 becomes S10.
NOT_YET_IMPLEMENTED = {
    ("post", "/specimens"): "S1 (C)",
    ("patch", "/specimens/{specimen_id}"): "S1 (C)",
    ("delete", "/specimens/{specimen_id}"): "S1 (C)",
    ("post", "/specimens/{specimen_id}/photos"): "S2 (C)",
    ("post", "/specimens/{specimen_id}/log"): "S2 (C)",
    ("post", "/locations"): "S1 (C)",
    ("patch", "/locations/{location_id}"): "S1 (C)",
    ("put", "/species/{species_id}/care-values"): "S2 (D)",
    ("post", "/taxon/resolve"): "S1 (D)",
    ("post", "/tending/tasks/{task_id}/complete"): "S4 (G)",
    ("post", "/tending/tasks/complete-batch"): "S4 (G)",
    ("post", "/tending/care-rules"): "S4 (G)",
    ("post", "/tending/feeds"): "S4 (G)",
    ("post", "/tending/feeds/{feed_id}/revoke"): "S4 (G)",
    ("post", "/grounds/layers"): "S7 (H)",
    ("put", "/grounds/layers/{layer_id}/calibration"): "S7 (H)",
    ("put", "/grounds/pins"): "S7 (H)",
    ("get", "/journal/plates"): "S8 (K)",
    ("get", "/journal/{specimen_id}/notes"): "S8 (K)",
    ("post", "/journal/{specimen_id}/notes"): "S8 (K)",
    ("get", "/hub/sensors"): "S3 (F)",
    ("post", "/hub/sensors"): "S3 (F)",
    ("get", "/hub/integrations"): "S3 (F)",
    ("get", "/hub/lunette"): "S9 (F)",
}


def _implemented_routes(client) -> set[tuple[str, str]]:
    """What the app actually serves, taken from the OpenAPI document it generates.

    Reading ``app.routes`` misses routes nested inside included routers, so we
    compare document to document instead.
    """
    served = client.app.openapi()["paths"]
    return {
        (method, path.removeprefix("/api/v1"))
        for path, item in served.items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }


def _contract_routes(spec) -> set[tuple[str, str]]:
    return {
        (method, path)
        for path, item in spec["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }


def test_no_route_exists_outside_the_contract(client, spec):
    extra = _implemented_routes(client) - _contract_routes(spec)
    assert not extra, (
        f"routes served but not in the contract: {sorted(extra)}. "
        "Add them to contracts/openapi/openapi.yaml via an ADR first (rule 1)."
    )


def test_implemented_contract_routes_are_served(client, spec):
    expected = _contract_routes(spec) - set(NOT_YET_IMPLEMENTED)
    missing = expected - _implemented_routes(client)
    assert not missing, (
        f"contract declares these but the app does not serve them: {sorted(missing)}. "
        "Either implement them or list them in NOT_YET_IMPLEMENTED with a sprint."
    )


def test_not_yet_implemented_entries_are_real_contract_paths(spec):
    stale = set(NOT_YET_IMPLEMENTED) - _contract_routes(spec)
    assert (
        not stale
    ), f"NOT_YET_IMPLEMENTED names paths the contract dropped: {sorted(stale)}"


def test_not_yet_implemented_entries_are_actually_missing(client):
    """Stop the exemption list outliving the work it excuses."""
    served = _implemented_routes(client)
    landed = {r for r in NOT_YET_IMPLEMENTED if r in served}
    assert (
        not landed
    ), f"these are implemented now — remove them from NOT_YET_IMPLEMENTED: {sorted(landed)}"


def test_healthz_reports_the_frozen_contract_version(client, repo_root):
    body = client.get("/api/v1/healthz").json()
    assert body["status"] == "ok"
    assert (
        body["contract_version"]
        == (repo_root / "contracts" / "VERSION").read_text().strip()
    )
