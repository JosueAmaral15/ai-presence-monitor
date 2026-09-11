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
retried. The message then appeared exactly once in the target task, and the
SQLite audit recorded `SessionStart` at `16:00:10` and `UserPromptSubmit` at
`16:00:11` for the same session.

The result demonstrates a same-session wait cycle: the caller waits for
`codex queue`, while the queued turn cannot be handled until the current turn
releases the session. A synchronous timeout is therefore uncertain and cannot
be treated as a definitive delivery failure.

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

The later Codex hook is the first processing evidence and updates normal
Protocol 2 activity. This removes the false-positive interval that would
otherwise credit work before the target session actually receives the input.

## Acceptance Criteria

- [x] One authorized native E2E reaches the exact target once.
- [x] A later hook confirms activity in the same session.
- [x] Current-session detection covers both Codex environment variables.
- [x] POSIX and Windows detached process policies are unit-tested.
- [x] Detached dispatch does not update presence state.
- [x] Tray dispatch is always non-blocking.
- [x] CLI supports automatic, forced, and explicitly synchronous modes.
- [x] Full quality gate, package build, and isolated installation pass.
- [ ] Task branch is committed and merged locally into `develop`.

## Validation Result

- Full suite: 152 tests passed.
- Coverage: 86%, above the 80% project gate.
- Source compilation, Ruff, mypy, package build, and `git diff --check` passed.
- The `0.6.1` wheel installed in an isolated virtual environment.
- Installed `ai-presence continue --help` exposes `--detach` and
  `--no-detach`; the tray entrypoint loads without importing PySide6.
- An installed dry-run against the current exact session reported
  `destacado=true` without waiting, emitting input, or accessing SQLite.

## Release Boundary

The authorized E2E has been consumed. No second real message may be sent
without new explicit authorization. Automated tests and dry-runs validate this
fix without producing another input.

`main` promotion remains blocked by the external Windows CI gate documented in
Task 012. Local Linux validation does not replace that platform evidence.

## Rollback

Use `--no-detach` only from a process that is not the target Codex turn, or
disable native input:

```bash
ai-presence control disable native-input
```

No database migration or `.env` change is required.
