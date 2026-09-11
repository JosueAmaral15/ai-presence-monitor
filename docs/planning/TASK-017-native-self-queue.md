# Task 017 - Non-blocking Native Input for the Current Codex Session

## Objective

Prevent a Codex worker from blocking its active turn when it queues input to
that same session, while preserving one-shot delivery and truthful presence
state.

## E2E Diagnosis

On 2026-09-11, the user explicitly authorized one local native message:

```text
message: continue
session: 019f5691-c118-7370-a205-94cfde0a93d7
destination: local
delay: 0
```

The synchronous `codex queue` process reached its 15-second timeout. It was not
retried. A `continue` message and subsequent `SessionStart`/`UserPromptSubmit`
hooks were initially attributed to that attempt. The user then clarified that
the visible message was typed manually. Those observations prove only manual
activity in the target session, not native queue delivery.

The result is therefore inconclusive. It does demonstrate that the synchronous
client did not complete within 15 seconds while targeting its calling session.
A same-session wait cycle is the working diagnosis, but successful queue
delivery must not be claimed without uniquely correlated evidence. A timeout
is uncertain and cannot be treated as either definitive success or failure.

## Design

- Compare the target with `CODEX_SESSION_ID` and `CODEX_THREAD_ID`.
- For the current session, spawn `codex queue` without a shell and return
  `dispatch_started` immediately.
- Isolate standard streams. POSIX starts a new session; Windows uses
  `CREATE_NO_WINDOW` and `CREATE_NEW_PROCESS_GROUP`.
- Keep synchronous execution for other sessions unless `--detach` is supplied.
- Allow `--no-detach` only as an explicit diagnostic override.
- Always detach tray dispatch so the Qt event loop cannot freeze.
- Never retry automatically after a timeout, rejected command, or uncertain
  detached result.

## Presence Semantics

`dispatch_started` proves only that the operating system created the Codex CLI
process. It does not prove acceptance or processing, so it must not create
`observation:automation:continue` or change `last_activity_at`.

A later Codex hook is session activity evidence and updates normal Protocol 2
activity. It does not identify the originating message by itself. This removes
the false-positive interval that would otherwise credit work before the target
session actually receives any input.

## Acceptance Criteria

- [ ] One authorized native E2E with a unique marker reaches the exact target
      once.
- [ ] The identifiable message and a later hook confirm processing in the same
      session.
- [x] The previous manual `continue` was removed from the native E2E evidence.
- [x] Current-session detection covers both Codex environment variables.
- [x] POSIX and Windows detached process policies are unit-tested.
- [x] Detached dispatch does not update presence state.
- [x] Tray dispatch is always non-blocking.
- [x] CLI supports automatic, forced, and explicitly synchronous modes.
- [x] Full quality gate, package build, and isolated installation pass.
- [x] Task branch is committed and merged locally into `develop`.

## Validation Result

- Full suite: 152 tests passed.
- Coverage: 86%, above the 80% project gate.
- Source compilation, Ruff, mypy, package build, and `git diff --check` passed.
- The `0.6.1` wheel installed in an isolated virtual environment.
- Installed `ai-presence continue --help` exposes `--detach` and
  `--no-detach`; the tray entrypoint loads without importing PySide6.
- An installed dry-run against the current exact session reported
  `destacado=true` without waiting, emitting input, or accessing SQLite.
- Task commit: `89992de` on `codex/native-input-e2e-20260911`.
- Local `develop` merge: `81e07fb`.

## Release Boundary

The previous authorization was consumed by the inconclusive attempt. No second
real message may be sent without new explicit authorization. The retest must
use a unique marker such as `[AI-PRESENCE-E2E:<id>] continue`; the human must
not type that marker, and manual continuation should use `prossiga` during the
test window.

Automated tests and dry-runs validate the implementation without proving a
real queue delivery. The E2E result requires all of the following:

1. one command invocation against one exact session;
2. one visible message containing the exact unique marker;
3. no manual use of that marker;
4. a later hook from the same session;
5. no retry after timeout or another uncertain result.

`main` promotion remains blocked by the external Windows CI gate documented in
Task 012. Local Linux validation does not replace that platform evidence.

## Rollback

Use `--no-detach` only from a process that is not the target Codex turn, or
disable native input:

```bash
ai-presence control disable native-input
```

No database migration or `.env` change is required.
