# Task 028 - Profiled Controls and Red-Inactivity Gate

## Objective

Extend the scheduled one-shot prompt with an optional red-inactivity gate and
persist the complete tray configuration independently for each worker. A
project-scoped worker therefore keeps settings that are distinct from another
project-scoped worker on the same computer.

Target version: `0.10.0` (still unreleased).

## Behavioral Contract

- Every saved profile is keyed by the exact bounded `worker_id` already used by
  the presence database.
- A missing profile inherits global preferences and permissions without
  creating a file, but never inherits an armed attempt, exact session, due time
  or schedule identifier.
- Saving one profile preserves the global settings and every other profile.
- The tray exposes the selected profile and only offers Codex sessions observed
  for that worker.
- The red-inactivity checkbox is disabled by default.
- Without the checkbox, the existing one-shot delay behavior is unchanged.
- With the checkbox, dispatch requires both the configured due time and red
  inactivity for the selected active worker.
- Protocol 1 uses `last_signal_at` and its 30-minute red threshold. Protocol 2
  uses `last_activity_at` and its 15-minute red threshold.
- A missing, idle, unsupported or not-yet-red worker cannot dispatch input.
- A successful eligibility check still claims and disarms the schedule before
  transport. Failure and uncertainty are never retried automatically.
- No automated test emits real Codex input.

## Compatibility Strategy

The control document keeps schema version 1 and the existing top-level
`settings` object. An additive `profiles` object stores full settings per
worker. Older 0.9/0.10 code continues to read the global object and ignores the
new object. New code accepts documents without `profiles` and preserves their
behavior.

## Phases

1. Add profile-aware atomic reads and writes to `ControlStore`.
2. Add the red-gate field and protocol eligibility evaluation to the scheduler.
3. Make worker-aware CLI paths load the matching profile.
4. Add profile selection, filtered sessions and the checkbox to the tray.
5. Update requirements, architecture, decisions, security and operator guides.
6. Run focused tests, the full coverage gate, lint, type checks and builds.

## Security Gates

- Profile identifiers are bounded, single-line values and are never shell
  fragments or filesystem paths.
- Red eligibility reads only persisted worker state and the canonical protocol
  thresholds; it does not infer activity from a timer or notification state.
- The selected exact Codex session remains mandatory.
- Native input remains mandatory and GUI/remote fallback is not introduced.
- Prompt text remains redacted from control status output.
- The control file remains private, atomic and outside the repository.

## Rollback

Stop the tray and reinstall the previous verified wheel through the
transactional upgrade procedure. The previous runtime ignores `profiles` and
continues using top-level `settings`. Do not delete the control file; profile
state can remain as inert additive data until this version is restored.

## Validation

- Store tests cover legacy input, profile inheritance, profile isolation and
  preservation during global writes.
- Scheduler tests cover Protocol 1 and 2 clocks, due-before-red waiting, idle
  workers, unsupported protocols, one dispatch and no retry.
- CLI tests cover explicit profile selection and project-derived continuation.
- Tray helpers are tested independently from optional Qt where possible.
- Full suite must retain the repository coverage threshold and pass on the
  supported Python matrix before promotion.

## Results

- Focused affected suite: 63 tests and 20 subtests passed.
- Full suite: 306 tests and 54 subtests passed with 86.25% total coverage.
- Python 3.10, 3.11 and 3.12 matrix: 306 tests passed on each runtime.
- Ruff, mypy, compileall, shell syntax, wheel and sdist build passed.
- Source-runtime tray smoke confirmed the graphical system tray is available.
- No schedule was armed and no real Codex input was emitted during validation.
- The implementation is eligible for `develop`. Promotion of unreleased 0.10.0
  to `main` remains gated by one explicitly authorized real scheduled-prompt E2E
  with a unique marker and later exact-session hook evidence.
