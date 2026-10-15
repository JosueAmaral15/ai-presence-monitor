# Task 041 - Desktop Event Notifications

## Goal

Add an opt-in, persistent system-tray control that reports trustworthy local
events without replaying history or overstating preliminary transport states.

## Scope

1. Store one global boolean in `control.json`, defaulting to disabled.
2. Place the checkable action above **Respond to message...**.
3. Consume immutable lifecycle and Codex hook events, inactivity alerts and
   Discord question-state transitions from SQLite.
4. Route prompt-rule dispatch and failure notices through the same master gate.
5. Persist cursors in the existing `observer_state` table.
6. Bound visible bursts and exclude prompt, question and answer content.

## Evidence Contract

- `start` and `finish` are worker lifecycle claims.
- `observation:codex:Stop` is a Codex turn-end hook, not response content.
- `dispatch_started` means a detached process started.
- `input_emitted` means a synchronous transport completed.
- `delivery_confirmed` means a later matching session hook was observed; it
  does not prove semantic interpretation.

No generic window scraping or notification interception is added. A future
platform adapter must persist a bounded, typed event before the tray can report
it.

## Validation

- focused observer, control and tray tests;
- full quality and coverage gate;
- Python 3.10, 3.11 and 3.12 matrix;
- clean 0.10.7 release build and isolated installation check.

## Promotion Boundary

Validated work may be pushed and promoted to `develop`. Installing the new
runtime or promoting `develop` to `main` requires a separate explicit decision.

## Validation Evidence

- full quality gate: 342 tests, 86% aggregate coverage, Ruff, mypy, shell
  syntax, wheel and sdist build passed;
- Python matrix: the same 342 tests passed on 3.10, 3.11 and 3.12;
- Linux Mint graphical preflight: `tray --check` reported an available system
  tray without starting a persistent icon or mutating controls.
