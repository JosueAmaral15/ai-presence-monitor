# Task 031 - Discord Observer and Hosted CI Recovery

## Objective

Recover the Discord reply observer from SQLite contention and transient network
failures without replaying uncertain answer delivery, then restore genuine
hosted Linux CI evidence for the public prerelease line.

## Confirmed State

- Installed runtime 0.10.1 and schema 1 are healthy.
- The main monitor and tray are active.
- The reply observer is enabled but failed after SQLite lock, Discord timeout,
  DNS failure and the systemd start limit.
- The database contains no pending remote question; existing rows are expired
  or delivery-confirmed.
- Discord DNS and the public API gateway are currently reachable.
- The latest GitHub Actions Linux jobs contain zero steps. Their check-run
  annotations state that the account is locked because of a billing issue.
- The workflow defines supported Ubuntu/Python jobs correctly; changing it
  cannot unlock the account.

## Safety Boundaries

- Do not print or commit `.env`, Discord credentials, prompts or answers.
- Do not restart the reply observer until the implementation, tests and
  installed-runtime gate are ready.
- Retry only a failed read poll before message processing starts.
- Never retry Discord guidance, Codex input or an uncertain dispatch.
- Configuration errors and non-transient HTTP failures remain fail-closed.
- A service restart is not proof of recovery; require sustained successful
  polls and a clean service check.
- Do not describe local checks as hosted CI. Account recovery needs a new run
  whose Linux jobs execute real steps.

## Phase 1 - Resilience Implementation

1. Configure every `PresenceStore` connection with a bounded SQLite busy
   timeout.
2. Preserve transient/permanent classification from the Discord HTTP client.
3. Return a dedicated temporary-failure result only for safe pre-processing
   failures.
4. In continuous observer mode, apply bounded exponential backoff and reset it
   after a successful poll.
5. Keep one-shot mode observable through a nonzero temporary-failure status.

## Phase 2 - Verification

1. Test SQLite busy timeout and initialization contention.
2. Test retryable network/HTTP classes and permanent HTTP rejection.
3. Test observer backoff, cap, reset and one-shot behavior without real sleep.
4. Run the complete quality gate and Python 3.10/3.11/3.12 matrix.
5. Build and verify a clean patch wheel.

## Phase 1 and Phase 2 Evidence

- Candidate version: 0.10.1.
- Every `PresenceStore` connection now configures a 30-second SQLite busy
  timeout.
- Discord timeouts, URL failures, HTTP 408/429 and HTTP 5xx are retryable only
  while fetching messages. HTTP 4xx configuration/authorization failures stay
  permanent.
- Continuous mode backs off exponentially to the configured ceiling and resets
  after success. One-shot mode returns temporary-failure status 75 without
  retry.
- A real isolated poll read 13 messages from the configured Discord channel and
  accepted, guided and dispatched zero messages; the operational database was
  not used.
- The complete quality gate passed 321 tests, 86% coverage, Ruff, mypy,
  compileall, shell syntax, package build and diff checks.
- The same 321 tests passed on Python 3.10, 3.11 and 3.12.
- The clean release gate verified source commit
  `3725479aa57b961206386c351d8affb5ad156cb9` and the 0.10.1 wheel with
  SHA-256 `07c224591c1a34ab9f26ff925687f27c04346c5cf5242f478ffc2d2ba12f12c8`.

## Authorized Upgrade Evidence

- The transactional updater completed the 0.10.0 to 0.10.1 upgrade and kept
  the matching 0.10.0 rollback wheel in its private backup.
- The private manifest is mode `0600`, reports `completed`, and records the
  expected target and rollback hashes.
- The installed CLI reports 0.10.1; schema 1 remains current with SQLite
  integrity `ok`.
- The main monitor and the recreated tray session are active.
- A post-upgrade isolated poll read 13 Discord messages and accepted, guided
  and dispatched zero messages. It used a temporary database and did not
  consume an operational question.
- Strict doctor reports only the intentionally unrestarted reply observer as
  failed. Its reset and first live start remain a separate operational
  authorization boundary.

## Phase 3 - Authorized Live Recovery

1. Inspect pending-question counts again.
2. Apply the exact patch wheel through the transactional updater after explicit
   authorization at that boundary.
3. Reset the failed systemd state and start the observer exactly once.
4. Observe multiple successful polls, service state, database health and
   sanitized doctor output.
5. Stop on any uncertain answer dispatch; do not replay it.

## Live Recovery Evidence

- Immediately before restart, the operational database contained zero pending
  questions: two were delivery-confirmed and three were expired.
- After explicit one-invocation authorization, the failed state was reset and
  the observer was started exactly once at `2026-10-09 06:46:00 -03`.
- Nine consecutive polls completed over approximately 45 seconds with zero
  accepted answers, deliveries, guidance messages or failures.
- The observer remained on one PID with `NRestarts=0` and
  `ActiveState=active`.
- Post-recovery strict doctor reports every check `ok`; schema 1 remains
  current with SQLite integrity `ok` and the operational database still has
  zero pending questions.
- No uncertain answer dispatch occurred, so no replay or manual recovery was
  attempted.

## Phase 4 - Hosted CI

The repository cannot repair an account-level billing lock. The owner must
clear that lock in GitHub billing or obtain GitHub Support assistance. After
GitHub accepts jobs again, dispatch one Quality run and require all supported
Linux matrix jobs to execute steps and pass. Windows remains experimental and
non-blocking. The owner cannot clear the lock in the current session, so this
external gate is explicitly deferred rather than represented as passing.

The `develop` promotion triggered hosted run
[`37913742672`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/37913742672)
for commit `a21aa85be2a3e4065950bbef29a2cd734de8b81f`. All three Linux jobs
finished with zero executed steps. Each check annotation states that the job
was not started because the account is locked due to a billing issue. This run
is evidence of the external block, not a passing CI gate.

## Completion

Record the source commit, package hash, transaction manifest, service evidence,
CI run URL and exact remaining limitations. Promote to `develop` only after the
software gates pass, and to `main` only after live observer recovery and hosted
Linux CI both pass or a new explicitly scoped release decision documents any
external blocker.
