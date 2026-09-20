"""Care rules, tasks, Morning Rounds and calendar feeds.

Owner: Workstream G. S0 mock. The themed/plain title pairing (ADR 0005) and the
stable ICS UID scheme are contract, not mock detail — keep both when the real
implementation lands.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Response

from app import fixtures
from app.settings import get_settings

router = APIRouter(tags=["tending"])

MEMBER_ID = "01890050-0000-7000-8000-000000000001"

#: Themed title, then the plain equivalent. Rule 7: never one without the other.
TITLES = {
    "water": ("Tend {name}", "Water {name}"),
    "fertilize": ("Feed {name}", "Fertilize {name}"),
    "mist": ("Mist {name}", "Mist {name}"),
    "inspect": ("Inspect {name}", "Check {name} for pests"),
    "bring_indoors": ("Shelter {name} from the frost", "Bring {name} indoors"),
    "return_outdoors": (
        "Return {name} to the grounds",
        "Put {name} back outside",
    ),
    "cover": ("Shroud {name}", "Cover {name} before frost"),
    "prune": ("Prune {name}", "Prune {name}"),
    "repot": ("Rehouse {name}", "Repot {name}"),
    "rotate": ("Turn {name}", "Rotate {name}"),
}


def subject(specimen: dict[str, Any]) -> str:
    """A nickname is already a name and takes no article; a species name does.

    "Tend Sour Bertram" and "Tend the snake plant", never "Tend the Sour Bertram".
    """
    name = fixtures.display_name(specimen)
    return name if specimen.get("nickname") else f"the {name.lower()}"


def ics_uid(specimen_id: str, task_type: str, due: date) -> str:
    """Stable per-task identity, so a reschedule updates the calendar in place."""
    return f"{task_type}-{specimen_id}-{due.isoformat()}@herbology"


def _task(
    specimen: dict[str, Any],
    task_type: str,
    due: datetime,
    status: str = "due",
    satisfied_by: str | None = None,
    amount_ml: int | None = None,
) -> dict[str, Any]:
    name = subject(specimen)
    themed, plain = TITLES.get(task_type, ("Tend {name}", "Tend {name}"))
    plain_title = plain.format(name=name)
    if amount_ml:
        plain_title = f"{plain_title} — {amount_ml} ml"
    return {
        "id": ics_uid(specimen["id"], task_type, due.date()),
        "specimen": {
            "id": specimen["id"],
            "display_name": fixtures.display_name(specimen),
            "is_outdoor": specimen.get("is_outdoor", False),
            "thumb_url": None,
        },
        "task_type": task_type,
        "due_at": due.isoformat().replace("+00:00", "Z"),
        "all_day": task_type not in ("bring_indoors", "cover"),
        "status": status,
        "satisfied_by": satisfied_by,
        "amount_ml": amount_ml,
        "priority": "urgent" if task_type in ("bring_indoors", "cover") else "normal",
        "title": themed.format(name=name),
        "plain_title": plain_title,
        "detail": None,
        "completed_at": None,
        "completed_by": None,
        "deep_link": f"/specimen/{specimen['id']}/tending",
    }


def _mock_tasks(on: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A plausible day: some due, some already covered by yesterday's rain."""
    noon = datetime.combine(on, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
    due, satisfied = [], []
    for index, specimen in enumerate(fixtures.specimens()):
        species = fixtures.by_id(fixtures.species(), specimen.get("species_id") or "")
        interval = int((species or {}).get("water_interval_days") or 7)
        if (on.toordinal() + index) % max(interval, 2) != 0:
            continue
        litres = specimen.get("container_litres") or 20
        amount = int(min(1500, max(150, litres * 25)))
        location = fixtures.by_id(
            fixtures.locations(), specimen.get("location_id") or ""
        )
        rained_on = bool(
            specimen.get("is_outdoor") and location and not location.get("is_covered")
        )
        if rained_on and index % 2 == 0:
            satisfied.append(
                _task(
                    specimen,
                    "water",
                    noon,
                    status="satisfied",
                    satisfied_by="rain",
                    amount_ml=amount,
                )
            )
        else:
            due.append(_task(specimen, "water", noon, amount_ml=amount))
    return due, satisfied


@router.get("/tending/rounds")
async def get_morning_rounds(on: date | None = None) -> dict[str, Any]:
    day = on or date.today()
    due, satisfied = _mock_tasks(day)
    forecast = fixtures.baseline_weather()["days"][0]
    return {
        "date": day.isoformat(),
        "greeting": "Good morning. The greenhouse is stirring.",
        "due": due,
        "satisfied": satisfied,
        "alerts": [],
        "weather": {
            "time": f"{forecast['date']}T00:00:00Z",
            "temp_min_c": forecast["tmin_c"],
            "temp_max_c": forecast["tmax_c"],
            "precip_mm": forecast["precip_mm"],
            "condition": forecast["condition"],
        },
    }


@router.get("/tending/tasks")
async def list_tasks(
    status: str | None = None, specimen_id: str | None = None
) -> list[dict[str, Any]]:
    due, satisfied = _mock_tasks(date.today())
    rows = due + satisfied
    if status:
        rows = [r for r in rows if r["status"] == status]
    if specimen_id:
        rows = [r for r in rows if r["specimen"]["id"] == specimen_id]
    return rows


@router.get("/tending/care-rules")
async def list_care_rules(specimen_id: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for specimen in fixtures.specimens():
        if specimen_id and specimen["id"] != specimen_id:
            continue
        species = fixtures.by_id(fixtures.species(), specimen.get("species_id") or "")
        outdoor = specimen.get("is_outdoor")
        rows.append(
            {
                "id": f"rule-water-{specimen['id'][-4:]}",
                "species_id": None,
                "specimen_id": specimen["id"],
                "task_type": "water",
                "strategy": "water_balance" if outdoor else "interval",
                "base_interval_days": (species or {}).get("water_interval_days"),
                "amount_ml": None,
                "modifiers": {"season": {"winter": 1.6}, "dormancy": "suspend"},
                "months": [],
                "enabled": True,
            }
        )
    return rows


@router.get("/tending/feeds")
async def list_calendar_feeds() -> list[dict[str, Any]]:
    base = get_settings().public_base_url
    token = "mock-token-do-not-ship"
    return [
        {
            "id": "01890060-0000-7000-8000-000000000001",
            "member_id": MEMBER_ID,
            "name": "All rounds",
            "webcal_url": base.replace("http://", "webcal://").replace(
                "https://", "webcal://"
            )
            + f"/api/v1/calendar/{token}.ics",
            "https_url": f"{base}/api/v1/calendar/{token}.ics",
            "filters": {},
            "push_target": "none",
            "last_rendered_at": None,
            "revoked": False,
        }
    ]


@router.get("/calendar/{token}.ics")
async def get_calendar_ics(token: str) -> Response:
    """A minimal but valid VCALENDAR, so calendar clients can be tested in S0."""
    due, _ = _mock_tasks(date.today())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//The Ministry of Herbology//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:The Ministry of Herbology",
    ]
    for task in due:
        day = datetime.fromisoformat(task["due_at"].replace("Z", "+00:00")).date()
        lines += [
            "BEGIN:VEVENT",
            f"UID:{task['id']}",
            "SEQUENCE:0",
            f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{task['title']} — {task['plain_title']}",
            f"DESCRIPTION:{task['plain_title']}",
            f"URL:{get_settings().public_base_url}{task['deep_link']}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar")
