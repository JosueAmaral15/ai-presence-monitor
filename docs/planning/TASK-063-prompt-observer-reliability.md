# Task 063 - Prompt Observer Reliability and Explicit Token Recovery

## Problem

An enabled red-inactivity Prompt Rule can remain in `waiting_for_event` when
the tray is closed or the worker has been finished. The current architecture
splits ownership: the tray processes ordinary rules while the background
observer processes only usage-gated rules. In addition, red timing currently
requires an active worker, so an explicitly armed continuation cannot progress
after a real `finish` event even though the last activity clock is known.

The independent quota-recovery implementation exists, but its **Usage
recovery** label and shared service name do not make the token-availability
observer sufficiently explicit to operators.

## Plan

1. Make the background automation observer the sole owner of every modern
   Prompt Rule; the tray will edit and display rules but will not dispatch them.
2. Process non-usage rules on a local timer without reading the Codex account.
3. Keep account reads on their separate, slower interval and share one
   sanitized snapshot between due usage-gated rules and token recovery.
4. For an explicitly armed red rule, calculate the protocol red-duration point
   from the last real monitored clock even after the worker becomes idle.
   `finish` remains a real activity event and therefore restarts that clock.
5. Rename the explicit GUI section to **Token recovery**, retaining independent
   five-hour and weekly checkboxes, exact sessions and messages.
6. Expose only sanitized token-recovery counts and states through CLI status.
7. Add deterministic tests for a 271-minute post-red delay, closed tray, idle
   worker, account-read cadence, one-shot dispatch and existing no-retry rules.
8. Run focused tests, the full quality gate and an installed-runtime dry-run
   before requesting authorization for any real prompt delivery.

## Required Semantics

- Protocol 2 reaches the red-duration point 15 minutes after its last real
  activity; Protocol 1 uses its existing 30-minute red duration.
- A delay of 271 minutes with a red trigger becomes due 271 minutes after that
  red-duration point, not 271 minutes after saving the rule.
- Activity before the first dispatch rearms the red wait from the new activity.
- Token recovery sends only after the selected window was observed exhausted
  and then available. Initial availability must never dispatch.
- Prompt Rules and Token Recovery remain independent features.
- Dispatch claim, failure, uncertainty and exact-session evidence rules remain
  unchanged; no automatic retry or GUI fallback is added.

## External Validation Boundary

A real token-recovery E2E still requires a naturally exhausted five-hour or
weekly Codex window that later becomes available. Tests must not consume tokens
deliberately. A real prompt-rule transport requires a unique marker and
explicit authorization for that isolated invocation.

## Validation Record

Local validation completed on 2026-11-12:

- 389 tests passed with 86% aggregate coverage;
- Ruff, mypy across 52 source files, shell syntax, wheel/sdist build and
  `git diff --check` passed;
- the deterministic Protocol 2 scenario reached red after 15 minutes, waited
  another 271 minutes and dispatched exactly once after the worker finished;
- local observer cycles did not read the Codex account, while due token-gated
  work shared the slower account snapshot;
- the `0.13.1` wheel installed in an isolated environment, reported the
  expected version and passed `tray --check`;
- the installed `0.13.0` runtime accepted the candidate and canonical rollback
  packages in transactional `--dry-run`, reporting `would_upgrade`.

No real runtime upgrade, service restart, prompt transport or quota transition
was performed as part of this validation.
