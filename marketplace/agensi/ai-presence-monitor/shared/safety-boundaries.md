# Shared Safety Boundaries

Apply these rules to every skill in this pack.

## Scope and identity

1. Read the target project's `AGENTS.md` and named monitor protocol first.
2. Resolve the target project's real absolute root. Never substitute the AI
   Presence Monitor source checkout for the project being worked on.
3. Use the exact Codex session when a command sends or correlates input. Do not
   select a different recent session to make a command succeed.
4. Never mutate another worker profile. An agent may disable automation only
   for the worker derived from its current project context.

## Secrets and installation

- Never display, copy, load into chat or commit a monitor `.env`, token,
  webhook, password, database or account payload.
- Locate `ai-presence` through normal command discovery and the target
  project's documented fallback. Do not invent a path for another computer.
- If the command is unavailable, report that the runtime is missing or not
  discoverable. Do not download, install or upgrade it without a separate user
  request and the product's upgrade protocol.

## Authorization and effects

- Read-only inspection does not grant permission to send input, publish a
  message, notify Discord, operate a GUI or recover a session.
- Ordinary continuation requires the user's persistent task-automation grant
  or explicit authorization for that invocation.
- Diagnostic recovery, answer dispatch and GUI automation always require
  explicit authorization for the individual invocation.
- A previous authorization, delivered notification or enabled transport does
  not authorize a different action or retry.

## Evidence

- `dry-run` proves selection and argument validation only.
- `dispatch_started` proves that a transport process started only.
- `input_emitted` proves that synchronous transport returned successfully only.
- A later hook from the exact session is required to establish later activity.
- A real transport E2E additionally requires a unique marker the human did not
  type. Do not manufacture confirmation with `touch` or a manually invoked
  hook.
- Failure, timeout, uncertainty or interruption does not authorize retry,
  fallback transport or a different target.

## Immediate stop condition

If a monitor-controlled alarm is audible, run `ai-presence stop-alarm`, check
the exit status and report the result before continuing other work.
