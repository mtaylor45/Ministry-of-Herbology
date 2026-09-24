"""Notifications through Home Assistant — Workstream F, Sprint 4.

The rest of the Ministry is a screen someone chooses to open. This package is
the part that interrupts them, so it is held to a different standard: every
message here has to be worth a phone lighting up at seven in the morning, and
has to be honest about how much the app actually knows.

| Module | What it does |
| --- | --- |
| ``model.py`` | A notification, a recipient, and how certain the thing is |
| ``copy.py`` | The words. Rule 7's pairing, and the hedging ADR 0018 requires |
| ``policy.py`` | When to send, when to stay quiet, and what not to send twice |
| ``channels.py`` | The transport: Home Assistant's ``notify`` services |
| ``state.py`` | Reading today's rounds, the frost report and integration health |
| ``jobs.py`` | The three Arq jobs, and what they record |
"""
