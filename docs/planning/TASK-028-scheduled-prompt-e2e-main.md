# Task 028 - Scheduled Prompt E2E and Main Promotion

## Objective

Prove one real 0.10.0 prompt-rule dispatch to the current exact Codex session
before promoting the already validated `develop` candidate to `main`.

## Authorization Boundary

The real step emits Codex input. It requires explicit authorization for one
invocation immediately before dispatch. General permission to commit, push or
continue development is not reused as input authorization.

## Isolated E2E Contract

1. Generate a unique marker immediately before the run.
2. Use the source 0.10.0 rule scheduler with a temporary `control.json` and SQLite
   database; do not alter installed 0.9.0 controls or presence data.
3. Create one active Protocol 2 worker in the temporary database with a known
   activity clock.
4. Enable `task-automation` only in the isolated profile and arm one one-shot
   exact-session rule with the `red_inactivity` trigger and a one-minute delay.
5. Prove the rule remains `waiting_for_event` immediately before the canonical
   15-minute Protocol 2 threshold.
6. At the threshold, prove the rule becomes `waiting` until the additional
   configured delay expires.
7. After that delay, invoke the real local native client exactly once and
   require `dispatch_started` or `input_emitted`.
8. Prove the isolated rule is disabled, its occurrence count is one and a
   second evaluation does not dispatch.
9. Accept success only when the unique marker appears as user input without the
   human typing it and a later exact-session hook is present.

No GUI, remote endpoint, Discord, alarm, activity synchronization, retry or
fallback is permitted.

## Operational Preflight

- The current exact Codex session and five installed hooks are available.
- `codex queue` is available.
- The installed runtime remains 0.9.0; the E2E therefore runs the 0.10.0 source
  candidate explicitly.
- The reply observer is failed after a historical SQLite lock followed by
  Discord timeout/DNS failures. It is unrelated to this local scheduler E2E and
  must not be restarted as part of the promotion.

## Promotion Gate

After the marker and hook evidence are recorded, update this plan and
`docs/TASKS.md`, commit on the task branch, fast-forward `develop`, push it,
fast-forward `main` to the same commit and push `main`. No release tag, GitHub
release or installed-runtime upgrade is included. The live test covers the
new one-shot rule path; bounded repetition remains covered by deterministic
tests because a second real prompt would add risk without proving a different
transport.

## Result - 2026-10-08

The authorized isolated E2E passed against exact session
`019f5691-c118-7370-a205-94cfde0a93d7` with marker
`[AI-PRESENCE-PROMPT-RULE-E2E:5cc95eb9-6d10-4325-bc3b-151c28b31b9c]`.
The human did not type the marker; it arrived as user input through the queued
prompt.

Recorded scheduler states were:

- immediately before red: `waiting_for_event`;
- at the Protocol 2 red threshold: `waiting`, due at the additional one-minute
  delay;
- at that due time: `dispatch_started`;
- after dispatch: rule disabled, occurrence count `1`;
- second evaluation: `disabled`, with no second transport.

The temporary `control.json` and SQLite database were removed automatically.
The operational database then recorded a later exact-session
`observation:codex:PreToolUse` hook for worker
`notebook-josue:codex:project=ai-presence-monitor-c5b81815`; the observation
was 1.419 seconds old when checked. No GUI, remote endpoint, Discord, alarm,
fallback, retry or activity synchronization participated in the transport.

The validated candidate was fast-forwarded to `origin/develop` and
`origin/main` at commit `e55658f`. No release tag, GitHub release or installed
runtime upgrade was performed.
