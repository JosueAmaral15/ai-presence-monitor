# Task 029 - Profile Prompt Rules

## Objective

Replace the single tray editor with a persistent collection of prompt rules per
worker profile. Also give an AI-worker a narrow command that disables task
automation only for the worker derived from its current project context.

## Rule Model

Each rule stores:

- stable rule identifier and enabled checkbox;
- exact Codex session;
- trigger: elapsed time after arming or canonical protocol red inactivity;
- delay in minutes after the trigger;
- bounded single-line prompt text;
- one-shot or repeating mode;
- repeat interval and maximum occurrence count;
- next due time, occurrence count, confirmation wait and last transport state.

The safe repeating default is three total occurrences. A rule may configure up
to 100 occurrences, but never an unbounded loop. After a successful transport,
the next occurrence remains paused until a later hook from the same exact
session is observed. Failure or uncertainty disables the rule.

## Agent Boundary

`disable-current-automation` derives the worker from the configured scope,
current working directory and current Codex session environment. It accepts no
worker, project, scope, computer or agent override. AI-worker documentation
permits this command and forbids arbitrary control mutation. `control show
--profile` remains read-only; profile editing belongs to the human tray.

This is an accidental-cross-project safeguard, not an OS security boundary. A
malicious process running as the same user can still change its working
directory or edit the private control file.

## Compatibility

- Keep control schema version 1 and all legacy scheduled-prompt fields.
- Add `prompt_rules` to each complete profile.
- Continue processing an armed legacy schedule until the human saves that
  profile in the new editor.
- On save, represent the visible legacy schedule as a rule and disable the
  legacy runtime state.
- New profiles inherit preferences but never another profile's rules or runtime
  schedule state.

## GUI

The preferences dialog keeps an explicit project/agent selector. The prompt
section contains repeatable rule rows and an Add button. Each row exposes its
enabled state, trigger, delay, text, repeat checkbox, interval, occurrence limit
and remove action. Sessions remain filtered to the selected worker.

## Validation

- Persistence and migration tests for multiple independent profiles.
- Scheduler tests for delay, red event, one-shot, bounded repeat, confirmation,
  failure, one-dispatch-per-poll and profile isolation.
- CLI tests proving current-project disable and rejection of arbitrary profile
  mutation.
- Qt import/smoke remains optional and no automated test emits real Codex input.
- Full coverage, Python 3.10/3.11/3.12, Ruff, mypy, compileall, shell syntax and
  package build must pass before the revised E2E candidate.

## Implementation Result

Completed on the task branch on 2026-10-08. The local candidate passed 312
tests on each supported Python version, 86% aggregate coverage, Ruff, mypy,
compileall, shell syntax, wheel/sdist build and the native tray availability
check. No automated test emitted real Codex input. The isolated real scheduler
E2E and `main` promotion remain tracked by Task 028 and require fresh explicit
authorization immediately before the single transport.
