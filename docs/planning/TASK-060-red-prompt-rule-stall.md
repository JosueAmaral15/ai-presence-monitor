# Task 060 - Red Prompt Rule Stall

## Reported Symptom

After configuring a Prompt Rule and observing red inactivity, the tray kept
showing:

```text
Waiting for canonical red inactivity, then the configured delay.
```

The status did not advance to a concrete due time.

## Investigation Plan

1. Inspect sanitized persisted state for the affected profile: worker status,
   protocol, monitored clock, red threshold, rule trigger, `armed_at`,
   `next_due_at` and scheduler ownership. Do not expose prompt text, session ID
   or environment secrets.
2. Reproduce the exact state transition with deterministic clocks for Protocol
   1 and Protocol 2.
3. Verify whether the tray is the only scheduler for non-usage-gated rules and
   whether the background observer ignores a red rule while `next_due_at` is
   still unset.
4. Keep one owner per rule class: the tray for rules without a usage gate and
   the continuous observer for every phase of usage-gated rules. Collect Codex
   usage only when a due rule requires it.
5. Keep canonical-red semantics: active worker, protocol-specific monitored
   clock, red threshold, event not older than the rule's arm time, configured
   delay after that event and exact profile/session isolation.
6. Add regression coverage for tray closed, service restart, worker lifecycle,
   token-gated and non-token-gated rules, and uncertain dispatch.
7. Run local quality, release and remote CI gates. Use a unique-marker E2E only
   after deterministic tests pass and explicit one-invocation authorization is
   available.

## Constraints

- Do not synthesize presence or a red event.
- Do not infer usage availability from inactivity.
- Do not resend an uncertain input.
- Do not expose rule text, Codex session IDs, tokens or webhook configuration.
- Do not let one profile advance or mutate another profile's rule.

## Root Cause

The tray intentionally skipped usage-gated rules, while the continuous
observer selected them only after `next_due_at` was already populated. A
usage-gated `red_inactivity` rule starts with `next_due_at` unset, so neither
scheduler owned the transition from canonical red inactivity to the configured
post-red delay.

## Implemented Resolution

- The continuous observer now processes every enabled usage-gated rule before
  selecting due account-dependent work.
- This preliminary pass evaluates canonical red inactivity and persists the
  due time without reading Codex account usage.
- Account usage is collected only after at least one rule or quota-recovery
  target is due.
- Non-usage-gated rules remain exclusively tray-owned.
- Existing claim-before-dispatch and uncertain-delivery handling are
  unchanged.

## Validation

- Protocol 1 advances at its 30-minute canonical red threshold.
- Protocol 2 advances at its 15-minute canonical red threshold.
- The configured delay begins at the canonical red event, not at observer
  startup or rule creation.
- No account read occurs before the post-red delay is due.
- A due rule reads account usage once and dispatches once.
- A non-usage rule remains untouched by the continuous observer.
- The full local quality gate passed with 386 tests and 86% coverage, Ruff,
  mypy, shell syntax validation, wheel/sdist build and `git diff --check`.

## Remaining Release Evidence

Install the candidate runtime transactionally, restart the observer and run an
isolated unique-marker E2E for the exact configured profile. This external
input operation requires explicit one-invocation authorization and must not be
inferred from a persistent automation setting.
