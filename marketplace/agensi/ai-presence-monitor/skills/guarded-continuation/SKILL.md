---
name: ai-presence-guarded-continuation
description: Evaluate and perform an authorized native continuation for an exact Codex session through an existing AI Presence Monitor installation, with no blind retry or false delivery claim.
---

# AI Presence Guarded Continuation

Use this skill for continuation only; ordinary work activity does not need a
`continue` message. Read `shared/safety-boundaries.md` before acting.

## Decide whether continuation is valid

Continue only when all conditions hold:

1. The current step is complete and validated.
2. A concrete next task is documented and belongs to the same scope.
3. No question, approval, error or other run is pending.
4. The exact target session is known.
5. The user enabled persistent task automation or explicitly authorized this
   invocation.

If any condition is false or unknown, stop and report it.

## Inspect before dispatch

Use the project's documented worker identity to inspect controls, then run an
exact-session dry-run:

```bash
ai-presence control show --profile "$WORKER_ID" --json

ai-presence --dry-run continue \
  --project "$PROJECT" \
  --thread "$EXACT_SESSION" \
  --transport native
```

Do not enable controls, edit prompt rules or redirect another profile. The
agent may disable only its current project's automation when required:

```bash
ai-presence disable-current-automation
ai-presence disable-current-prompt-rules
```

Re-enabling and rule editing belong to the human operator.

## Dispatch once

With a persistent grant, follow the installed command's normal continuation
form. With one-invocation authorization, make that boundary explicit:

```bash
ai-presence continue \
  --project "$PROJECT" \
  --thread "$EXACT_SESSION" \
  --transport native \
  --authorize-once
```

Never add `--authorize-once` unless the user authorized that invocation. Never
change session or transport because a dispatch failed or became uncertain.

## Report evidence precisely

Report `dispatch_started` or `input_emitted` exactly as preliminary states. Do
not call the continuation delivered or processed until the monitor observes the
required later activity from the exact session. A real E2E also requires one
unique marker that the human confirms they did not type.
