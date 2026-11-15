# Task 065 - Natural Availability Recovery E2E

## Objective

Validate the complete Availability Recovery path for one exact Codex session without
deliberately consuming quota and without treating initial availability as a
recovery event.

## Action Plan

1. Confirm the installed runtime, database, controls and managed services are
   healthy before observing account usage.
2. Start the project-scoped worker and read one sanitized Codex usage snapshot.
3. Inspect only sanitized Availability Recovery counts and states for the current
   worker profile; never print the configured prompt, session identifier or
   credentials.
4. Require the human operator to opt in through the tray, selecting the Codex
   provider and exact session. An AI-worker must
   not enable, rearm or redirect this rule.
5. Let the background observer record natural unavailability and persist
   `waiting_for_availability`.
6. After the same provider becomes available naturally, require a unique
   marker to return to the selected Codex session.
7. Confirm later canonical hooks for that same worker and session. Treat
   `dispatch_started` and `input_emitted` as transport evidence only.
8. Record the evidence, run the release gates and consider `main` promotion
   only after every criterion below passes.

## Acceptance Criteria

- [x] Installed runtime `0.13.1`, schema 3, SQLite integrity and strict doctor
  checks pass.
- [x] Monitor, Discord reply observer and Prompt Rule observer are active.
- [x] The exact project worker has `task_automation` and native input enabled.
- [x] A sanitized one-shot read reports the current real usage state.
- [x] Runtime `0.14.0` is installed transactionally.
- [ ] The human operator has enabled an Availability Recovery rule for the exact
  current Codex session.
- [ ] The provider is observed naturally unavailable.
- [ ] The same provider is later observed naturally available.
- [ ] A unique marker returns to the exact target session without manual entry.
- [ ] Canonical hooks after delivery confirm processing in the same session.

## Evidence - 2026-11-15

The project was clean at `develop` commit `07125f1`. The installed runtime
reported `0.13.1`; strict doctor, schema 3 and database integrity passed. All
three managed services were `active/running`, with historical restart counters
unchanged at `49/19/0`. The root volume retained 7.1 GB free.

The project worker was started in Protocol 2. A one-shot sanitized Codex read
reported `usage_available`. The corresponding worker profile had
`task_automation=true`, native input enabled, and zero configured or enabled
Token Recovery rules. Therefore no exhausted-to-available transition exists
yet and no dispatch is permitted. This is an external observation gate, not a
software failure.

The authorized transaction later installed `0.14.0`, preserved a private
`0.13.1` rollback manifest and passed schema, integrity, strict doctor, managed
service and graphical tray checks. The installed observer reported
`quota_targets=0`, confirming that no Availability Recovery rule is currently
armed. The operator also reported a natural account change from 1 percent to
100 percent before the upgrade. That transition cannot retroactively prove an
observer dispatch and does not satisfy the remaining criteria.

## Human Gate

After the authorized `0.14.0` upgrade, select the current
`ai-presence-monitor` worker profile in the tray, open **Availability
recovery**, select Codex and the exact current session, enable the single rule,
enter a unique marker as the message, and save. Keep the Prompt Rule observer
service running.

After that opt-in, no quota should be consumed deliberately. The observer must
remain armed until the provider naturally becomes unavailable and later
available.
