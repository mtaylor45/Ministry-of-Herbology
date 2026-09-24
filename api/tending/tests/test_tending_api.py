"""The five endpoints, end to end on the mock stack.

This is the S4 exit criterion as a test: daily care runs from the app, and the
tasks appear in a calendar. Every assertion here is something a person would
notice going wrong.
"""

from __future__ import annotations

from icalendar import Calendar

MEMBER = "01890050-0000-7000-8000-000000000001"


def rounds(client) -> dict:
    response = client.get("/api/v1/tending/rounds")
    assert response.status_code == 200
    return response.json()


def feed_path(client) -> str:
    feeds = client.get("/api/v1/tending/feeds").json()
    return feeds[0]["https_url"].replace("http://localhost:8000", "")


# ----------------------------------------------------------------- the rounds


def test_morning_rounds_groups_the_day(client):
    body = rounds(client)
    assert set(body) >= {"date", "greeting", "due", "satisfied", "alerts", "weather"}
    assert body["due"], "the fixture household has plants that want watering"


def test_the_greeting_is_themed_and_plain_in_one_breath(client):
    """Rule 7 applies to prose, not only to task titles."""
    greeting = rounds(client)["greeting"]
    assert "greenhouse" in greeting
    assert "due today" in greeting


def test_every_task_pairs_a_themed_title_with_a_plain_one(client):
    for task in rounds(client)["due"]:
        assert task["title"] and task["plain_title"]
        assert task["title"] != task["plain_title"]


def test_a_task_built_on_an_uncited_interval_says_so_where_it_shows(client):
    """ADR 0004's visible mark, on a field a 1.2.0 client already renders."""
    marked = [t for t in rounds(client)["due"] if t["confidence"] == "unknown"]
    assert marked, "the fixture species carry uncited intervals"
    for task in marked:
        assert "no citation" in (task["detail"] or "")


def test_a_plant_that_cannot_be_scheduled_is_named_rather_than_dropped(client):
    """A silent plant is indistinguishable from a plant that needs nothing."""
    for row in rounds(client)["unscheduled"]:
        assert row["specimen_id"] and row["reason"].strip()


def test_an_unparseable_date_is_refused_rather_than_guessed(client):
    assert (
        client.get("/api/v1/tending/rounds", params={"on": "soon"}).status_code == 422
    )


# ----------------------------------------------------------------------- tasks


def test_tasks_filter_by_status_and_specimen(client):
    everything = client.get("/api/v1/tending/tasks").json()
    assert everything
    specimen_id = everything[0]["specimen"]["id"]
    filtered = client.get(
        "/api/v1/tending/tasks", params={"specimen_id": specimen_id}
    ).json()
    assert filtered and all(t["specimen"]["id"] == specimen_id for t in filtered)
    done = client.get("/api/v1/tending/tasks", params={"status": "done"}).json()
    assert done == []


def test_generation_is_idempotent_across_requests(client):
    """Running the schedule twice must not double the calendar."""
    first = {t["id"] for t in client.get("/api/v1/tending/tasks").json()}
    second = {t["id"] for t in client.get("/api/v1/tending/tasks").json()}
    assert first == second


def test_one_tap_completion_is_attributed_and_dated(client):
    task = rounds(client)["due"][0]
    body = client.post(
        f"/api/v1/tending/tasks/{task['id']}/complete",
        json={"completed_by": MEMBER, "amount_ml": 500, "notes": "Looked thirsty"},
    ).json()
    assert body["status"] == "done"
    assert body["completed_at"]
    assert body["completed_by"]["id"] == MEMBER
    assert body["amount_ml"] == 500


def test_completing_a_task_takes_it_out_of_the_rounds(client):
    task = rounds(client)["due"][0]
    client.post(f"/api/v1/tending/tasks/{task['id']}/complete", json={})
    assert task["id"] not in {t["id"] for t in rounds(client)["due"]}


def test_batch_completion_is_what_morning_rounds_sends(client):
    ids = [task["id"] for task in rounds(client)["due"][:3]]
    body = client.post(
        "/api/v1/tending/tasks/complete-batch",
        json={"task_ids": ids, "completed_by": MEMBER},
    ).json()
    assert {t["id"] for t in body} == set(ids)
    assert all(t["status"] == "done" for t in body)


def test_a_batch_containing_an_already_finished_task_still_ticks_off_the_rest(client):
    ids = [task["id"] for task in rounds(client)["due"][:2]]
    client.post(f"/api/v1/tending/tasks/{ids[0]}/complete", json={})
    body = client.post(
        "/api/v1/tending/tasks/complete-batch", json={"task_ids": ids}
    ).json()
    assert [t["id"] for t in body] == [ids[1]]


def test_completing_an_unknown_task_is_a_404_not_a_silent_success(client):
    response = client.post(
        "/api/v1/tending/tasks/00000000-0000-0000-0000-000000000000/complete", json={}
    )
    assert response.status_code == 404


def test_completion_retires_the_cycle_so_the_calendar_lets_go(client):
    """The old occurrences are fiction once the anchor moves; they must be
    cancelled rather than left sitting in somebody's calendar."""
    task = rounds(client)["due"][0]
    specimen_id = task["specimen"]["id"]
    client.post(f"/api/v1/tending/tasks/{task['id']}/complete", json={})
    remaining = [
        t
        for t in client.get(
            "/api/v1/tending/tasks", params={"specimen_id": specimen_id}
        ).json()
        if t["task_type"] == task["task_type"]
    ]
    assert remaining
    assert all(t["status"] in {"done", "cancelled", "due"} for t in remaining)
    assert any(t["status"] == "cancelled" for t in remaining)


