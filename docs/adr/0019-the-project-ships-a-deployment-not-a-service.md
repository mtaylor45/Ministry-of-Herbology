# 19. The project ships a deployment, not a service

Date: 2026-09-24

## Status

Accepted.

## Context

The plan and rule 5 both assumed a staging environment this project operates:
"the change deploys to staging" is one of the four clauses in the definition of
done, and Workstream B's S1 task was to stand that environment up. It never
happened, because it needed Harbor registry credentials and a Docker swarm
manager that only the maintainer has.

The maintainer has now decided not to supply them, and the reason is good: **this
repository is public.** Credentials for a private registry and a home swarm have
no business in a public project's issue tracker, CI configuration or agent
briefs, and an agent holding them is a worse idea still. The maintainer deploys
to their own Harbor and their own swarm, independently of this repository.

That is not a gap to work around. It is what a self-hosted application actually
is, and the project had been quietly modelling itself as a hosted service with
one privileged operator.

## Decision

**The Ministry of Herbology ships a deployment that other people run.** There is
no project-operated staging environment, no project-owned registry, and no
credential anywhere in this repository or in CI.

Three consequences follow, and they are the whole decision:

### 1. Rule 5's definition of done changes

"The change deploys to staging" becomes:

> **the change comes up from the documented deployment on a clean machine.**

Verified by CI building the images and by the deployment guide being followed
end to end at each sprint demo — not by a URL somebody owns. A change that only
works on one person's swarm is not done.

### 2. Everything an operator must supply is a parameter, never a default

Registry host, image tag, public URL, database credentials, the Home Assistant
token, MQTT credentials, the NWS contact string: all supplied by the operator at
deploy time. The repository carries **names and shapes, never values**.
`.env.example` documents variables; it never holds one that works.

No example value may be usable as-is. A guide that hands out a working password
is how a self-hosted app ends up with ten thousand installations sharing one
credential.

### 3. Secrets are secrets, not environment variables

Anything that grants access — the database password, the HA long-lived token,
MQTT credentials, the optional third-party API keys — is a **Docker swarm
secret**, mounted as a file and read from disk. Environment variables leak into
`docker inspect`, into process listings, into crash reports and into logs.

The two rules already in force stay in force and belong in the guide where the
operator can see them:

- **An MQTT payload never carries a token or an API key.** The hub publishes
  readings and states to Home Assistant; it does not publish credentials.
- **A calendar feed token is the only real credential the app itself issues.**
  It is never logged, never reused across feeds, and revoking one must not
  disturb the others.

> **Addendum, 2026-09-24 — "never logged" was not true, in two places.**
>
> The token rides in the URL path (`/api/v1/calendar/{token}.ics`) because
> Google's and Apple's calendar fetchers send no session and no headers. There
> is nowhere else to put it. That makes every component which logs a request
> path a place the credential lands.
>
> Workstream G found the first: uvicorn writes the path for every request it
> serves. Its own package keeps the promise — no logger, no `print`, and a test
> that says so — but the promise is about the deployment, not about one package.
>
> The second turned up while fixing the first, and is the more instructive.
> Nginx *did* carry an `access_log off` guard, with a comment explaining the
> exact risk: "a calendar token being readable to anyone who can read logs —
> which, on a self-hosted box, is usually a backup." It guarded
> `/api/v1/feeds/`, which no route has ever served. The real paths are
> `/api/v1/calendar/{token}.ics` and `/api/v1/tending/feeds`. Every fetch fell
> through to `location /api/` and wrote the credential into `$request`.
>
> **The intent was right, the comment claimed the risk was handled, and the
> prefix matched nothing.** A guard aimed at the wrong path is worse than no
> guard, because it stops anyone looking again.
>
> Fixed in both halves, and both are now asserted by
> `tests/test_calendar_token_is_never_logged.py` rather than trusted:
> `api/app/log_redaction.py` rewrites the path out of `uvicorn.access` records,
> which also covers running the API with no front end at all; and the Nginx
> guard now names the two paths that actually carry a token — the feed list
> among them, because its *responses* contain webcal URLs with tokens inside.
>
> The status, timing and client address survive redaction, so the log still
> answers the question an operator actually asks it: is the feed being fetched,
> and does it work.

## Consequences

**Workstream B's S3/S4 task is now: make this deployable by a stranger.** Not a
staging deploy — a swarm stack, an nginx front end, secrets handling, a
migration path, backup and restore, and `docs/deploy/` written for somebody who
has never seen this repository. `docs/deploy/` is added to B's owned paths.

**The guide is the deliverable, and it is tested by being followed.** A
deployment document nobody has executed is a wish list. The exit criterion is
that a reader with their own registry and their own swarm gets a working
installation without asking anyone a question.

**The maintainer's own deployment is out of scope and stays that way.** Nobody
on this project needs to know their registry host, their swarm topology or their
domain, and nothing in the repository should be shaped around them.

**CI still proves the images build.** The `Build images` job is what keeps the
Dockerfiles honest now that no deploy follows a merge; it must never be allowed
to become advisory.

## References

- ADR 0002 — the stack (Docker behind Nginx)
- ADR 0009 — Home Assistant is the only sensor route (the HA token is a secret)
- ADR 0010 — no hardware today, build for it anyway
- `docs/deploy/` — the guide this ADR calls for, owned by B
