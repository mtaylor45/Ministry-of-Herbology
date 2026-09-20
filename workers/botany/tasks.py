"""Botanical knowledge worker — Workstream D.

S0 skeleton. Taxon resolution lands in S1; the source connectors and cited care
synthesis in S2. ADR 0004 governs everything here: this worker may rank and
select among sourced values and may write prose, but it may never originate a
number.
"""

from dataclasses import dataclass
from typing import ClassVar

#: Preference order when two sources disagree about the same field. Taxonomic
#: authorities outrank aggregators; an aggregator outranks an encyclopaedia.
SOURCE_RANK = {
    "user": 0,
    "powo": 1,
    "gbif": 2,
    "usda": 3,
    "perenual": 4,
    "wikidata": 5,
    "wikipedia": 6,
    "other": 9,
}

CONFIDENCE_BY_RANK = {
    0: "high",
    1: "high",
    2: "high",
    3: "high",
    4: "medium",
    5: "medium",
}


@dataclass(frozen=True, slots=True)
class SourcedValue:
    field: str
    value: object
    source_kind: str
    unit: str | None = None


def choose(values: list[SourcedValue]) -> tuple[SourcedValue | None, str]:
    """Pick the value to publish for a field, and say how much to trust it.

    Returns ``(None, "unknown")`` when nothing is sourced, which is a legitimate
    answer the UI must render — not a gap to fill with a plausible guess.
    """
    if not values:
        return None, "unknown"
    best = min(values, key=lambda v: SOURCE_RANK.get(v.source_kind, 9))
    rank = SOURCE_RANK.get(best.source_kind, 9)
    confidence = CONFIDENCE_BY_RANK.get(rank, "low")
    # Disagreement between two otherwise trusted sources is itself information.
    others = [v for v in values if v is not best]
    if others and any(
        v.value != best.value and SOURCE_RANK.get(v.source_kind, 9) <= 3 for v in others
    ):
        confidence = "medium" if confidence == "high" else "low"
    return best, confidence


async def resolve_taxon(ctx: dict, name: str) -> None:  # pragma: no cover - S1
    raise NotImplementedError("S1 (D): POWO/GBIF taxon resolution")


async def enrich_species(ctx: dict, species_id: str) -> None:  # pragma: no cover - S2
    raise NotImplementedError("S2 (D): Wikipedia, Wikidata, USDA, Perenual connectors")


class WorkerSettings:
    functions: ClassVar[list] = [resolve_taxon, enrich_species]
