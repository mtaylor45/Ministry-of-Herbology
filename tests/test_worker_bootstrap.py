"""Every Arq worker must connect to the Redis it was configured with.

Owner: Workstream A — this crosses four workstreams' directories.

This test exists because of a bug that shipped through every other gate. None
of the four ``WorkerSettings`` classes declared ``redis_settings``, so Arq fell
back to its own default of ``localhost:6379`` and all four workers exited with
``ConnectionError: Error 111`` the moment a deployment tried to run them. The
result was an installation that served the API, the web app and the database
correctly and did no background work at all: no weather ingest, no taxon
resolution, no Home Assistant polling, no plates.

``MOH_REDIS_URL`` was documented in ``.env.example``, set by the dev compose and
set by the swarm stack. Nothing read it.

Nothing caught it because the unit tests call the task functions directly and
never boot Arq, and because the *enqueue* side reads the URL correctly — jobs
arrived in the right Redis and nobody drained them. Workstream B found it by
deploying the stack and watching the workers fall over (ADR 0019: the guide is
tested by being followed).
"""

from __future__ import annotations

import importlib

import pytest

#: The four Arq entry points, one per worker, by the workstream that owns it.
WORKERS = [
    ("workers.weather.tasks", "E"),
    ("workers.botany.tasks", "D"),
    ("workers.hub.tasks", "F"),
    ("workers.plates.tasks", "K"),
]


@pytest.fixture
def redis_url(monkeypatch):
    """A URL no default could produce by accident."""
    url = "redis://redis.test.invalid:6399/7"
    monkeypatch.setenv("MOH_REDIS_URL", url)
    return url


@pytest.mark.parametrize("module_name,workstream", WORKERS)
def test_a_worker_connects_to_the_configured_redis(module_name, workstream, redis_url):
    settings = importlib.import_module(module_name).WorkerSettings
    resolved = settings.redis_settings

    assert resolved.host == "redis.test.invalid", (
        f"{workstream}'s worker ignores MOH_REDIS_URL and will connect to "
        f"{resolved.host}:{resolved.port}. Arq's default is localhost:6379, "
        "which is nothing in a deployment."
    )
    assert resolved.port == 6399
    assert resolved.database == 7


@pytest.mark.parametrize("module_name,workstream", WORKERS)
def test_importing_a_worker_does_not_require_arq(module_name, workstream, monkeypatch):
    """Importing a worker module must not pull Arq in.

    The API and the scenario suite import ``workers.weather.tasks`` for its
    engines, and Workstream E kept Arq off that path deliberately. The
    bootstrap resolves ``redis_settings`` lazily so it stays that way; this
    fails if someone moves the import to module scope.
    """
    import sys

    monkeypatch.delitem(sys.modules, module_name, raising=False)
    monkeypatch.delitem(sys.modules, "arq", raising=False)
    monkeypatch.delitem(sys.modules, "arq.connections", raising=False)

    real_import = __import__

    def refuse_arq(name, *args, **kwargs):
        if name == "arq" or name.startswith("arq."):
            raise ImportError("arq is not installed in this environment")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", refuse_arq)
    importlib.import_module(module_name)  # must not raise


def test_the_default_is_arqs_default_and_is_useless_in_a_deployment():
    """Kept explicit so the fallback is a decision rather than an accident."""
    from workers.runtime import DEFAULT_REDIS_URL
    from workers.runtime import redis_url as configured

    assert DEFAULT_REDIS_URL == "redis://localhost:6379/0"
    assert configured() == DEFAULT_REDIS_URL  # no MOH_REDIS_URL set here
