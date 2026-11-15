# Task 067 - Transactional Runtime Upgrade 0.14.0

## Objective

Install the locally validated `0.14.0` wheel exactly once, retain a known-good
`0.13.1` rollback artifact and verify the installed services and graphical tray
without sending any automated prompt.

## Action Plan

1. Confirm a clean `develop`, the candidate SHA-256, rollback wheel, free disk
   space, installed version and strict product health.
2. Start one project-scoped Protocol 2 worker for the maintenance session.
3. Execute one explicitly authorized transactional upgrade with no automatic
   retry after an uncertain result.
4. Verify installed version, schema 3, SQLite integrity and strict doctor.
5. Verify that the monitor, Discord reply observer and automation observer were
   restarted and remain active without new restart attempts.
6. Restart the graphical tray so it loads the new Python package, then confirm
   one running instance and construct its preferences offscreen.
7. Record evidence, keep the natural Availability Recovery E2E separate and
   preserve the rollback manifest.

## Result - 2026-11-15

The candidate wheel SHA-256 was
`0f5a0b857dab7a4412f887e3c73e39e6246908783ecac6ed4adcc46dca10a549`.
The single transaction completed from `0.13.1` to `0.14.0` and created the
private rollback manifest at
`~/.local/state/ai-presence-monitor/backups/upgrade-0.13.1-to-0.14.0-20261115-124035-1f3cf04b/manifest.json`.

The installed command reported `ai-presence 0.14.0`. Schema 3 was current,
SQLite integrity was `ok`, and strict doctor passed. The monitor, Discord reply
observer and Prompt Rule/Availability Recovery observer were `active/running`
with zero restarts after the transaction. The tray was restarted as
`ai-presence-tray-session.service`; it was `active/running` with one process
and zero restarts. Its installed offscreen preference check constructed
**Controls**, **Prompt rules** and **Availability recovery**.

## Evidence Boundary

The operator observed a natural account change from 1 percent remaining to 100
percent between two human prompts. That demonstrates a real provider capacity
return, but it occurred before `0.14.0` was installed and before an Availability
Recovery rule was armed. It is therefore not evidence that the observer sent a
prompt. The automated E2E still requires a human-enabled exact-session rule, a
future naturally unavailable-to-available transition, a unique marker that the
human did not type, and later canonical hooks from that same session.
