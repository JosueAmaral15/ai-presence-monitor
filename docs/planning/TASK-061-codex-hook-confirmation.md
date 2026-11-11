# Task 061 - Codex Lifecycle Hook Confirmation

## Problem

The authorized Prompt Rule E2E delivered a unique marker to the exact Codex
session and started a new turn. The canonical presence database did not receive
a later lifecycle-hook event from that turn, although the installed monitor
reported its hook files as present.

Transport delivery and lifecycle observation are independent evidence. The
first must not be promoted to `delivery_confirmed` when the second is absent.

## Evidence Collected

- The current Codex session displayed and processed the unique marker.
- The Prompt Rule reserved one occurrence and did not resend.
- The installed `hooks.json` defines `SessionStart`, `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse` and `Stop`.
- `PreToolUse` and `PostToolUse` use the supported catch-all matcher `*`.
- The installed hook command accepted an equivalent payload with `--dry-run`
  and derived the expected project worker without writing to the database.
- No post-dispatch event for the exact session appeared in the canonical
  database during the active turn.
- On 2026-11-05, `codex doctor` independently reported insufficient free space,
  missing or unusable rollout references and a failed integrity check for
  `~/.codex/logs_2.sqlite`. A read-only SQLite `quick_check` then reported
  corrupt pages and an inconsistent index. On 2026-11-11, a new read-only
  `PRAGMA quick_check` returned `ok` while active Codex processes owned the
  database and its WAL/SHM files. The earlier incident remains relevant, but
  the database is not currently established as corrupt and was not repaired or
  mutated during this investigation. Low free disk space remains a runtime
  risk and neither observation proves the cause of the missing hook.

## Action Plan

1. Review and trust the current user-level hook definition in Codex Desktop.
2. Preserve a backup-first recovery plan and recover adequate free disk space
   without deleting rollout or conversation evidence; repeat read-only health
   checks only if symptoms recur.
3. Reload the Codex runtime or start a fresh session so hooks are loaded from
   the current configuration.
4. Perform a harmless tool action and require real `UserPromptSubmit`,
   `PreToolUse` and `PostToolUse` evidence from the same session.
5. Confirm that the hook event changes monitor activity and can confirm a
   pending exact-session native delivery.
6. Add a product-health distinction between "hook files installed" and
   "recent lifecycle event observed" if the runtime cannot expose hook trust
   or loaded state directly.
7. Run focused and full quality gates, then reassess release promotion.

## Safety Constraints

- Do not call the hook manually without `--dry-run` to manufacture evidence.
- Do not use `touch` as a substitute for lifecycle evidence.
- Do not resend the unique Prompt Rule marker.
- Do not bypass hook trust silently.
- Do not delete, replace or mutate the Codex state database based on the
  historical incident. Require a backup and reviewed recovery plan if current
  read-only evidence reports corruption again.
- Do not expose prompt text, account tokens, environment values or full session
  identifiers in committed evidence.

## External Boundary

The current official Codex hook documentation states that user hooks can be
loaded from `~/.codex/hooks.json`, non-managed hooks require user review and
trust, `*` is a supported catch-all matcher, and most local function tools use
the lifecycle hook path. A runtime reload or explicit trust review may require
human interaction in Codex Desktop.
