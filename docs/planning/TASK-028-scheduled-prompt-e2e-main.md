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
