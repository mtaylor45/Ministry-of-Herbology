# S4 — Home and IoT (Workstream F)

Appended by F ahead of the demo. A owns the sprint's own summary.

## The task

Notifications through Home Assistant for the three things worth interrupting
somebody about: today's rounds, a frost alert, and an adapter that has stopped
answering. S3 built the adapter; this is the part that reaches a person who is
not looking at the app.

## Shipped

- **`workers/hub/notify/`** — the model, the copy, the policy, the channel, the
  reader and three Arq jobs (`notify_rounds`, `notify_frost`,
  `notify_integration_health`), registered and scheduled.
- **`workers/hub/credentials.py`** — S3's MQTT credential guard, lifted out so
  the notification channel runs the same check.
- **`workers/hub/mocks/ministry.py`** — `MorningRounds` and `FrostReport` in the
  contract's shape from the frozen fixtures, so the whole path demonstrates
  offline.
- **`publish_to_mqtt`'s seam, filled.** See "One thing S3 left broken", below.
- 140 tests, network-free, on top of S3's 156.

## The three cadences, and why they are different

**Frost runs every fifteen minutes.** That is the requirement, not a
preference. A Freeze Warning issued at 2 PM for that night is not something to
learn about at 3, and a job on a daily schedule learns about it the following
morning — after the plants died. The job is cheap (one GET, and nothing sent
unless the forecast is new news), so the interval is set by how late an alert
may be, not by how much it costs.

**Frost is the one kind that ignores quiet hours**, and the override is stated
in `policy.may_send` rather than left as an oversight. A person who asked not to
be disturbed after ten did not mean "let the lemon tree die quietly". The
override is only defensible because the switch exists: a household that
disagrees sets `frost: false` in `notify_prefs`, and a test asserts that works.
The message also carries both platforms' urgency hints — iOS's
`interruption-level: time-sensitive` and Android's `ttl: 0` / `priority: high`
— because a notification held for the next summary is a notification that did
not happen, and this worker has no way to learn what kind of phone somebody has.

**Rounds go out once, at the hour the member chose, in the site's local time.**
The cron is hourly and the *job* decides whether the local clock has reached
that hour: a cron in UTC cannot know, and a household that moves through a DST
change would otherwise get their rounds an hour out twice a year.

**Health waits.** A hub reboots, an access point drops, a container restarts.
One failed poll is a blip; a fault is a failure still there after thirty
minutes. Notifying on the first error would make this the noisiest of the three
and the least urgent, and a health alert people have learned to swipe away is
worse than none on the day it means something. An integration that has *never*
answered is reported immediately — it has had its grace period since the
deployment started, and "this has never once worked" is exactly the setup
problem worth saying.

## What the notifications are not allowed to do

Four rules, each with tests that fail if the code stops keeping them.

**They never carry a credential.** `assert_clean` runs over every rendered title,
body and data blob before the transport sees it. This is not theoretical:
Workstream G escalated in S4 that the calendar token was being written to two
access logs, and it was. A notification body is a more attractive door onto the
same mistake, because it is assembled from a task's `detail` and an
integration's `last_error` — free text somebody else wrote. A feed URL pasted
into a task detail is refused, by pattern, with the refusal naming the field
and not repeating the value.

The check moved out of `workers/hub/mqtt.py` into its own module rather than
being copied. A broker retains a message until something replaces it and a phone
keeps a notification until somebody swipes it: one rule, one implementation, two
senders, and one place to add the next pattern.

**They carry the task's plain title, verbatim.** Not the themed title, not a
rewrite of either. Rule 7 pairs themed copy with plain copy and a phone at seven
in the morning is the least appropriate place for the themed half alone, so the
Ministry's voice travels on `Notification.themed_title`, beside the plain title
rather than instead of it, for a surface that wants it.

**They do not read like measurements.** Contract 1.3.0's `confidence`,
`degraded` and `degradations[]` are parsed into a `Certainty` at the edge and the
copy has no path that renders a degraded input as a bare instruction.
`Degradation.detail` is specified as "a plain sentence, written to be shown to
the reader as-is", so it is shown as-is.

The state that mattered most to get right is the third one. Those three fields
are **G's escalation 1 and are not in the frozen 1.2.0 contract**, so a
deployment running a 1.2.0 API serves a task with no certainty on it at all.
Absence is not confidence. `Certainty.stated` keeps "the scheduler is confident"
apart from "the scheduler is running a version that cannot express confidence",
and hedges the second — because the alternative is that the one API version
which can tell us nothing is the one we sound surest about.

