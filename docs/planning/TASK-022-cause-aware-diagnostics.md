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

## Phase 2 - Codex App Server Feasibility

Status: implemented and locally validated on
`codex/task-022-app-server-probe`.

The bounded prototype adds `probe-codex-app-server`. Its request allowlist is
limited to initialization, metadata-only thread reads, structured account
limit reads and explicit observational resume/unsubscribe. It does not expose
turn input, queue, GUI automation, persistence, notification or recovery.

Local Codex CLI 0.154.0 results for the exact current session:

- separate stdio App Server initialization passed;
- `thread/read(includeTurns=false)` passed and returned `notLoaded` in the
  child process;
- `account/rateLimits/read` passed with sanitized structured data;
- `thread/resume(excludeTurns=true)` failed with `-32600`, sanitized as
  `thread_already_active`;
- no live event claim is possible because the existing GUI-owned session could
  not be subscribed from the independent child.

The result disproves the assumption that an arbitrary second stdio process can
observe an already-active GUI session. Production work must use hooks and safe
rate-limit polling now, or intentionally host future sessions through a shared
managed App Server endpoint before enabling a live adapter.

See `docs/CODEX-APP-SERVER-PROBE.md` for operation and AI-worker rules.

## Phase 3 - Codex Evidence Observers

Status: implemented and validated on
`codex/task-022-codex-evidence-observers`, then integrated locally into
`develop`.

Recognized same-session hooks now write two independent records after a worker
has been explicitly started: the existing presence observation and a bounded,
expiring diagnostic fact. Unknown hook types may preserve their legacy presence
observation but do not become diagnostic evidence. Hook evidence uses constant
summaries and never retains the hook payload, prompt, message, command or tool
name.

`observe-codex-limits` starts a dedicated stdio child and calls only
`account/rateLimits/read`. It classifies the sanitized response as usage
available, usage blocked, a documented or future account limit, spend control,
or unknown state. `ordinary_usage_allowed` takes precedence over credit
availability because a false credit balance alone does not prove a usage limit.

The command is one-shot by default. `--watch` rechecks the exact worker before
each poll and exits when `finish` makes that worker idle. Both paths store only
diagnostic evidence: they do not update activity clocks, diagnose a cause,
open an incident, notify, alarm, send input or perform recovery. Live App
Server subscription remains disabled.

## Remaining Phases

- [x] Phase 2: prototype an exact-session Codex app-server event subscription
      and document the separate-process ownership boundary.
- [x] Phase 3: implement hook-backed Codex evidence plus sanitized account-limit
      polling; keep shared-endpoint live events disabled.
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
  in Phase 1, Phase 2 or Phase 3.
- Evidence summaries must remain brief and must not contain secrets or
  transcript content.

## Validation

Phase 1 and Phase 2 require:

```bash
PYTHONPATH=src python3 -m unittest tests.test_diagnostics -v
PYTHONPATH=src python3 -m unittest tests.test_codex_app_server -v
PYTHONPATH=src python3 -m unittest tests.test_codex_evidence -v
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

Phase 2 validation result on 2026-09-14:

- 189 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed with 86% coverage;
- Ruff, mypy, compileall, wheel/sdist build and `git diff --check` passed;
- live metadata and rate-limit reads succeeded against Codex CLI 0.154.0;
- the exact active-thread subscription failed closed with the sanitized
  `thread_already_active` reason;
- no prompt, turn, queue input, GUI action, Discord notification, database
  evidence or recovery action was emitted.

Phase 3 validation result on 2026-09-14:

- 203 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed with 86% coverage;
- Ruff, mypy, compileall, wheel/sdist build and `git diff --check` passed;
- a live bounded dry-run returned `usage_available` from the installed Codex
  App Server without creating or writing SQLite evidence;
- focused tests prove hook allowlisting, TTLs, one-shot and watch behavior,
  worker rechecks, unknown-value collapse and unchanged presence clocks;
- no live subscription, Discord notification, local alarm, Codex input,
  incident, diagnosis or recovery action was emitted.

## Rollback

Before release integration, switch away from or delete the task branch. The
new tables are additive and unused by the current monitor.

After installation, rolling back the package leaves the additive diagnostic
tables untouched. Existing releases ignore them. Do not delete the tables from
a live database unless a separate backup and destructive migration are
explicitly authorized.

## Next Implementation Step

Phase 4 should add independent Linux process, network, power and service-health
observers. Each observer must persist only bounded facts, use explicit TTLs and
remain unable to update presence clocks, notify or recover. The separate live
Codex event adapter remains disabled until a session hosted through a shared
managed endpoint proves exact-thread events E2E.
