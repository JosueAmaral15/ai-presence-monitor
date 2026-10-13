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
