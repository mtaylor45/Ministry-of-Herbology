"""Care rules, tasks, Morning Rounds and calendar feeds.

Owner: Workstream G. S4 made this real: the handlers below are thin, the
decisions live in ``tending.service`` and ``tending.domain``, and storage is
``FixtureRepository`` when ``MOH_MOCK_MODE=true`` and ``DatabaseRepository``
when a Postgres is attached.

Two things the S0 mock's docstring called contract rather than mock detail, and
was right about both, are kept and hardened:

* every task carries a themed ``title`` *and* a ``plain_title`` (rule 7, and a
  ``NOT NULL`` pair in the frozen schema) — see ``tending.titles``;
* the ICS UID is stable per task. The mock derived it from the due date, which
  is stable only until something reschedules; it is now derived from the
  occurrence's identity, so a moved task updates its calendar event in place
  instead of leaving a second one behind. See ``tending.domain``.

No route is added here that ``contracts/openapi/openapi.yaml`` does not declare.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.settings import get_settings
from tending import schemas, service
from tending.repository import (
    Completion,
    TaskQuery,
    TendingRepository,
    UnknownFeedError,
    UnknownMemberError,
    UnknownSpecimenError,
    get_repository,
)
from tending.titles import TASK_TYPES

router = APIRouter(tags=["tending"])

Repo = Depends(get_repository)


def _base_url() -> str:
    return get_settings().public_base_url


# ----------------------------------------------------------------- the rounds


@router.get("/tending/rounds")
async def get_morning_rounds(
    on: str | None = None, repo: TendingRepository = Repo
) -> dict[str, Any]:
    """Morning Rounds — what needs doing today, and what could not be judged."""
    day = None
    if on:
        try:
            day = datetime.fromisoformat(on).date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Malformed date") from None
    return await service.morning_rounds(repo, day)


# ----------------------------------------------------------------------- tasks


@router.get("/tending/tasks")
async def list_tasks(
    status_: str | None = Query(default=None, alias="status"),
    specimen_id: str | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    repo: TendingRepository = Repo,
) -> list[dict[str, Any]]:
    return await service.list_tasks(
        repo,
        TaskQuery(
            status=status_,
            specimen_id=specimen_id,
            due_before=due_before,
            due_after=due_after,
        ),
    )


@router.post("/tending/tasks/complete-batch")
async def complete_tasks(
    body: schemas.BatchCompletion, repo: TendingRepository = Repo
) -> list[dict[str, Any]]:
    """Batch completion — what the Morning Rounds screen sends.

    Declared before the single-task route so that ``complete-batch`` is never
    read as a ``task_id``. Unknown or already-finished ids are skipped rather
    than refused: a batch of six where one was completed on a phone thirty
    seconds ago should tick off the other five, not fail the lot.
    """
    try:
        return await service.complete(
            repo,
            [str(task_id) for task_id in body.task_ids],
            Completion(completed_by=body.completed_by),
        )
    except UnknownMemberError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post("/tending/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    body: schemas.TaskCompletion | None = None,
    repo: TendingRepository = Repo,
) -> dict[str, Any]:
    """One-tap completion, attributed to a member and logged as a task event."""
    body = body or schemas.TaskCompletion()
    try:
        completed = await service.complete(
            repo,
            [task_id],
            Completion(
                completed_by=body.completed_by,
                amount_ml=body.amount_ml,
                notes=body.notes,
                new_location_id=body.new_location_id,
            ),
        )
    except UnknownMemberError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if not completed:
        raise HTTPException(status_code=404, detail="No such open task")
    return completed[0]


# ------------------------------------------------------------------ care rules


@router.get("/tending/care-rules")
async def list_care_rules(
    specimen_id: str | None = None, repo: TendingRepository = Repo
) -> list[dict[str, Any]]:
    rows = await repo.care_rules(specimen_id)
    return [schemas.care_rule_out(row) for row in rows]


@router.post("/tending/care-rules", status_code=201)
async def create_care_rule(
    body: schemas.CareRuleCreate, repo: TendingRepository = Repo
) -> dict[str, Any]:
    if body.task_type not in TASK_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Unknown task type: {body.task_type}"
        )
    if not body.species_id and not body.specimen_id:
        raise HTTPException(
            status_code=422,
            detail="A care rule applies to a species or a specimen; give one.",
        )
    try:
        row = await repo.create_care_rule(body.model_dump())
    except UnknownSpecimenError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return schemas.care_rule_out(row)


# ---------------------------------------------------------------------- feeds


@router.get("/tending/feeds")
async def list_calendar_feeds(repo: TendingRepository = Repo) -> list[dict[str, Any]]:
    base = _base_url()
    return [schemas.feed_out(row, base_url=base) for row in await repo.feeds()]


@router.post("/tending/feeds", status_code=201)
async def create_calendar_feed(
    body: schemas.CalendarFeedCreate, repo: TendingRepository = Repo
) -> dict[str, Any]:
    """One feed per member and filter set, at its own tokenized URL."""
    try:
        row = await repo.create_feed(body.model_dump())
    except UnknownMemberError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return schemas.feed_out(row, base_url=_base_url())


@router.post("/tending/feeds/{feed_id}/revoke", status_code=204)
async def revoke_calendar_feed(
    feed_id: str, repo: TendingRepository = Repo
) -> Response:
    """Revoke one feed. The others keep working — that is the whole point.

    The token is rotated as well as marked revoked, so the URL somebody pasted
    into a calendar stops resolving immediately rather than merely being
    flagged.
    """
    try:
        await repo.revoke_feed(feed_id)
    except UnknownFeedError:
        raise HTTPException(status_code=404, detail="No such feed") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/calendar/{token}.ics")
async def get_calendar_ics(token: str, repo: TendingRepository = Repo) -> Response:
    """The ICS feed itself. Unauthenticated — the token is the secret.

    A revoked or unknown token gets the same 404. Distinguishing them would
    confirm to an unauthenticated caller that a token they hold was once real.
    """
    document = await service.render_feed(repo, token, base_url=_base_url())
    if document is None:
        raise HTTPException(status_code=404, detail="No such calendar feed")
    return Response(
        document,
        media_type="text/calendar; charset=utf-8",
        headers={
            # Neither a proxy nor a browser should hold a copy of a document
            # fetched with a credential in its URL.
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'inline; filename="ministry-of-herbology.ics"',
        },
    )
