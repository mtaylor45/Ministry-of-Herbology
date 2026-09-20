"""Building the resolver: which connectors, pointed at what.

One place decides live-or-mock and which sources are switched on, so the job,
the API route and the tests all get the same worker.
"""

from __future__ import annotations

from functools import lru_cache

from .connectors.base import Connector
from .connectors.gbif import GbifConnector
from .connectors.http import HttpFetcher
from .connectors.powo import PowoConnector
from .resolve import TaxonResolver
from .settings import BotanySettings, get_settings

#: Sources that need a key or a paid tier. ADR 0007 keeps them off: the free
#: path has to be complete on its own, so these can only ever *add* to an answer,
#: never be the reason one is missing. Both are off unless a key is configured.
FLAGGED_SOURCES = ("perenual", "plantnet")


def enabled_flagged_sources(settings: BotanySettings | None = None) -> tuple[str, ...]:
    settings = settings or get_settings()
    return tuple(
        kind for kind in FLAGGED_SOURCES if getattr(settings, f"enable_{kind}", False)
    )


def build_connectors(settings: BotanySettings | None = None) -> list[Connector]:
    """The connectors to ask, in source-precedence order."""
    settings = settings or get_settings()
    if settings.mock_mode:
        from .mocks import build_mock_connectors

        return build_mock_connectors(settings)

    fetcher = HttpFetcher(settings)
    return [
        PowoConnector(fetcher, settings.powo_base_url),
        GbifConnector(fetcher, settings.gbif_base_url),
    ]


def build_resolver(settings: BotanySettings | None = None) -> TaxonResolver:
    return TaxonResolver(build_connectors(settings))


@lru_cache
def get_resolver() -> TaxonResolver:
    """The process-wide resolver, so one HTTP client and one cache are shared."""
    return build_resolver()


def reset_resolver() -> None:
    get_resolver.cache_clear()
