# Task 047 - Prompt Rule Missed-dispatch Investigation

## Incident

On 2026-11-02, a prompt rule was saved near 10:00 with a 52-minute delay, but
no prompt reached the selected Codex session by 13:03. The investigation must
distinguish configuration, scheduling, service availability, usage gating,
transport launch and later Codex confirmation instead of treating them as one
state.

## Read-only preflight

1. Identify the installed runtime and the dedicated prompt-rule observer state.
2. Inspect only sanitized rule metadata: profile, rule ID, enabled flag, trigger,
   delay, due time, last state/attempt, usage gate and occurrence counters.
3. Correlate user-service logs from 09:45 onward with the stored rule timestamps.
4. Check whether the tray or observer owned the rule and whether the rule was
   skipped because the worker was idle, the service was absent, usage evidence
   was unavailable or the exact session was not configured.

## Reproduction

Create an isolated HOME, database and control profile. Exercise the same
52-minute state by advancing the evaluation clock rather than waiting in real
time. Reproduce the observed state before changing production code.

## Correction

Apply the smallest change at the proven boundary. Preserve fail-closed usage
gating, one-shot claim-before-send behavior, exact-session targeting and no
automatic retry after an uncertain transport result. Add a regression test for
the real failure mode and update operational diagnostics so a future missed
dispatch has an explicit reason.

## Validation

- focused regression and observer tests;
- full quality gate and Python 3.10-3.12 matrix;
- isolated installed-wheel service cycle;
- one explicitly authorized exact-session E2E marker after upgrade;
- strict doctor and restart-count verification.

## Promotion

Commit the correction separately from the chat implementation. Promote to
`develop` only after local gates and installed-runtime validation. Promotion to
`main` still requires the real integrations and documented release decision.
