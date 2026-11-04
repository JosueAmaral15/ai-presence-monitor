# Task 058 - Independent Codex Quota Recovery Observer

## Goal

Add a profile-scoped, opt-in recovery section that can notify one exact Codex
session when either the five-hour or weekly usage window becomes available
again. This feature is separate from Prompt Rules and does not change their
timers, red-inactivity gates or repetition semantics.

## State model

Each window has an independent enabled flag, message and durable state:

- `armed`: enabled, but no exhaustion has been observed;
- `waiting_for_availability`: authoritative sanitized evidence reached 100%;
- `dispatching`: the transition was claimed before transport;
- `dispatch_started` or `input_emitted`: one attempt was made for this cycle;
- `failed_or_uncertain`: the attempt is not retried automatically;
- `disabled`: the user disabled the rule.

Only `waiting_for_availability -> available` can dispatch. An initially
available, missing, stale or unrecognized window cannot dispatch. A later
exhaustion rearms the same enabled rule for a new cycle.

## Window identification

Use the sanitized `windowDurationMins`, `usedPercent` and `resetsAt` fields from
the Codex App Server. Match the five-hour and weekly windows by duration, not by
assuming primary/secondary ordering. Unknown or changed durations fail closed
and remain observable in status output.

## Authorization and transport

The human enables each rule in the tray for a project/agent profile and selects
an exact session. Dispatch still requires task automation and native input for
that profile. The observer uses native `codex queue`; it does not use mouse or
keyboard fallback, does not retry an uncertain attempt and does not synthesize
presence activity. A later hook remains the evidence that the session acted.

## Plan

1. Add backward-compatible persisted quota recovery settings to `control.json`.
2. Add a separate **Usage recovery** section to the tray preferences.
3. Implement deterministic per-window classification and transition handling.
4. Extend the durable observer service to poll when either recovery rule or a
   due usage-gated Prompt Rule needs evidence.
5. Add CLI status and one-cycle validation output without raw account payloads.
6. Cover two-profile isolation, restart, no-initial-dispatch, one dispatch per
   exhaustion cycle, uncertain transport and unchanged Prompt Rules.
7. Run an isolated exact-session E2E with a unique marker before release.

## Rollback

Disable both recovery checkboxes. Existing Prompt Rules, conversation history,
Discord integration and account evidence remain unchanged. Older control files
load with both recovery rules disabled.
