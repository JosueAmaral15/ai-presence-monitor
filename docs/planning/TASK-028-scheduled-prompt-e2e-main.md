# Task 028 - Scheduled Prompt E2E and Main Promotion

## Objective

Prove one real 0.10.0 scheduled prompt dispatch to the current exact Codex
session before promoting the already validated `develop` candidate to `main`.

## Authorization Boundary

The real step emits Codex input. It requires explicit authorization for one
invocation immediately before dispatch. General permission to commit, push or
continue development is not reused as input authorization.

## Isolated E2E Contract

1. Generate a unique marker immediately before the run.
2. Use the source 0.10.0 scheduler with a temporary `control.json` and SQLite
   database; do not alter installed 0.9.0 controls or presence data.
3. Create one active Protocol 2 worker in the temporary database with a known
   activity clock.
4. Arm one exact-session schedule with delay and red gate enabled.
5. Prove the due schedule remains `waiting_for_red` immediately before the
   canonical 15-minute threshold.
6. At the threshold, invoke the real local native client exactly once and
   require `dispatch_started` or `input_emitted`.
7. Prove the isolated schedule is disabled and a second evaluation does not
   dispatch.
8. Accept success only when the unique marker appears as user input without the
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
release or installed-runtime upgrade is included.