And under ADR 0010 nothing measures the soil, so no sentence says the soil is
dry. Every watering carries the standing caveat that it was worked out from the
weather and the household's settings. The sensor wording exists and is reachable
only by a task that names `satisfied_by: sensor`, which nothing produces today:
the day a probe appears the caveat drops out on its own, with no other change.

**They never claim all is well.** There is no all-clear notification in this
application. `MorningRounds.unscheduled[]` means the app cannot always tell
"nothing needs doing" from "I could not work out what these plants need", and of
those two only silence is honest about both. When something *is* sent, the
plants that could not be judged are counted in it — and when the API omits the
key entirely (G's escalation 3, also not in 1.2.0) the message says the list may
not be everything, because a missing key has not told us there are none, it has
told us nothing. The frost report's `unassessable[]` is handled the same way.

## Two defects the tests caught

Both were found by tests written against the brief rather than against the code,
which is the argument for writing them that way.

1. **The ledger stamped entries with the wall clock and read them back against
   the job's clock.** The two are the same in a deployment and are not the same
   under a frozen clock, so the dedupe quietly did nothing whenever they
   differed — the exact class of failure this workstream is supposed to be
   watching for, in this workstream's own code. Both ends use the job's clock.

2. **A dedupe key named the member, not the destination.** Two members pointing
   `notify_prefs` at one kitchen tablet made it chime twice for the same frost,
   which is how a household learns to ignore it. The key names the service now:
   one tablet, one chime; two phones, two messages.

## One thing S3 left broken, now fixed

`publish_to_mqtt` took its state from `ctx`, and **nothing filled `ctx`**. A
deployed worker published a permanent `0` on `herbology/rounds/due` and a
permanent `OFF` on `herbology/frost/state` — the contract's topics, carrying
nothing. It now reads the same two endpoints the notification jobs read, so a
household can hang a Home Assistant automation off the frost sensor and have it
mean something.

A read that fails publishes **nothing**. A retained zero cannot be taken back:
the availability topic can say "we are not answering", and a retained `0` on a
task count says "there is nothing to do", forever, to anything watching.
`unassessable` does not turn the frost sensor on, for the same reason it does
not read as an alert in a notification — an automation that closed the vents on
"we do not know" would be acting on nothing.

## ADR 0010, kept honestly again

No hardware is pretended into existence anywhere in this branch.

- The **soil-sensor path** is modelled and unreachable: `copy.names_sensor` is
  the single place that decides whether a reading measured anything, and a test
  asserts nothing today can make it true.
- The **irrigation path** needs no new code and has a test saying so. A watering
  the rain or a controller already covered arrives in `MorningRounds.satisfied[]`
  and only `due` is read, so it is simply never notified. The day an irrigation
  controller exists, that is still true.
- The mock world's tasks are stamped `confidence: unknown` and `degraded: true`
  with a degradation that says in plain words they are fixture data — so mock
  mode demonstrates the **hedged** branch, which is what it honestly is. A mock
  producing confident-looking tasks would be this package asserting care facts
  with no citation (rule 6), and would leave the branch that must not be the
  default as the one nobody sees.

## The `notify_prefs` convention

`member.notify_prefs` is `jsonb`, typed `additionalProperties: true` — an open
blob with no stated convention, exactly as `sensor_source.external_ids` was in
S3. This adapter reads:

```json
{
  "home_assistant": {
    "service": "notify.mobile_app_marks_phone",
    "rounds": true,
    "frost": true,
    "health": true,
    "rounds_hour": 7,
    "quiet_hours": [22, 7],
    "units": "metric"
  }
}
```

`service` is a Home Assistant service name, not a credential: the credential is
the token in the Authorization header and it never comes near a payload. Any
domain is accepted — `script.tell_everyone` is a perfectly good way for a
household to route this, and refusing it would be the app deciding how somebody's
hub is organised. A member with no `service` is not a recipient, and that is not
a fault: it is the normal state of a household where one person has the companion
app and two do not.

`MOH_HA_NOTIFY_SERVICE` is the deployment-wide fallback for a member with no
prefs of their own — one household, one phone, nobody who wants to edit a JSON
blob to get their watering reminders. It is empty by default, which reads as
*nobody is set up*, a setup step rather than a fault. Defaulting it to HA's
`notify.notify` would be this app deciding to message every device in somebody's
house.

## For A — five things, none of them worked around

1. **There is no `notification` table, so the ledger is derived from `job_run`.**
   "Have we already told them this?" needs durable state and the frozen schema
   has nowhere for it. Each job records its dedupe keys in `job_run.detail` and
   the next run reads them back over a 36-hour window — one index scan on
   `job_run_job_idx`, no contract change. What it cannot do is what a table
   would: expire one key, or answer *which member* was told without unpacking a
   blob. Requested: a `notification` table (`id, kind, dedupe_key, member_id,
   sent_at, ok`), forward-only. This is the honest workaround, not a preference.

2. **`member.notify_prefs` has no stated convention.** The block above is now
   load-bearing across F and, when the Ministry Office grows a notification
   settings screen, J. It deserves a line in the spec the same way
   `external_ids` did — S3's escalation 5, which is still open.

3. **`fixtures/` has no members file.** `api/inventory`'s mock repository carries
   a single in-code Keeper with `notify_prefs: {}`, so a mock stack read through
   the API can never demonstrate a notification. `MockMinistryReader.members`
   returns C's Keeper — C's id, C's name — with a synthetic `notify_prefs`
   attached and marked as such. A `fixtures/members/members.json` with two
   members, one of whom has a notify service, would replace the derivation
   entirely. Fixtures are L's and A's, so this is a request.

4. **The API's `session` scheme is declared and unenforced, and this worker now
   depends on that.** `MOH_API_URL` is called with no Authorization header and no
   cookie — deliberately, and a test asserts it, because `MOH_HA_TOKEN` belongs
   to Home Assistant and to nothing else. The day the cookie is enforced, this
   worker needs a service identity, and what that should be is A's call rather
   than something to guess at here with a shared secret. Flagged now because the
   change that enforces auth will otherwise break the notifications silently.

5. **`Integration` still has no `status`** — S3's escalation 4, restated because
   S4 gave it a second consumer. The five-way distinction `health.py` computes
   (`ok`, `degraded`, `down`, `stale`, `unconfigured`) is what decides whether a
   notification is sent at all, and `last_ok_at` plus `last_error` cannot express
   *stale*, which is the silent case this whole workstream is about.

**Seconding two of G's.** `Task.confidence`/`degraded`/`degradations[]` (G's 1)
and `MorningRounds.unscheduled[]` (G's 3) now have a second consumer, and this
package reads both defensively against an API that has neither. The degraded
reading is worse than the honest one — every task hedged, because nothing can be
known — so the additions are worth having for the copy's sake as much as for
J's. ADR 0018 §3's advisory-trigger gap on `FrostAlert` is untouched here; the
`advisory` headline is read and carried through when present.

## For B — two variables, and a note

`MOH_API_URL` and `MOH_HA_NOTIFY_SERVICE` need lines in `.env.example` and in the
`worker-hub` service's environment block in `infra/stack/docker-stack.yml` and
`infra/compose/docker-compose.dev.yml`. `MOH_API_URL: http://api:8000` is already
set for the `web` service in both files, so the value is settled; F does not own
those files (rule 2). Neither variable is a secret — one is an internal hostname,
the other a Home Assistant service name.

Still open from S3 and unchanged: `api/pyproject.toml` carries no MQTT client, so
`connect_publisher` still raises with a message naming what is missing. Filling
the publish seam makes that gap matter more than it did — the topics now carry
real state and still cannot reach a broker.

## Verified

The sandbox this ran in had no `.venv`; one was built from `api/pyproject.toml`
and the commands below are the repository's own.

- `.venv/bin/pytest tests/contract -q` — 48 passed
- `.venv/bin/pytest tests api workers scripts -q` — 891 passed, 37 skipped
- `.venv/bin/pytest workers/hub -q` — 296 passed
- `ruff`, `black` (88), `mypy workers/hub` clean
- `scripts/check_ownership.py` — 23 files, all within `workers/hub/`

Every test in this branch is network-free by construction: the autouse fixture
from S3 fails any test that opens a socket or an httpx transport, and it matters
more for the notification path than it did for the poller, because a service call
that reached a real address would both carry a token there and ring somebody's
phone.
