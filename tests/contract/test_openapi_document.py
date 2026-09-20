"""The frozen contract must itself be a valid OpenAPI document.

Owner: Workstream L. Rule 1 (contract-first): a malformed spec breaks every
workstream at once, so this runs first and cheaply.
"""

from openapi_spec_validator import validate

WORKSTREAMS = set("ABCDEFGHIJKL")


def test_spec_is_valid_openapi(spec):
    validate(spec)


def test_every_operation_declares_an_owning_workstream(spec):
    missing = [
        f"{method.upper()} {path}"
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
        and op.get("x-workstream") not in WORKSTREAMS
    ]
    assert not missing, f"operations with no owning workstream: {missing}"


def test_every_operation_has_a_unique_operation_id(spec):
    ids = [
        op["operationId"]
        for item in spec["paths"].values()
        for method, op in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(ids) == len(set(ids)), "duplicate operationId"


def test_contract_version_matches_spec_version(spec, repo_root):
    frozen = (repo_root / "contracts" / "VERSION").read_text().strip()
    assert spec["info"]["version"] == frozen
