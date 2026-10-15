# Task 040 - Prompt-rule Codex usage gate

## Goal

Add an optional second condition to each per-worker prompt rule so native Codex
input is dispatched only when both its primary timing/red-inactivity trigger
and fresh Codex usage availability are satisfied.

## Contract

The tray exposes **Require available Codex usage** for explicit project or
agent profiles. Existing and new rules default to unchecked. Enabling or
changing the checkbox is a configuration change and starts a clean rule cycle.

After the primary rule becomes due, the scheduler accepts only sanitized
`usage_available` account-limit evidence that:

- belongs to the same worker and exact Codex session;
- is still valid according to its configured TTL;
- was observed at or after the rule's due time.

This is the aggregate ordinary-usage decision reported by Codex. It avoids
hard-coding plan names or assuming that every account has both a five-hour and
weekly window. No balance, percentage, account identifier or raw rate-limit
payload is persisted in rule controls.

Missing, expired, unknown or blocked evidence yields `waiting_for_usage`. The
rule remains enabled with its due time and occurrence count unchanged. No
transport is claimed, no input is sent and no retry state is created.

## Producer boundary

The scheduler consumes evidence but never polls the Codex App Server itself.
The existing bounded observer must run for the exact active worker and session:

```bash
ai-presence observe-codex-limits \
  --project /absolute/project/path \
  --session EXACT_SESSION \
  --watch
```

This separation keeps potentially blocking account reads outside the tray UI
and preserves the existing read-only observer allowlist.

## Validation

1. Prove legacy controls load with the condition disabled.
2. Prove condition changes rearm a rule and disabling preserves the field.
3. Prove missing and blocked evidence do not dispatch or consume occurrences.
4. Prove stale, foreign-worker and foreign-session evidence cannot authorize
   input.
5. Prove fresh exact-scope `usage_available` evidence permits one dispatch.
6. Run the full quality gate, supported Python matrix and clean release gate.

## Release boundary

Validated code may advance to `develop`. Installing 0.10.6 or promoting it to
`main` remains a separate transactional release decision and is not authorized
by this implementation task.

## Local validation

- focused control, prompt-rule and tray tests passed;
- the full gate passed 335 tests with 86% coverage, Ruff, mypy, shell syntax,
  package build and diff checks;
- the same 335 tests passed on Python 3.10, 3.11 and 3.12;
- a live read-only dry-run against Codex CLI 0.160.0 returned
  `usage_available` without persisting evidence. The initial 10-second
  initialization timed out; one bounded pre-processing read with a 30-second
  timeout succeeded, and no further retry was made.
