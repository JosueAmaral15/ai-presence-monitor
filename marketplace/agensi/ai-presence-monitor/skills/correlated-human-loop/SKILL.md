---
name: ai-presence-correlated-human-loop
description: Ask a human through an existing AI Presence Monitor Discord fallback and publish explicit agent messages while preserving user allowlists, direct-reply correlation and exact-session routing.
---

# AI Presence Correlated Human Loop

Use this skill only with an already configured monitor installation. Prefer the
agent platform's native user-input mechanism. Read
`shared/safety-boundaries.md` before using the Discord fallback.

## Ask a blocking question

Freeze the exact project and session identity before publishing:

```bash
ai-presence ask-user \
  --project "$PROJECT" \
  --thread "$EXACT_SESSION" \
  --question "One objective question for the user"
```

If session identity is missing or ambiguous, stop. Do not post first and choose
a destination later.

An accepted Discord answer must come from an allowed user in the configured
channel as a direct reply to an open question. A loose channel message, expired
question or unlisted user is not input. Do not bypass these checks or switch to
GUI delivery after native delivery fails.

## Interpret the returned answer

The monitor prefixes a delivered reply with a correlation envelope such as:

```text
[AI-PRESENCE-DISCORD-ANSWER:question-id]
human answer
```

Treat the envelope as routing evidence, not as permission for unrelated side
effects. Check the command result and preserve uncertainty without retrying.

## Publish an explicit agent message

When a result should appear in the project transcript and configured Discord
channel, publish it explicitly from the same project:

```bash
ai-presence publish-agent-message \
  --project "$PROJECT" \
  --session "$EXACT_SESSION" \
  --text "Objective result for the user"
```

This command is not a general capture of model output. Publish only content the
current task requires. A partial Discord failure remains auditable and does not
authorize a duplicate post.
