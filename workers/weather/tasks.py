"""Weather & environment worker — Workstream E.

S0 skeleton: the Arq job graph and the pure functions the engines are built
from, with the scenario fixtures as their acceptance tests. Ingest against
Open-Meteo and NWS lands in S3; the engines in S5 and S6.
"""

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

#: Fraction of a container's water-holding capacity that may be lost before a
#: watering is due. Containers reach it far sooner than open ground.
THRESHOLD_FRACTION = 0.6

#: Frost margin. The plan specifies 3 °F of headroom over the species minimum.
FROST_MARGIN_C = 3.0 * 5.0 / 9.0


@dataclass(frozen=True, slots=True)
class BalanceInputs:
    """One day of inputs to the soil water balance."""

    et0_mm: float
    precip_mm: float
    irrigation_mm: float = 0.0
    #: 0 for a covered spot the rain never reaches, 1 for open sky.
    cover_factor: float = 1.0


def step_deficit(
    previous_mm: float, inputs: BalanceInputs, k_c: float, capacity_mm: float
) -> float:
    """Advance the soil water deficit by one day.

    ``D(t) = clamp(D(t-1) + K_c·ET₀ − f_cover·P − I, 0, D_max)`` — the plan's
    water-balance equation, and the only place it is written down in code.
    """
    deficit = (
        previous_mm
        + k_c * inputs.et0_mm
        - inputs.cover_factor * inputs.precip_mm
        - inputs.irrigation_mm
    )
    return max(0.0, min(capacity_mm, deficit))


def capacity_mm(in_container: bool, container_litres: float | None) -> float:
    """Plant-available water the root zone holds, in millimetres of deficit.

    A container runs dry quickly; open ground draws on a much deeper profile.
    The container figure scales with pot volume and saturates, because a bigger
    pot buys less than proportionally more buffer once roots fill it.
    """
    if not in_container:
        return 60.0
    litres = container_litres or 10.0
    return min(40.0, 8.0 + 0.55 * litres)


def is_watering_due(deficit_mm: float, capacity: float) -> bool:
    return deficit_mm >= capacity * THRESHOLD_FRACTION


def frost_threshold_c(species_min_temp_c: float) -> float:
    """The temperature at which we act, not the one at which the plant dies."""
    return species_min_temp_c + FROST_MARGIN_C


def needs_frost_action(
    forecast_low_c: float, species_min_temp_c: float, *, is_outdoor: bool
) -> bool:
    if not is_outdoor:
        return False
    return forecast_low_c <= frost_threshold_c(species_min_temp_c)


def frost_action(*, in_container: bool) -> str:
    """Containers come inside; anything in the ground gets covered instead."""
    return "bring_indoors" if in_container else "cover"


async def ingest_forecast(ctx: dict, site_id: str) -> None:  # pragma: no cover - S3
    raise NotImplementedError("S3 (E): Open-Meteo forecast and history ingest")


async def evaluate_water_balance(ctx: dict, day: date) -> None:  # pragma: no cover - S5
    raise NotImplementedError("S5 (E): daily water-balance evaluation")


async def evaluate_frost_guard(ctx: dict) -> None:  # pragma: no cover - S6
    raise NotImplementedError("S6 (E): 72h frost lookahead and NWS advisories")


class WorkerSettings:
    """Arq entrypoint. Schedules are set in S3."""

    functions: ClassVar[list] = [
        ingest_forecast,
        evaluate_water_balance,
        evaluate_frost_guard,
    ]
