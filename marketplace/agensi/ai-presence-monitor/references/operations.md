# Operations Reference

## Resolve the command

Use the installed command when present:

```bash
command -v ai-presence
```

Some Linux installations place the command inside the product runtime. A
project's `AGENTS.md` may provide the exact fallback path. Do not invent one
for a different computer.

## Start and finish

Set `PROJECT` to the absolute root of the project being worked on:

```bash
ai-presence start \
  --project "$PROJECT" \
  --scope project \
  --task "TASK-ID short description" \
  --message "Accepted work started"
```

After the work, validation and required commit:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --scope project \
  --message "Accepted work completed"
```

Use the protocol configured by the project unless the user explicitly selects
another one.

## Meaningful fallback activity

Only when hooks are unavailable and meaningful work occurred:

```bash
ai-presence touch \
  --project "$PROJECT" \
  --scope project \
  --message "Implemented and validated a concrete change"
```

Do not schedule timer-only `touch` calls.

## Inspect without mutation

```bash
ai-presence status --project "$PROJECT" --scope project
ai-presence doctor
```

Use JSON output only when the installed command documents that option. Do not
include raw configuration or secret-bearing files in reports.

## Alarm handling

When a monitor-controlled local alarm is audible:

```bash
ai-presence stop-alarm
```

Check the exit status and report whether the alarm was stopped, already
inactive, or could not be controlled.

## Continuation evidence

Before any continuation action, confirm the exact session and applicable human
authorization. After dispatch:

- `dispatch_started`: a transport process started;
- `input_emitted`: synchronous transport returned successfully;
- later hook activity: the exact Codex session subsequently acted;
- unique marker observed without human entry: required for a real transport
  E2E claim.

Never collapse these into a single "delivered" state.
