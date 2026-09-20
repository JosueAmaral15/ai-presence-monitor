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

## Phase 4 - Linux System Evidence Observers

Status: implemented and validated on
`codex/task-022-linux-evidence-observers`, then integrated locally into
`develop`.

The phase adds one Linux-only `observe-linux-state` command with independent
read-only collectors:

- process state from an explicit PID, with an expected `/proc/<pid>/comm` name
  and process start ticks used to detect identity mismatch or PID replacement;
- network route/link state from `/proc/net/route` and `/sys/class/net`, without
  DNS lookup, HTTP request, packet transmission or a claim of Internet access;
- power resume evidence from the difference between `CLOCK_BOOTTIME` and
  monotonic elapsed time while a watch process remains alive;
- explicit user-systemd unit health through `systemctl --user show`, using an
  argument vector, bounded fields and no shell.

The command is one-shot by default and samples network and power unless they
are explicitly skipped. Process and service checks are opt-in targets. The
`--watch` mode rechecks the exact active worker before and after every sample;
`finish` stops the observer. Dry-run performs one local sample and writes no
database. Every persisted fact has the same bounded TTL and none updates
presence clocks.

Known limits are normative:

- no default route is evidence about local routing, not proof of an upstream
  outage;
- an observer cannot run while Linux is suspended, so it reports a detected
  resume gap after execution resumes rather than claiming live suspension;
- a one-shot process read cannot rule out PID reuse before its first successful
  sample; an expected process name is therefore recommended;
- an intentionally inactive optional service is not automatically unhealthy;
  Phase 5 must interpret only services the operator selected as required.

Implementation checkpoints:

- [x] bounded collectors and allowlisted states;
- [x] one-shot/watch CLI with active-worker rechecks and dry-run isolation;
- [x] positive interval, TTL, suspend-gap and systemd-timeout validation;
- [x] configuration and `.env.example` defaults;
- [x] focused unit tests with fake `/proc`, `/sys`, clocks and systemctl output;
- [x] live local dry-run without SQLite mutation;
- [x] complete test, coverage, lint, type, build and Python matrix gates;
- [x] task commit and local `develop` integration.

## Phase 5 - Deterministic Diagnosis Engine

Status: implemented and validated on `codex/task-022-diagnosis-engine`, then
integrated locally into `develop`.

This phase adds a one-shot, side-effect-bounded diagnosis workflow. It reads
the exact worker, derives severity from that worker's existing protocol clock,
reduces current evidence to the newest observation batch for each source and
kind, then records one immutable diagnosis and applies one incident transition.

Deterministic precedence for an overdue worker is:

1. explicit account, interaction and context-limit facts;
2. explicit process failure or closure facts;
3. detected suspend/resume and required-service failure facts;
4. local network degradation, with confidence limited because local route
   state does not prove upstream Internet availability;
5. recent Codex activity or a recognized long-running operation;
6. `unexplained_inactivity` when no stronger current fact is sufficient.

The engine will not infer a cause from `usage_available`, a running process, a
default route, an awake one-shot sample or an active service. Conflicting
current Codex sessions fail closed unless the caller supplies the exact
session. Session-neutral evidence may support one selected session, but
session-bound evidence from another session may not be linked.

Incident transitions are intentionally small:

- an overdue non-healthy diagnosis opens or updates the worker's single open
  incident at the current protocol threshold;
- `working` or `long_running_operation` resolves an existing incident;
- a worker inside its threshold records `working` from a bounded presence fact
  and resolves an existing incident instead of opening a new one;
- `--dry-run` computes and prints the transition without writing evidence,
  diagnosis or incident rows;
- notification timestamps are untouched and no Discord, Telegram, alarm,
  Codex input, retry or recovery action exists in this phase.

Implementation checkpoints:

- [x] pure evidence reduction and precedence classifier;
- [x] bounded presence-clock evidence for healthy/overdue decisions;
- [x] one-shot `diagnose` CLI with exact worker/session selection and dry-run;
- [x] deterministic open, update and resolve transitions;
- [x] focused tests for precedence, confidence, expiry, contradictions,
      session isolation, severity and persistence isolation;
