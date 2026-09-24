"""The Arq bootstrap every worker shares.

Owner: Workstream A — this is cross-cutting by construction. The four workers
live in four workstreams' directories (D, E, F, K) and every one of them needs
the same answer to the same question: which Redis?

Why this exists at all: until Workstream B deployed the stack and watched the
workers fall over, no ``WorkerSettings`` declared ``redis_settings``. Arq
therefore used its own default of ``localhost:6379``, every worker exited with
``ConnectionError: Error 111``, and a deployment did no background work — no
weather ingest, no taxon resolution, no Home Assistant polling, no plates.
``MOH_REDIS_URL`` was documented, set by the dev compose and set by the swarm
stack, and nothing read it.

Nothing caught it because the unit tests call the task functions directly and
never boot Arq, and because the *enqueue* side in ``api/inventory/enrichment.py``
reads the URL correctly — so jobs arrived in the right Redis and simply nobody
drained them. ``tests/test_worker_bootstrap.py`` is the guard now.

The metaclass is load-bearing rather than clever. Arq reads ``redis_settings``
as an attribute of the settings class, but importing a worker module must not
require Arq to be installed: the API and the scenario suite import
``workers/weather/tasks.py`` for its engines, and E deliberately kept Arq out of
that path. A property on the metaclass is read like a plain class attribute and
runs only when something actually asks — which is Arq, at worker startup.
"""

from __future__ import annotations

import os
from typing import Any

#: Arq's own default, and what the four workers were silently using.
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def redis_url() -> str:
    """The configured Redis, read at the moment it is needed.

    Read from the environment rather than from a worker's settings object
    because there are four of those, one of them does not exist, and they
    would all say the same thing.
    """
    return os.environ.get("MOH_REDIS_URL") or DEFAULT_REDIS_URL


class ArqBootstrap(type):
    """Gives a ``WorkerSettings`` class a lazily-resolved ``redis_settings``."""

    @property
    def redis_settings(cls) -> Any:
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(redis_url())
