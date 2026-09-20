"""The shape every source connector has.

S1 ships two — POWO and GBIF. S2's Wikipedia, Wikidata, USDA and Perenual
connectors slot into the same three parts, and so should anything after them:

1. a **fetcher**, which is the only thing that touches the network, so every
   parser is testable against a recorded payload;
2. **pure parse functions** over a payload, returning ``TaxonRecord``s;
3. a **connector** binding the two, returning the records *and* the
   ``SourceRecord`` that cites them (ADR 0004 — no value travels uncited).

A connector never decides what to publish. Ranking and confidence happen once,
in ``resolve.py``, over everything every connector returned.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from ..names import ParsedName
from ..sources import SourceRecord

#: How a source matched what the user typed. Ordered best to worst; the ranking
#: step turns these into a score, and a weaker kind lowers confidence.
MATCH_KINDS = ("exact", "vernacular", "fuzzy", "higher_rank", "partial")

MATCH_WEIGHT: dict[str, float] = {
    "exact": 1.0,
    "vernacular": 0.92,
    "fuzzy": 0.78,
    "higher_rank": 0.7,
    "partial": 0.6,
}


@dataclass(frozen=True, slots=True)
class FetchResult:
    """One payload, and the request that produced it."""

    url: str
    payload: Any
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    from_cache: bool = False
    is_mock: bool = False


@runtime_checkable
class Fetcher(Protocol):
    """The only thing in the worker that is allowed to touch the network."""

    async def get_json(
        self, kind: str, url: str, params: Mapping[str, Any] | None = None
    ) -> FetchResult: ...


@dataclass(frozen=True, slots=True)
class TaxonRecord:
    """One source's answer about one taxon.

    Every field here was read out of a payload. Nothing on this record is
    computed, inferred or filled in with a likely value — that is the whole
    point of ADR 0004, and it is why ranking lives somewhere else.
    """

    accepted_name: str
    source_kind: str
    rank: str = "species"
    family: str | None = None
    genus: str | None = None
    common_name: str | None = None
    gbif_key: str | None = None
    powo_id: str | None = None
    authorship: str | None = None
    #: The name the source actually matched, which may be a synonym of the
    #: accepted one — that is how "Sansevieria" arrives at "Dracaena".
    matched_name: str | None = None
    #: ``accepted`` | ``synonym`` | ``unknown``, as the source reported it.
    status: str = "unknown"
    match_kind: str = "exact"
    #: The source's own confidence in the match, 0..1, where it offers one.
    source_score: float = 1.0

    @property
    def is_synonym(self) -> bool:
        return self.status == "synonym"


@dataclass(frozen=True, slots=True)
class ConnectorResult:
    """What one connector came back with, including the citation for it."""

    kind: str
    records: tuple[TaxonRecord, ...] = ()
    #: One per call made. Kept even when a call returned nothing, so an empty
    #: answer is as auditable as a full one.
    sources: tuple[SourceRecord, ...] = ()
    #: Set when the source could not be reached. A source that is down must not
    #: look like a source that said "no such plant".
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class Connector(Protocol):
    """A source that can be asked to resolve a name."""

    kind: str

    async def resolve(self, parsed: ParsedName) -> ConnectorResult: ...


#: Connector factories by source kind, so S2 adds a module and a registration
#: rather than another branch in the resolver.
_REGISTRY: dict[str, Callable[..., Connector]] = {}


def register(kind: str, factory: Callable[..., Connector]) -> None:
    _REGISTRY[kind] = factory


def registered() -> Mapping[str, Callable[..., Connector]]:
    return dict(_REGISTRY)


def build(kind: str, *args: Any, **kwargs: Any) -> Connector:
    if kind not in _REGISTRY:
        raise KeyError(f"no connector registered for {kind!r}; registered: {sorted(_REGISTRY)}")
    return _REGISTRY[kind](*args, **kwargs)


def empty_result(kind: str, error: str | None = None) -> ConnectorResult:
    return ConnectorResult(kind=kind, records=(), sources=(), error=error)
