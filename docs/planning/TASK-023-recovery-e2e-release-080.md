# Task 023 - Recovery E2E and Private Linux 0.8.0 Release

## Goal

Validate one real diagnostic recovery dispatch to the exact current Codex
session, package the completed Task 022 work as version 0.8.0, and promote the
validated private Linux release through `develop` and `main`.

## Authorization

On 2026-09-20, the user authorized:

- one isolated real recovery E2E with a unique marker;
- one diagnostic Discord notification required by the recovery policy;
- one local native dispatch to the current exact Codex session;
- use of `proceed` for human messages so the marker is not typed manually;
- version 0.8.0 and deferral of the shared-endpoint live adapter;
- a documented private Linux CI exception if hosted CI remains unavailable;
- push of `develop`, followed by merge and push of `main` only after all gates.

The authorization does not permit retry after uncertain delivery, GUI input,
remote input, alarm, Telegram fallback, production-database mutation, or a
second recovery dispatch.

## Phase 1 - Isolated Recovery E2E

1. Generate one marker in the form
   `[AI-PRESENCE-RECOVERY-E2E:<uuid>] continue`.
2. Create a temporary SQLite database outside the repository.
3. Create one isolated active worker, exact-session `codex_closed` diagnosis
   with medium confidence, and one open yellow incident.
4. Run the diagnostic notification dry-run and prove zero attempt rows.
5. Send one real Discord diagnostic notification and require `delivered`.
6. Ask the human to confirm exactly one marker in Discord.
7. Run recovery dry-run and prove zero recovery rows.
8. Invoke one real `recover-diagnostic-incident --authorize-once` with the
   marker as `PRESENCE_CONTINUE_MESSAGE`.
9. Stop the turn after `dispatch_started` or `input_emitted`; do not retry.
10. Require the automatically queued marker in this exact Codex session and a
    later same-session hook before declaring delivery confirmed.
11. Verify one recovery row, unchanged presence activity clock, and no second
    dispatch. Remove the temporary directory after sanitized evidence is saved.

Stop immediately on `rejected`, `uncertain`, an unexpected exception, a
session mismatch, more than one Discord message, or any ambiguous queue state.
Preserve the isolated database for diagnosis in that case and keep `main`
unchanged.

## Phase 2 - Release Candidate

- update `pyproject.toml` and package `__version__` to 0.8.0;
- convert the Task 022 changelog entry into a 0.8.0 release entry;
- document the E2E evidence and defer the shared-endpoint adapter explicitly;
- update requirements, decisions, security, tasks, index and rollback notes;
- run compilation, 271+ tests, coverage, Ruff, mypy and diff checks;
- run tests on Python 3.10, 3.11 and 3.12;
- build wheel and sdist from the final release commit;
- install the wheel in a fresh isolated virtual environment;
- smoke-test installed CLI help, database initialization, Linux runtime guard,
  diagnostic recovery dry-run, hooks and user services;
- confirm `.env`, tokens, webhooks, databases and temporary E2E files are not
  staged or packaged.

## Sanitized E2E Evidence

Completed on 2026-09-20:

- marker:
  `[AI-PRESENCE-RECOVERY-E2E:d0f7c884-428c-49bd-a903-0989a5616a10] continue`;
- exact target session: `019f5691-c118-7370-a205-94cfde0a93d7`;
- isolated cause: `codex_closed`, medium confidence, yellow severity;
- notification dry-run: `would_send`, zero notification/recovery rows;
- real Discord result: `delivered`, one notification row;
- the user confirmed exactly one matching Discord message;
- recovery dry-run: `would_dispatch`, zero recovery rows;
- real recovery result: `dispatch_started`, one recovery row;
- the exact marker arrived automatically in the target Codex session and was
  not typed by the user;
- later hooks from the same session included `UserPromptSubmit`;
- the isolated worker `last_activity_at` remained exactly unchanged;
- GUI and remote input were disabled, and no retry, fallback, alarm, Telegram,
  production-database mutation or second dispatch occurred.

## Phase 3 - Integration and Publication

1. Commit the E2E and release evidence on the task branch.
2. Merge the validated task branch into `develop` and rerun focused checks.
3. Push `develop`.
4. Inspect hosted Linux CI. If it remains billing-blocked, record a new narrow
   private Linux 0.8.0 exception based on the local matrix and isolated install.
5. Merge `develop` into `main` with preserved history.
6. Rerun the final smoke check, push `main`, and verify both remote heads.
7. Finish the AI-worker once.

## Release Candidate Evidence

Validated on 2026-09-20 from the task branch:

- 271 tests passed on Python 3.10, 3.11 and 3.12;
- the complete Python 3.12 gate passed at 88% total coverage;
- Ruff, mypy, compilation and `git diff --check` passed;
- wheel and sdist built as version 0.8.0;
- the wheel installed with no dependencies in a fresh temporary virtual
  environment;
- the installed package reported 0.8.0, initialized an isolated database,
  returned `no_open_incident` from recovery dry-run, processed a hook dry-run
  and rendered the Linux monitor service without writing the real unit;
- wheel and sdist contain no `.env`, SQLite database or control-state file;
- the Git diff contains no recognized Discord webhook, Telegram token or
  secret assignment, and Git tracks no `.env` or SQLite database;
- both existing user services remained `active/running` with successful main
  process status and unchanged restart counters during the smoke interval;
- the isolated install directory and the isolated E2E database were removed.

## Deferred Scope

The shared-endpoint live App Server adapter remains disabled and moves to a
separate task. The current child-process probe cannot observe an already
GUI-owned session, and changing session hosting is not required for the
private Linux 0.8.0 release. Windows remains preserved, experimental,
default-disabled, and non-blocking.

## Hosted CI Result

Push of `develop` commit `6e8c1c3` created Quality run `35514873721`. The
Python 3.10, 3.11 and 3.12 Ubuntu jobs each failed before executing any step.
GitHub reported `account is locked due to a billing issue`; Windows remained
the expected manual/skipped experimental job. The user had explicitly
authorized a narrow private Linux 0.8.0 exception if this external condition
persisted. `docs/DECISIONS.md` records that exception and does not classify the
hosted run as passed.

## Rollback

- Before publication: delete the temporary E2E directory and return to
  `develop`; no production data requires rollback.
- After the task commit but before merge: revert the task commit or delete the
  task branch.
- After `develop` merge but before `main`: revert the merge on `develop`.
- After `main` publication: revert the release merge on both branches, rebuild
  the previous 0.7.0 wheel, reinstall it in the private runtime, and restart
  only the affected user services.

## Checklist

- [x] Discord diagnostic marker confirmed once by the user.
- [x] One recovery dispatch reaches the exact current session.
- [x] Later same-session hook confirms post-dispatch activity.
- [x] No retry, GUI fallback, remote input or presence synchronization occurs.
- [x] Version 0.8.0 and documentation are complete.
- [x] Full local, matrix, package and isolated-install gates pass.
- [x] Private Linux CI decision is recorded for blocked run `35514873721`.
- [x] Task commit `063287e` is merged locally into `develop`.
- [x] Validated `develop` commit `6e8c1c3` is pushed to its remote branch.
- [x] Validated `develop` is merged locally into `main`.
- [ ] Release 0.8.0 `main` is pushed and remote heads are verified.
- [ ] AI-worker is finished exactly once.
