# Task 022 - Cause-aware Diagnostics

## Goal

Replace undifferentiated inactivity reporting with evidence-backed diagnoses
without allowing individual observers to send notifications or trigger recovery
actions independently.

The desired flow is:

```text
evidence observers
        |
        v
diagnostic_evidence
        |
        v
diagnosis engine
        |
        v
diagnostic_diagnoses -> diagnostic_incidents -> notification policy
                                                   |
                                                   v
                                      optional recovery coordinator
```

## Architectural Decision

An observer reports only a bounded fact from its own evidence source. The
diagnosis engine will correlate those facts and select one primary diagnosis
with a confidence level. The incident state machine will own notification
deduplication and lifecycle. Recovery remains a separate, disabled-by-default
consumer.

This separation prevents a network observer, process observer and Codex
observer from sending contradictory alerts for one inactivity episode.

## Diagnostic Vocabulary

Evidence sources:

- Codex app-server and Codex hooks;
- process, network and power state;
- pending interaction and service health;
- workspace activity as supporting evidence only.

Diagnoses:

- `working` and `long_running_operation`;
- `waiting_for_user` and `waiting_for_approval`;
- `usage_limit_exceeded` and `context_window_exceeded`;
- `network_unavailable`, `codex_closed` and `codex_crashed`;
- `system_suspended` and `observer_unhealthy`;
- `unexplained_inactivity` when no stronger cause is supported.

The project deliberately uses `unexplained_inactivity` instead of claiming
that genuine inactivity has been proven.

## Phase 1 - Domain and Persistence Foundation

Status: implemented and validated on `codex/task-022-diagnostic-foundation`,
then integrated locally into `develop`. Later observer and notification phases
remain pending.

Deliverables:

- typed evidence, diagnosis, confidence, severity and incident states;
- additive SQLite tables and indexes;
- ordered many-to-many links from diagnoses to immutable evidence;
- at most one open diagnostic incident per worker;
- incident update, notification timestamp and resolution lifecycle;
- compatibility initialization through the existing `PresenceStore`;
- focused migration, validation, correlation and lifecycle tests.

The foundation stores concise state labels and summaries. It does not store
Codex transcripts, prompts, arbitrary app-server payloads, tokens, webhooks or
environment values.

## Remaining Phases

- [ ] Phase 2: prototype an exact-session Codex app-server event subscription.
- [ ] Phase 3: implement the Codex event observer and map authoritative errors.
- [ ] Phase 4: add Linux process, network, power and service observers.
- [ ] Phase 5: implement diagnosis precedence, confidence and incident
      transitions.
- [ ] Phase 6: add deduplicated cause-aware Discord notifications.
- [ ] Phase 7: validate each cause with fault injection and real integration
      tests.
- [ ] Phase 8: design an optional one-shot recovery coordinator after detection
      is stable.

Windows implementations remain preserved but disabled behind the existing
experimental runtime gate. Task 022 targets the supported Linux runtime first.

## Safety Invariants

- Evidence collection never updates Protocol 1 or Protocol 2 activity clocks by
  itself.
- No observer sends Discord, Telegram, local alarm or Codex input directly.
- No diagnosis is created without at least one persisted evidence record.
- Linked evidence must belong to the diagnosed worker and cannot span Codex
  sessions.
- Opening a new diagnosis updates the worker's current open incident instead of
  creating parallel contradictory incidents.
- No automatic recovery, retry, GUI fallback or `continue` dispatch is present
  in Phase 1.
- Evidence summaries must remain brief and must not contain secrets or
  transcript content.

## Validation

Phase 1 requires:

```bash
PYTHONPATH=src python3 -m unittest tests.test_diagnostics -v
python3 scripts/quality_check.py
```

The focused suite covers additive initialization, typed evidence, expiry,
cross-worker/session rejection, ordered evidence links, single-incident update,
notification timestamps and resolution.

Validation result on 2026-09-13:

- 177 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed with 87% coverage;
- Ruff, mypy, compileall, wheel/sdist build and `git diff --check` passed;
- no live observer, Discord notification or recovery action was executed.

Integration result:

- task commit: `de1625b`;
- merged locally into `develop` after the complete gate passed;
- `main` was not promoted because Task 022 still requires live observer and
  Discord integration phases;
- no remote push was performed without a separate request.

## Rollback

Before release integration, switch away from or delete the task branch. The
new tables are additive and unused by the current monitor.

After installation, rolling back the package leaves the additive diagnostic
tables untouched. Existing releases ignore them. Do not delete the tables from
a live database unless a separate backup and destructive migration are
explicitly authorized.

## Next Implementation Step

Phase 2 should be a read-only feasibility spike. It must determine whether an
external client can subscribe to the exact Codex GUI session and receive
`turn/completed`, `thread/status/changed`, `thread/tokenUsage/updated`,
`contextCompaction` and structured `codexErrorInfo` events without taking over
the session. No production observer should be built until that capability is
demonstrated locally.
