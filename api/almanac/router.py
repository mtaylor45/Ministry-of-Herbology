"""Forecast, conditions history, water balance and frost.

Owner: Workstream E. S0 mock, driven by ``fixtures/weather/`` and the scenario
files, so J can build the Almanac before the ingest workers exist.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import fixtures

router = APIRouter(prefix="/almanac", tags=["almanac"])

WINDOW_DAYS = {"1d": 1, "7d": 7, "30d": 30}


def _iso(d: str, hour: int = 12) -> str:
    return f"{d}T{hour:02d}:00:00Z"


@router.get("/forecast")
async def get_forecast(
    site_id: str, horizon: str = Query("daily", pattern="^(hourly|daily)$")
) -> list[dict[str, Any]]:
    days = fixtures.baseline_weather()["days"]
    if horizon == "daily":
        return [
            {
                "time": _iso(d["date"], 0),
                "temp_min_c": d["tmin_c"],
                "temp_max_c": d["tmax_c"],
                "precip_mm": d["precip_mm"],
                "precip_prob_pct": 80.0 if d["precip_mm"] else 10.0,
                "et0_mm": d["et0_mm"],
                "condition": d["condition"],
            }
            for d in days[:10]
        ]
    first = days[0]
    return [
        {
            "time": _iso(first["date"], h),
            "temperature_c": round(
                first["tmin_c"]
                + (first["tmax_c"] - first["tmin_c"])
                * max(0.0, (12 - abs(14 - h)) / 12),
                1,
            ),
            "precip_mm": round(first["precip_mm"] / 24, 2),
            "precip_prob_pct": 80.0 if first["precip_mm"] else 10.0,
            "condition": first["condition"],
        }
        for h in range(24)
    ]


@router.get("/history")
async def get_history(
    window: str = Query(..., pattern="^(1d|7d|30d)$"),
    site_id: str | None = None,
    location_id: str | None = None,
    specimen_id: str | None = None,
    metric: str = "temperature_c",
) -> dict[str, Any]:
    days = fixtures.baseline_weather()["days"][-WINDOW_DAYS[window] :]
    times, values, lows, highs = [], [], [], []
    for d in days:
        stamp = int(datetime.fromisoformat(d["date"]).replace(tzinfo=UTC).timestamp())
        times.append(stamp)
        if metric == "precip_mm":
            values.append(d["precip_mm"])
            lows.append(None)
            highs.append(None)
        elif metric == "et0_mm":
            values.append(d["et0_mm"])
            lows.append(None)
            highs.append(None)
        else:
            values.append(round((d["tmin_c"] + d["tmax_c"]) / 2, 1))
            lows.append(d["tmin_c"])
            highs.append(d["tmax_c"])
    units = {
        "temperature_c": "°C",
        "humidity_pct": "%",
        "precip_mm": "mm",
        "et0_mm": "mm",
    }
    return {
        "metric": metric,
        "unit": units.get(metric, ""),
        "times": times,
        "values": values,
        "min": lows,
        "max": highs,
        "label": f"{metric} · last {window}",
    }


@router.get("/water-balance/{specimen_id}")
async def get_water_balance(specimen_id: str) -> dict[str, Any]:
    specimen = fixtures.by_id(fixtures.specimens(), specimen_id)
    if not specimen:
        raise HTTPException(status_code=404, detail="No such specimen")
    species = fixtures.by_id(fixtures.species(), specimen.get("species_id") or "")
    k_c = float((species or {}).get("water_k_c") or 0.6)
    capacity = 24.0 if specimen.get("in_container") else 60.0
    threshold = capacity * 0.6

    location = fixtures.by_id(fixtures.locations(), specimen.get("location_id") or "")
    cover = 0.0 if (location or {}).get("is_covered") else 1.0

    deficit = 0.0
    days: list[dict[str, Any]] = []
    for d in fixtures.baseline_weather()["days"][-14:]:
        et0 = d["et0_mm"] * k_c
        precip = d["precip_mm"] * cover
        deficit = max(0.0, min(capacity, deficit + et0 - precip))
        days.append(
            {
                "day": d["date"],
                "deficit_mm": round(deficit, 2),
                "et0_mm": round(et0, 2),
                "precip_mm": round(precip, 2),
                "irrigation_mm": 0.0,
            }
        )

    return {
        "specimen_id": specimen_id,
        "deficit_mm": round(deficit, 2),
        "capacity_mm": capacity,
        "threshold_mm": round(threshold, 2),
        "k_c": k_c,
        "is_due": deficit >= threshold,
        "sensor_override_pct": None,
        "days": days,
    }


@router.get("/frost")
async def list_frost_alerts() -> list[dict[str, Any]]:
    """Mock: read the frost scenario and report what it expects to happen."""
    scenario = fixtures.scenario("frost")
    lows = {day["date"]: day["tmin_c"] for day in scenario["days"]}
    out = []
    for assertion in scenario["expect"]["assertions"]:
        if not assertion.get("alert"):
            continue
        specimen = fixtures.by_id(fixtures.specimens(), assertion["specimen"])
        if not specimen:
            continue
        species = fixtures.by_id(fixtures.species(), specimen.get("species_id") or "")
        out.append(
            {
                "id": f"frost-{assertion['specimen'][-4:]}",
                "specimen": {
                    "id": specimen["id"],
                    "display_name": fixtures.display_name(specimen),
                    "is_outdoor": specimen.get("is_outdoor", False),
                    "thumb_url": None,
                },
                "night_of": assertion["night_of"],
                "forecast_low_c": lows[assertion["night_of"]],
                "threshold_c": float((species or {}).get("min_temp_c") or 0.0) + 1.7,
                "action": assertion["action"],
                "advisory": (
                    scenario["advisories"][0]["headline"]
                    if scenario["advisories"]
                    else None
                ),
                "task_id": None,
                "state": "open",
            }
        )
    return out
