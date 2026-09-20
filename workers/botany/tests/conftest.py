"""Shared setup for the botany worker's tests. Owner: Workstream D.

Every test here runs offline. Nothing in this directory may open a socket: the
connectors are exercised against the recordings in ``mocks/recorded/``, which is
what makes a misspelling or a synonym case reproducible a year from now.

Run them with ``.venv/bin/python -m pytest workers/botany -q``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# ``workers.botany.*`` is the one name these modules have: ``workers/__init__.py``
# makes it a package (ADR 0011), and it is how the Arq worker and the API reach
# them (``PYTHONPATH=/srv/api:/srv`` in the images). One file, one module name —
# which is also what lets ``mypy api/app workers`` complete a run.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

T = TypeVar("T")


def _run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@pytest.fixture
def run():
    """Drive a coroutine from a synchronous test.

    Deliberately not ``pytest-asyncio``: the repository has no root pytest
    config, so ``asyncio_mode`` is whatever the caller's rootdir happens to say,
    and a test suite should not depend on where it was invoked from.
    """
    return _run


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def recorded_dir() -> Path:
    return REPO_ROOT / "workers" / "botany" / "mocks" / "recorded"


@pytest.fixture(scope="session")
def payload(recorded_dir: Path):
    def _load(relative: str) -> Any:
        return json.loads((recorded_dir / relative).read_text())

    return _load


@pytest.fixture(scope="session")
def spec() -> dict[str, Any]:
    """The frozen contract. Read-only here — Workstream A owns it."""
    import yaml  # type: ignore[import-untyped]  # types-PyYAML is not in api[dev]

    with (REPO_ROOT / "contracts" / "openapi" / "openapi.yaml").open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture
def resolver():
    from workers.botany.factory import build_resolver

    return build_resolver()


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if a test ever reaches for the network."""
    import httpx

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "a botany test tried to open a connection; tests replay "
            "mocks/recorded/ instead (rule 3)"
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
