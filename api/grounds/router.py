"""Map layers, calibration and specimen pins.

Owner: Workstream H. S0 mock: one floor plan and one survey, with pins spread
over them, so the map component and the Specimen cross-links can be built before
upload and calibration exist.
"""

from typing import Any

from fastapi import APIRouter

from app import fixtures

router = APIRouter(prefix="/grounds", tags=["grounds"])

FLOOR_PLAN = "01890070-0000-7000-8000-000000000001"
SURVEY = "01890070-0000-7000-8000-000000000002"


@router.get("/layers")
async def list_map_layers() -> list[dict[str, Any]]:
    site = fixtures.site()
    return [
        {
            "id": FLOOR_PLAN,
            "site_id": site["id"],
            "name": "Ground floor",
            "kind": "floor_plan",
            "image_url": "/static/mock/floor-plan.svg",
            "image_width_px": 1600,
            "image_height_px": 1200,
            "scale_mm_per_px": 12.5,
            "calibration": {"scale_mm_per_px": 12.5, "points": []},
            "ordinal": 0,
        },
        {
            "id": SURVEY,
            "site_id": site["id"],
            "name": "Property survey",
            "kind": "survey",
            "image_url": "/static/mock/survey.svg",
            "image_width_px": 2000,
            "image_height_px": 1500,
            "scale_mm_per_px": None,
            "calibration": {
                "scale_mm_per_px": None,
                "points": [
                    {
                        "px": [120, 1380],
                        "world": [
                            site["latitude"] - 0.0006,
                            site["longitude"] - 0.0008,
                        ],
                    },
                    {
                        "px": [1880, 120],
                        "world": [
                            site["latitude"] + 0.0006,
                            site["longitude"] + 0.0008,
                        ],
                    },
                ],
            },
            "ordinal": 1,
        },
    ]


@router.get("/pins")
async def list_pins(layer_id: str | None = None) -> list[dict[str, Any]]:
    pins = []
    indoor_slot = outdoor_slot = 0
    for specimen in fixtures.specimens():
        if specimen.get("is_outdoor"):
            layer, col, row = SURVEY, outdoor_slot % 3, outdoor_slot // 3
            px = {"x": 400 + col * 520, "y": 380 + row * 420}
            outdoor_slot += 1
        else:
            layer, col, row = FLOOR_PLAN, indoor_slot % 3, indoor_slot // 3
            px = {"x": 320 + col * 440, "y": 300 + row * 360}
            indoor_slot += 1
        if layer_id and layer != layer_id:
            continue
        pins.append(
            {
                "specimen_id": specimen["id"],
                "layer_id": layer,
                "px": px,
                "specimen": {
                    "id": specimen["id"],
                    "display_name": fixtures.display_name(specimen),
                    "is_outdoor": specimen.get("is_outdoor", False),
                    "thumb_url": None,
                },
            }
        )
    return pins