- [x] complete coverage, lint, type, build and Python-version gates;
- [x] documentation, task commit and local `develop` integration.

Rollback: before integration, switch back to `develop` and delete the task
branch. After integration, revert the Phase 5 task and merge commits. The
schema is unchanged; diagnoses and incidents already written remain historical
rows and do not affect presence clocks, alerts or input transports.

## Remaining Phases

- [x] Phase 2: prototype an exact-session Codex app-server event subscription
      and document the separate-process ownership boundary.
- [x] Phase 3: implement hook-backed Codex evidence plus sanitized account-limit
      polling; keep shared-endpoint live events disabled.
- [x] Phase 4: add Linux process, network, power and service observers.
- [x] Phase 5: implement diagnosis precedence, confidence and incident
      transitions.
- [x] Phase 6: add deduplicated cause-aware Discord notifications.
- [x] Phase 7: validate one selected cause with fault injection, one real
      Discord delivery and external-channel deduplication confirmation.
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
  in Phase 1, Phase 2, Phase 3 or Phase 4.
- Evidence summaries must remain brief and must not contain secrets or
  transcript content.
- Linux collectors must not read process command lines, environments, open
  files, network payloads, DNS responses or journal content.

## Validation

Phases 1 through 4 require:

```bash
PYTHONPATH=src python3 -m unittest tests.test_diagnostics -v
PYTHONPATH=src python3 -m unittest tests.test_codex_app_server -v
PYTHONPATH=src python3 -m unittest tests.test_codex_evidence -v
PYTHONPATH=src python3 -m unittest tests.test_linux_evidence -v
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

Phase 4 validation result on 2026-09-20:

- 226 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed with 87% coverage;
- Ruff, mypy, compileall, wheel/sdist build and `git diff --check` passed;
- focused tests use isolated `/proc`, `/sys`, clocks and systemctl results to
  cover process replacement, local route/link states, resume gaps, service
  sanitization, dry-run, worker rechecks, TTL and unchanged presence clocks;
- a real dry-run first rejected a shell/Python PID identity mismatch, then
  observed `process:running`, `network:default_route_available`, `power:awake`
  and two `service:active` facts without writing SQLite;
- no external network request, diagnosis, incident, Discord notification,
  alarm, Codex input or recovery action was emitted.

Phase 5 validation result on 2026-09-20:

- 242 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed with 87% total coverage and 98% coverage
  for `diagnosis_engine.py`;
- Ruff, mypy across 34 source modules, compileall, wheel/sdist build and
  `git diff --check` passed;
- focused tests cover precedence, confidence, newest-batch reduction,
  ambiguous-session failure, conservative network claims, unexplained
  fallback, Protocol 1/2 severity, open/update/resolve transitions,
  notification timestamp preservation and dry-run database isolation;
- a real dry-run selected the exact active Codex session, returned `working`
  with high confidence and left the real diagnosis count unchanged;
- no Discord/Telegram notification, alarm, Codex input, retry or recovery
  action was emitted.

## Rollback

Before release integration, switch away from or delete the task branch. The
new tables are additive and unused by the current monitor.

After installation, rolling back the package leaves the additive diagnostic
tables untouched. Existing releases ignore them. Do not delete the tables from
a live database unless a separate backup and destructive migration are
explicitly authorized.

Phase 4 rollback requires no schema reversal. Before integration, switch back
to `develop` and delete the task branch if desired. After integration, revert
the Phase 4 task and merge commits; existing diagnostic rows remain harmless
and expire normally. Stop any manually started `observe-linux-state --watch`
process before package rollback.

Phase 5 rollback also requires no schema reversal. Revert its task and merge
commits to remove classification and the CLI command. Historical diagnostic
rows remain inert; no monitor or notification path consumes them in Phase 5.

## Phase 6 - Deduplicated Cause-Aware Discord Notifications

Status: implemented and validated on
`codex/task-022-diagnostic-notifications`, then integrated locally into
`develop`.

This phase adds one explicit notification policy owner for open diagnostic
incidents. It does not allow evidence observers or the diagnosis engine to send
messages. A semantic notification key contains the incident, diagnosis kind,
confidence and severity, so a repeated diagnosis with the same meaning is
deduplicated while a cause or severity change can produce one new message.

Delivery safety is fail-closed:

- reserve a bounded notification record before any network request;
- use only the configured Discord alert webhook, or the red webhook for red
  severity when present;
- send one POST with mentions disabled and no automatic retry;
- mark the notification delivered and update `last_notified_at` only after a
  confirmed successful HTTP response;
- record only bounded status/failure codes for rejected or uncertain results;
- treat an existing `pending`, `rejected` or `uncertain` semantic key as already
  attempted so later runs do not duplicate it automatically;
- keep Telegram, local alarm, phone webhook, Codex input and recovery outside
  this phase.

Operational guidance requires a dry-run review before an explicitly invoked
real call. Dry-run must not reserve rows or access the network. A missing
webhook must fail before reservation so configuration can be corrected safely.
Live Discord E2E remains Phase 7 work and requires explicit authorization for
the external message.

Implementation checkpoints:

- [x] additive notification-attempt schema and bounded persistence API;
- [x] semantic deduplication independent of diagnosis UUID churn;
- [x] diagnostic-only Discord payload and single-attempt transport;
- [x] one-shot CLI with exact worker selection, dry-run and JSON output;
- [x] atomic confirmed-delivery update of notification and incident state;
- [x] focused tests for success, rejection, uncertainty, crash-safe pending
      state, repeated diagnosis, cause/severity change and no-side-effect dry-run;
- [x] 259 tests on Python 3.10, 3.11 and 3.12, 87% total coverage,
      98% notification-module coverage, Ruff, mypy, build and diff gates;
- [x] real active-worker dry-run returned `no_open_incident`, made no external
      request and left the notification ledger at zero rows;
- [x] documentation completed;
- [x] task commit and local `develop` integration.

Rollback: before integration, switch back to `develop` and delete the task
branch. After integration, revert the Phase 6 task and merge commits. The new
ledger table is additive and inert when the command is absent; do not delete it
from a live database without a backup and a separate destructive migration.

## Next Implementation Step

Phase 7 should validate one authorized real Discord message for each selected
cause/severity scenario and confirm semantic deduplication against the external
channel. Fault injection must also retain rejection, timeout and interrupted
states without retry. Alarm, Codex input and recovery remain outside that
phase. The separate live Codex event adapter remains disabled until a session
hosted through a shared managed endpoint proves exact-thread events E2E.

## Phase 7 - Real Discord Delivery and Fault Injection

Status: validated on `codex/task-022-diagnostic-notification-e2e`, then
integrated locally into `develop`.

The live test uses a temporary isolated SQLite database and a unique marker in
one yellow `usage_limit_exceeded` diagnosis. It must not modify the operational
worker, evidence, incident or notification rows. The sequence is fixed:

1. verify the existing alert webhook is configured without printing it;
2. create one isolated active worker, evidence, diagnosis and incident;
3. run `notify-diagnostic-incident --dry-run` and verify zero attempt rows;
4. invoke the real command once and require `delivered`;
5. invoke the same semantic event again and require `deduplicated` with one
   ledger row total;
6. ask the user to confirm that exactly one message with the unique marker is
   visible in the Discord alert channel;
7. run local-only rejection, timeout and interruption fault injection and
   confirm that later calls deduplicate without a second transport call.

If the real attempt returns `rejected` or `uncertain`, stop immediately. Do not
retry, switch webhook, use Telegram, play an alarm, dispatch Codex input or run
recovery. The temporary database may be removed after recording sanitized
results; webhook URLs and raw external responses must never enter the report.

Acceptance checklist:

- [x] webhook presence verified without secret disclosure;
- [x] dry-run produced the expected bounded event and zero attempts;
- [x] one authorized real POST returned confirmed delivery;
- [x] immediate equivalent invocation returned `deduplicated` with one row;
- [x] user confirmed exactly one matching Discord message;
- [x] local rejection, timeout and interruption paths remained one-shot;
- [x] focused regression gates passed;
- [x] evidence documented and committed on the task branch;
- [x] integrated locally into `develop`.

Sanitized evidence:

- both configured Discord webhook roles were present; no URL was printed;
- marker:
  `[AI-PRESENCE-DIAGNOSTIC-E2E:96b24d27-e7b1-4e30-863f-29bd30dd8b3f]`;
- selected scenario: `usage_limit_exceeded`, high confidence, yellow severity;
- dry-run result: `would_send`, zero notification rows;
- real result: `delivered`, one delivered row and updated
  `last_notified_at`;
- immediate equivalent invocation: `deduplicated`, still one row;
- the isolated temporary database was removed after the run;
- local HTTP rejection, raw timeout/transport uncertainty and unexpected
  interruption tests passed without a second transport call;
- 259 tests passed on Python 3.10, 3.11 and 3.12; Python 3.12 coverage remained
  87% overall and 98% for `diagnostic_notifications.py`; Ruff, mypy, package
  build and diff checks passed;
- one read-only bot attempt resolved the alert webhook channel but Discord
  rejected message listing with HTTP 403; it was not retried and no permission
  was changed;
- no Discord application or browser tab was exposed to the current Codex UI,
  so automated visual confirmation was unavailable;
- the user confirmed exactly one matching marker in the Discord channel
  `warnings-worker-robot`;
- task-branch validation and local `develop` integration are complete.

## Phase 8 - Optional One-Shot Recovery Coordinator

Status: implementation validated on `codex/task-022-recovery-coordinator`;
local `develop` integration pending.

This phase adds an explicitly invoked, disabled-by-default recovery consumer.
It does not run from an observer, diagnosis, notification, monitor timer or
background service. A real attempt always requires `--authorize-once`; the
persistent task-automation control is intentionally insufficient.

The first recovery action is deliberately narrow:

- action: one local native `continue` through `codex queue`;
- eligible causes: `codex_closed` with medium/high confidence or
  `codex_crashed` with high confidence;
- prerequisites: active worker, open incident, current unexpired diagnosis,
  exact persisted session and confirmed Discord delivery for the same semantic
  diagnostic event;
- excluded paths: GUI, remote input, delay, Telegram, alarm, phone, recovery
  chaining and presence-clock synchronization;
- deduplication: at most one reserved `native_continue` action per incident,
  regardless of later diagnosis UUID or severity changes;
- completion states: `dispatch_started`, `input_emitted` or `uncertain`;
  every reserved state is terminal for automatic dispatch and cannot retry.

`dispatch_started` and `input_emitted` remain transport evidence only. Neither
resolves the incident. Recovery requires a later same-session hook and a new
diagnosis transition to healthy state. Dry-run evaluates the same eligibility
without reserving a row, checking the executable or sending input.

Acceptance checklist:

- [x] additive recovery ledger and race-safe one-attempt persistence API;
- [x] cause, confidence, expiry, session and delivered-notification gates;
- [x] explicit one-invocation authorization enforced in the domain workflow;
- [x] local native-only dispatch with no activity synchronization;
- [x] terminal deduplication after success, detached start, uncertainty or
      interruption;
- [x] one-shot CLI with dry-run and bounded JSON output;
- [x] focused tests for eligibility, authorization, success, deduplication,
      uncertainty, stale diagnosis, missing notification and no-side-effect
      dry-run;
- [x] full coverage, lint, type, build and Python-version gates: 271 tests on
      Python 3.10, 3.11 and 3.12, 88% total coverage and 93% coordinator
      coverage;
- [x] human/AI-worker, architecture, decision, requirement and security docs;
- [ ] task commit and local `develop` integration.

The exact active-worker source dry-run returned `no_open_incident` with exit
status zero. It reserved no recovery and emitted no input.

No real recovery input is authorized by this implementation phase. A separate
E2E must use a unique marker, exact noncritical test session and explicit user
authorization for that single dispatch.
