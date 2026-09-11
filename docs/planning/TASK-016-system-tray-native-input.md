# Task 016 - System Tray and Native Codex Input

## Objective

Provide a system tray controller and a direct Codex input transport that does
not take over the user's mouse or keyboard.

## Scope

- Persist explicit local permissions for task automation and input transports.
- Send text to one exact Codex session through `codex queue`.
- Keep X11 and Win32 input as an explicit, disabled-by-default fallback.
- Expose the same controls through CLI commands and an optional PySide6 tray.
- Allow the tray message composer to target the local Codex instance or a
  configured authenticated remote app-server endpoint.
- Preserve presence synchronization only after an input command reports
  success, with a later Codex hook remaining the processing confirmation.

## Safety Rules

- Enabling task automation is authorization, not a periodic scheduler.
- An AI worker may request `continue` only for a concrete active task and must
  not use timer-only messages to simulate work.
- A transport failure has an uncertain delivery result and must not trigger an
  automatic retry through another transport.
- Thread identity must be explicit or inferred from a hook for the same worker.
- Remote endpoints never store token values; configuration contains only the
  environment-variable name holding the token.
- GUI fallback remains opt-in and keeps exact-window revalidation.

## Acceptance Criteria

- [x] `codex queue` is invoked without `shell=True`, mouse, keyboard, or
      clipboard access.
- [x] The `continue` command supports `auto`, `native`, and `gui` transports.
- [x] Runtime control state is stored atomically outside the repository.
- [x] CLI can inspect and change every tray permission and Codex target.
- [x] Tray menu contains Enable task automation, Respond to message, and Exit.
- [x] Tray preferences expose native input, GUI fallback, remote replies, and
      presence synchronization controls.
- [x] Local and remote native message delivery are available from the tray.
- [x] Base CLI installation does not require a GUI toolkit.
- [x] Tests, coverage, lint, types, build, documentation, and package install
      checks pass.
- [x] Functional work is committed on the task branch and promoted to
      `develop`; `main` remains subject to the complete release gate.

## Validation Plan

1. Unit-test subprocess arguments, policy persistence, transport selection,
   worker/session correlation, and failure handling.
2. Run the full test suite with coverage, Ruff, mypy, and build checks.
3. Install the wheel in an isolated virtual environment and verify entry
   points.
4. Run a tray availability smoke test without sending input.
5. Perform a real local `codex queue` test only with separate explicit user
   authorization for the message and target session.

## Validation Result

- Task commit: `6f6b500` on `codex/tray-native-input-20260911`.
- Functional merge: local `develop` branch.
- Automated suite: 146 tests passed.
- Total coverage: 86%, above the 80% gate.
- Ruff, mypy, source compilation, `git diff --check`, sdist, and wheel passed.
- The 0.6.0 wheel was installed in an isolated environment and both CLI entry
  points were loaded without installing the optional GUI dependency.
- System tray availability and real Qt construction passed on the current
  Linux desktop; the construction smoke was terminated after three seconds.
- Native `continue` dry-run passed without creating state or emitting input.

## External Validation Remaining

A real `codex queue` message has not been sent in this task because it requires
separate explicit authorization for the exact message and destination session.
This does not block `develop`, but it remains a release gate for promotion to
`main`. The external Windows CI gate recorded by Task 012 also remains open.
