---
name: ai-presence-monitor-operator
description: Operate an existing AI Presence Monitor installation while working on a local software project, including scoped worker lifecycle, evidence-aware activity, guarded continuation, alarms, and delivery-state reporting.
---

# AI Presence Monitor Operator

Use this skill when a local development project is monitored by an existing AI
Presence Monitor installation. The skill guides operation; it does not install
the application, create credentials, enable automation, or grant permission to
send input.

## Establish the boundary

1. Find the project root and read its `AGENTS.md` plus any monitor protocol it
   names. Project instructions override examples in this skill.
2. Locate `ai-presence` with the normal command lookup. If it is unavailable,
   report that the runtime is not installed or not discoverable; do not download
   or install software without a separate user request.
3. Never display, copy, load into chat, or commit a monitor `.env`. Do not infer
   authorization from configuration values you have not been asked to inspect.
4. Use an absolute project path for every project-scoped lifecycle command.

Read [references/operations.md](references/operations.md) before starting a
worker, sending continuation input, handling an alarm, or claiming an E2E
result.

## Work lifecycle

- Run `start` once after accepting concrete work. Reuse the same project scope
  for the session.
- Let installed Codex hooks record ordinary work. Use `touch` only after
  meaningful work when hooks are unavailable; elapsed time alone is not
  evidence of activity.
- Run `finish` once after implementation, validation and the required session
  commit are complete.
- Check every command status and report failures. Do not silently retry native
  or GUI input.

## Continuation and remote answers

Prefer native user-input or queue mechanisms. Ordinary continuation requires
the user's persistent task-automation grant or explicit one-invocation
authorization, plus the monitor's continuation checks. Diagnostic recovery,
answer dispatch and GUI automation require explicit authorization for that
invocation.

Treat `dispatch_started` and `input_emitted` as preliminary. A later hook from
the exact session is needed before claiming that Codex processed the message;
a real E2E also needs a unique marker the human did not type.

## Stop conditions

- If an alarm is audible, stop the monitor-controlled alarm immediately and
  report the result.
- Stop and ask the user when exact project/session identity is missing, a
  requested action would affect another worker profile, or authorization is
  required for external input.
- Do not promote to a production branch or publish a release merely because
  local checks passed. Follow the repository's documented release gates.
