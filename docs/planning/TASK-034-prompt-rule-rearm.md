# Task 034 - Prompt Rule Rearming

## Objective

Make a disabled or edited prompt rule start a genuinely new countdown while an
unchanged save preserves the existing deadline. Adopt 270 minutes as the single
shared default used by the model and tray.

## Observed Failure

The affected `books` profile persisted the edited 270-minute delay, but its
red-inactivity rule ended disabled in `failed_or_uncertain`. The scheduler used
the canonical red timestamp as the delay baseline even when that red episode
predated the user's new arm action. A sufficiently old episode could therefore
make a re-enabled or edited rule immediately due.

## Contract

- Disabling and later enabling a rule starts a new cycle.
- Any change to session, trigger, delay, text, repetition, repeat interval or
  occurrence limit starts a new cycle.
- A new cycle keeps the stable rule ID but clears occurrence count, attempt and
  dispatch timestamps, confirmation wait and previous due time.
- Saving the exact same configuration returns the existing runtime state and
  does not postpone its deadline.
- A red rule armed during an existing red episode starts its additional delay
  at the new arm time.
- Valid worker activity before the initial dispatch cancels the pending red
  deadline; the rule waits for the next canonical red threshold.
- Repeating behavior after a confirmed exact-session hook remains unchanged.

## Compatibility And Safety

`armed_at` is additive in the existing version-1 control document. Older rules
without it remain readable and retain their persisted state. Dispatch remains
claim-before-send, native-only, one-attempt and fail-closed. The change does not
add retry, GUI fallback, activity synchronization or cross-profile mutation.

## Validation

- focused control, scheduler and tray tests;
- complete quality gate with coverage, Ruff, mypy, compileall, shell syntax and
  package build;
- Python 3.10, 3.11 and 3.12 matrix;
- clean diff and exact source-version agreement.

No automated test may emit real Codex input. Installing the resulting runtime
or re-enabling the user's operational rule remains a separate authorized action.

## Validation Result

The implementation passed 325 tests with 86% aggregate coverage, Ruff, mypy,
compileall, shell syntax, package build and `git diff --check`. The same 325
tests passed on Python 3.10, 3.11 and 3.12. Focused control, scheduler, tray and
release-tooling validation passed 42 tests. No test used the operational
control document or emitted real Codex input.

The clean-tree release gate also passed for version 0.10.3 at commit
`e86c5ba425f606f64a2699c5dddbb21b554cd9e0`. Its manifest records
`source_dirty=false` and verifies the wheel, source archive, `.env.example`,
Linux installer, upgrader and release-verification tooling. Operational
installation, tray restart, rule re-enablement and exact-session input remain
outside this code-validation run.

The task branch and `develop` were pushed after the gate passed. Promotion to
`main` remains intentionally pending until runtime 0.10.3 is installed and an
isolated operational E2E confirms the rearmed countdown without sending an
unintended prompt to another session.

## Operational Result - 2026-10-13

The transactional dry-run reported `would_upgrade` from 0.10.2 to 0.10.3. The
single authorized transaction then completed, retained a private rollback
manifest and restored both managed services. The installed command reports
0.10.3, schema 1 remains current and integral, strict doctor reports every
check `ok`, and the tray was restarted as one process on the new runtime.

The authorized E2E used temporary control and SQLite files, the exact current
Codex session and marker
`[AI-PRESENCE-PROMPT-REARM-E2E:b18bda42-bee8-4cc0-8252-6dcb1687fc29] continue`.
It did not modify the operational `books` rule.

The isolated scheduler established these states:

- re-enabling the 210-minute rule armed it at `3000` and set due time `15600`;
- editing the delay to 270 minutes rearmed at `4000` and moved due time to
  `20200`, rather than retaining the old red episode or prior deadline;
- the poll at `20199` remained `waiting`;
- the due poll returned `dispatch_started` exactly once;
- the one-shot rule was disabled with occurrence count `1`;
- the next poll returned `disabled` and emitted no second input.

The exact marker then appeared as user input without being typed by the human.
The operational database recorded `observation:codex:UserPromptSubmit` for the
same session at `1791922444.6423137` and subsequent same-session hooks. No GUI,
remote endpoint, Discord, alarm, fallback, retry or activity synchronization
participated in the dispatch.

The hosted Quality run
[`38460625672`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/38460625672)
created all three required Linux jobs but ran zero steps. GitHub annotated each
job with the unchanged account-level billing lock. This is external non-pass
evidence, not successful CI; the version-specific private Linux exception is
recorded in `docs/DECISIONS.md`.

## Promotion Result

The task branch, `develop` and `main` were fast-forwarded and remotely verified
at evidence commit `e59fa693ccc415f5db91ff98f70c6dfe59475f19`. No tag,
GitHub release or public asset was created. Post-promotion Quality run
[`38461504848`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/38461504848)
again created the three Linux jobs, ran zero steps and reported the same billing
lock; it remains external non-pass evidence.

The first tray restart was launched from the terminating transient tray cgroup,
so that child ended with its parent unit. The tray was then restored as one
top-level `ai-presence-tray-session.service` transient user unit. Runtime
0.10.3, the monitor, reply observer and tray were all active after promotion.
