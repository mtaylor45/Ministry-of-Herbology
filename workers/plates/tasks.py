"""Naturalist's Journal plate pipeline — Workstream K.

S0 skeleton; the pipeline lands in S8. Public-domain sources are tried first and
a generated plate is the fallback, in one consistent house style. A generated
plate is always labelled as such (ADR 0004) and never carries a botanical
attribution it did not earn.
"""

from typing import ClassVar

#: Tried in order. The first that yields a usable, clearly licensed image wins.
PUBLIC_DOMAIN_SOURCES = [
    "biodiversity_heritage_library",
    "wikimedia_commons",
    "plantillustrations_org",
]

#: One house style for every generated plate, so the book reads as one volume.
#: Deliberately free of franchise references (ADR 0005).
HOUSE_STYLE = (
    "nineteenth-century botanical plate, hand-coloured lithograph, single specimen "
    "centred on aged cream paper, fine ink linework, muted natural pigments, "
    "no text, no border, no signature"
)

ACCEPTABLE_LICENCES = {"public domain", "cc0", "cc by", "cc by-sa"}


def is_usable_licence(licence: str | None) -> bool:
    return bool(licence) and licence.strip().lower() in ACCEPTABLE_LICENCES


async def source_plate(ctx: dict, species_id: str) -> None:  # pragma: no cover - S8
    raise NotImplementedError("S8 (K): public-domain plate sourcing")


async def generate_plate(ctx: dict, species_id: str) -> None:  # pragma: no cover - S8
    raise NotImplementedError("S8 (K): generated plate fallback")


class WorkerSettings:
    functions: ClassVar[list] = [source_plate, generate_plate]