def test_a_bring_indoors_completion_records_the_new_location(client):
    """Sprint 6 performs the move; the history must not be lost until then."""
    task = rounds(client)["due"][0]
    response = client.post(
        f"/api/v1/tending/tasks/{task['id']}/complete",
        json={"new_location_id": "01890010-0000-7000-8000-000000000002"},
    )
    assert response.status_code == 200


# ------------------------------------------------------------------ care rules


def test_care_rules_are_listed_per_specimen(client):
    rules = client.get("/api/v1/tending/care-rules").json()
    assert rules
    one = rules[0]["specimen_id"]
    assert all(
        r["specimen_id"] == one
        for r in client.get(
            "/api/v1/tending/care-rules", params={"specimen_id": one}
        ).json()
    )


def test_a_household_rule_overrides_the_derived_one(client):
    specimen_id = rounds(client)["due"][0]["specimen"]["id"]
    created = client.post(
        "/api/v1/tending/care-rules",
        json={
            "specimen_id": specimen_id,
            "task_type": "water",
            "strategy": "interval",
            "base_interval_days": 3,
            "modifiers": {"season": {"winter": 2}},
        },
    )
    assert created.status_code == 201
    rules = client.get(
        "/api/v1/tending/care-rules", params={"specimen_id": specimen_id}
    ).json()
    water = [r for r in rules if r["task_type"] == "water"]
    assert any(r["base_interval_days"] == 3 for r in water)


def test_a_rule_for_an_unknown_task_type_is_refused(client):
    response = client.post(
        "/api/v1/tending/care-rules",
        json={"specimen_id": "x", "task_type": "sing_to", "strategy": "interval"},
    )
    assert response.status_code == 422


def test_a_rule_that_applies_to_nothing_is_refused(client):
    response = client.post(
        "/api/v1/tending/care-rules",
        json={"task_type": "water", "strategy": "interval"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------- feeds


def test_a_fresh_install_has_a_subscribable_feed(client):
    feed = client.get("/api/v1/tending/feeds").json()[0]
    assert feed["webcal_url"].startswith("webcal://")
    assert feed["https_url"].endswith(".ics")
    assert "token" not in feed


def test_the_feed_parses_as_a_calendar_with_stable_unique_uids(client):
    response = client.get(feed_path(client))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.headers["cache-control"] == "private, no-store"
    calendar = Calendar.from_ical(response.text)
    uids = [str(c["UID"]) for c in calendar.walk() if c.name == "VEVENT"]
    assert uids and len(uids) == len(set(uids))
    assert all(uid.startswith("task-") for uid in uids)


def test_the_uid_survives_a_completion_and_a_regeneration(client):
    before = {
        str(c["UID"])
        for c in Calendar.from_ical(client.get(feed_path(client)).text).walk()
        if c.name == "VEVENT"
    }
    after = {
        str(c["UID"])
        for c in Calendar.from_ical(client.get(feed_path(client)).text).walk()
        if c.name == "VEVENT"
    }
    assert before == after


def test_each_feed_gets_its_own_token(client):
    first = client.get("/api/v1/tending/feeds").json()[0]
    second = client.post(
        "/api/v1/tending/feeds",
        json={
            "member_id": MEMBER,
            "name": "Outdoors only",
            "filters": {"outdoor": True},
        },
    ).json()
    assert second["https_url"] != first["https_url"]


def test_a_filtered_feed_carries_only_what_it_asked_for(client):
    created = client.post(
        "/api/v1/tending/feeds",
        json={
            "member_id": MEMBER,
            "name": "Outdoors only",
            "filters": {"outdoor": True},
        },
    ).json()
    text = client.get(created["https_url"].replace("http://localhost:8000", "")).text
    outdoor_ids = {
        t["specimen"]["id"]
        for t in client.get("/api/v1/tending/tasks").json()
        if t["specimen"]["is_outdoor"]
    }
    for component in Calendar.from_ical(text).walk():
        if component.name == "VEVENT":
            assert any(pid in str(component["URL"]) for pid in outdoor_ids)


def test_revoking_one_feed_leaves_the_others_working(client):
    """The whole reason a feed has its own token."""
    keep = client.get("/api/v1/tending/feeds").json()[0]
    doomed = client.post(
        "/api/v1/tending/feeds", json={"member_id": MEMBER, "name": "Old phone"}
    ).json()
    doomed_path = doomed["https_url"].replace("http://localhost:8000", "")

    assert (
        client.post(f"/api/v1/tending/feeds/{doomed['id']}/revoke").status_code == 204
    )
    assert client.get(doomed_path).status_code == 404
    assert (
        client.get(keep["https_url"].replace("http://localhost:8000", "")).status_code
        == 200
    )


def test_a_revoked_feed_stops_publishing_its_url(client):
    created = client.post(
        "/api/v1/tending/feeds", json={"member_id": MEMBER, "name": "Old phone"}
    ).json()
    client.post(f"/api/v1/tending/feeds/{created['id']}/revoke")
    revoked = [
        f
        for f in client.get("/api/v1/tending/feeds").json()
        if f["id"] == created["id"]
    ]
    assert revoked[0]["revoked"] is True
    assert revoked[0]["https_url"] == ""


def test_revoking_a_feed_that_does_not_exist_is_a_404(client):
    response = client.post(
        "/api/v1/tending/feeds/00000000-0000-0000-0000-000000000000/revoke"
    )
    assert response.status_code == 404


def test_an_unknown_token_is_a_404_and_says_nothing_else(client):
    response = client.get("/api/v1/calendar/not-a-real-token.ics")
    assert response.status_code == 404
    assert "revoked" not in response.text.lower()


def test_rendering_a_feed_records_when_it_was_last_fetched(client):
    client.get(feed_path(client))
    assert client.get("/api/v1/tending/feeds").json()[0]["last_rendered_at"]
