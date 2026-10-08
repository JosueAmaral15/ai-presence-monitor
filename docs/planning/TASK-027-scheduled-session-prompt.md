# Task 027 - Scheduled One-Shot Session Prompt

## Objective

Add an explicit tray option that schedules one native prompt for one exact
Codex session. The user controls whether it is enabled, the delay in minutes
and the text. Defaults are 210 minutes and `continue`.

Target version: `0.10.0` (not released by this task session).

## Contract

- Scheduling is disabled by default.
- Enabling captures the selected session, prompt and absolute due time.
- The dispatch is local and uses `codex queue`; it never uses GUI or remote
  fallback.
- The schedule is one-shot. It is disarmed and persisted before transport.
- `dispatch_started`, `input_emitted`, failure and uncertainty never trigger an
  automatic retry.
- A later hook remains the evidence that the target session processed input.
- Reopening preferences without changing the active schedule does not postpone
  its due time.
- Disabling the checkbox cancels the pending schedule but preserves the
  preferred delay and text for later use.

## Phases

1. Extend backward-compatible control state and validation.
2. Implement a Qt-independent scheduler/dispatcher with deterministic tests.
3. Add the checkbox, numeric field, text field and status to the tray dialog.
4. Poll the persisted due time with a lightweight Qt timer.
5. Update requirements, architecture, decisions, security and user guides.
6. Run focused tests, full coverage, Ruff, mypy and package checks.

## Security Gates

- Exact non-empty session is mandatory.
- Native input must remain enabled when arming and dispatching.
- Prompt is bounded, single-line and must not be empty.
- No shell, mouse, keyboard, clipboard, webhook or external retry is used.
- The control file remains atomic, private and outside the repository.
- Status output must not print the scheduled prompt text by default.

## Rollback

Stop the tray, disable the schedule in preferences and reinstall the previous
verified wheel through the transactional upgrade procedure. Older releases
ignore additive keys in `control.json`; removing only the new schedule keys is
optional and must not remove the whole control file unless all controls should
return to `.env` defaults.

## Validation

- Unit tests cover defaults, backward compatibility, validation, arming,
  cancellation, unchanged preferences, due dispatch and failure without retry.
- UI smoke verifies that the optional PySide import remains isolated.
- No live Codex input is sent by automated tests.

## Results

- Focused affected suite: 78 tests passed.
- Full suite: 299 tests passed with 86% total coverage.
- Python matrix: the same 299 tests passed on 3.10, 3.11 and 3.12.
- Ruff, mypy, compileall, shell syntax, wheel and sdist build passed.
- Source-runtime tray smoke confirmed the graphical system tray is available.
- No schedule was armed and no real Codex input was emitted during validation.
- Version 0.10.0 remains unreleased and is not installed in the dedicated
  operational environment by this task.
