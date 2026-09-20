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
WORKERS_DIR = REPO_ROOT / "workers"

# Imported as ``botany.*`` rather than ``workers.botany.*``. ``workers/`` is not
# a package — it has no ``__init__.py``, and it belongs to no single workstream —
# so the two spellings are two names for one file, which mypy rightly refuses to
# check twice. This is the name mypy maps these files to; production reaches the
# same modules as ``workers.botany.*`` with the repository root on the path
# (``PYTHONPATH=/srv/api:/srv`` in ``infra/docker/worker.Dockerfile``).
if str(WORKERS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKERS_DIR))

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
    from botany.factory import build_resolver

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
