# Deploying The Ministry of Herbology

**This is a placeholder.** Workstream B is writing the real guide on
`ws-b/s3-deployable-by-anyone`; when that lands it replaces this file wholesale.

Until then, what ADR 0019 commits the project to, so an operator reading this
early knows what to expect:

- **You run it.** There is no hosted instance, no project registry and no
  credential anywhere in this repository. You build the images, push them to a
  registry you control, and deploy them to a swarm you control.
- **Everything you supply is a parameter.** Registry host, image tag, public
  URL, database credentials, the Home Assistant token, MQTT credentials, the NWS
  contact string. `.env.example` documents the names. **No value in this
  repository is usable as-is** — generate your own.
- **Secrets are Docker swarm secrets, mounted as files**, not environment
  variables. Environment leaks into `docker inspect`, process listings, crash
  reports and logs.

Two rules that hold however you deploy:

- **An MQTT payload never carries a token or an API key.** The hub publishes
  readings and states to Home Assistant, nothing else.
- **A calendar-feed token is the only credential the app itself issues.** It is
  never logged, never reused across feeds, and revoking one must not disturb the
  others.

To run it locally instead, with no credentials at all, `make dev` brings up the
development stack against fixtures (`MOH_MOCK_MODE=true`).

See [ADR 0019](../adr/0019-the-project-ships-a-deployment-not-a-service.md).
