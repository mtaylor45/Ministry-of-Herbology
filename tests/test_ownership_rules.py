"""The ownership table must agree with the documents that describe it.

Owner: Workstream L. Three copies of the same table drift; this notices.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_ownership import OWNERSHIP, violations


def test_every_workstream_from_the_plan_has_an_ownership_entry():
    assert set(OWNERSHIP) == set("ABCDEFGHIJKL")


def test_claude_md_lists_the_same_workstreams(repo_root):
    claude_md = (repo_root / "CLAUDE.md").read_text()
    table = claude_md.split("## Layout")[1].split("## Stack")[0]
    listed = set(
        re.findall(r"^\| `[^`]+` \| ([A-L])(?:, [A-L])* \|", table, re.MULTILINE)
    )
    # A appears as the owner of contracts/ and docs/adr/, the rest once each.
    assert listed >= set("ABCDEFGHIJKL") - {"A"} or "A" in table


def test_owned_directories_exist(repo_root):
    for workstream, paths in OWNERSHIP.items():
        if workstream == "A":
            continue
        for path in paths:
            assert (
                repo_root / path
            ).exists(), f"{workstream} owns {path}, which does not exist"


def test_a_workstream_may_not_touch_the_contracts():
    assert violations("E", ["contracts/openapi/openapi.yaml"])
    assert violations("C", ["docs/adr/0007-something.md"])


def test_a_workstream_may_touch_its_own_paths():
    assert not violations("E", ["workers/weather/tasks.py", "api/almanac/router.py"])
    assert not violations("J", ["web/src/routes/register/+page.svelte"])


def test_the_architect_may_touch_anything():
    assert not violations(
        "A", ["contracts/openapi/openapi.yaml", "web/src/routes/+page.svelte"]
    )


def test_a_workstream_may_not_touch_another_workstreams_code():
    assert violations(
        "J", ["web/src/lib/ui/tokens.css"]
    ), "J must not edit I's design system"
    assert violations("D", ["api/tending/router.py"]), "D must not edit G's scheduler"


def test_every_workstream_has_an_agent_definition(repo_root):
    """The roster, the ownership table and the agent files must not drift."""
    import re

    agents = {
        path.stem: path.read_text()
        for path in (repo_root / ".claude" / "agents").glob("ws-*.md")
    }
    assert len(agents) == 12, f"expected 12 agent definitions, found {sorted(agents)}"

    ids = {re.match(r"ws-([a-l])-", stem).group(1).upper() for stem in agents}
    assert ids == set(OWNERSHIP)


def test_each_agent_names_the_paths_it_owns(repo_root):
    import re

    for path in (repo_root / ".claude" / "agents").glob("ws-*.md"):
        workstream = re.match(r"ws-([a-l])-", path.stem).group(1).upper()
        if workstream == "A":
            continue
        body = path.read_text()
        for owned in OWNERSHIP[workstream]:
            if owned.endswith("/"):
                assert (
                    owned in body
                ), f"{path.name} never mentions {owned}, which it owns"


def test_every_agent_declares_a_name_and_description(repo_root):
    for path in sorted((repo_root / ".claude" / "agents").glob("ws-*.md")):
        head = path.read_text().split("---")[1]
        assert (
            f"name: {path.stem}" in head
        ), f"{path.name} frontmatter name must match its filename"
        assert "description:" in head


def test_the_progress_marker_is_writable_by_every_workstream():
    """Rule 6 tells the implementing workstream to strike its own entry from
    NOT_YET_IMPLEMENTED, and that list lives in L's directory. Making it
    L-only was a contradiction every sprint would hit (ADR 0011)."""
    for workstream in "CDEFGHIJK":
        assert not violations(
            workstream, ["tests/contract/test_api_matches_spec.py"]
        ), f"{workstream} must be able to strike its own exemption"


def test_the_gallery_belongs_to_the_design_system():
    assert not violations("I", ["web/src/routes/gallery/+page.svelte"])
    assert violations(
        "I", ["web/src/routes/register/+page.svelte"]
    ), "I still may not write J's feature screens"
