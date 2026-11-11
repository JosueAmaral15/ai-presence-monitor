---
name: ai-presence-worker-lifecycle
description: Operate the project-scoped start, meaningful-activity and finish lifecycle of an existing AI Presence Monitor installation without manufacturing presence.
---

# AI Presence Worker Lifecycle

Use this skill when an installed AI Presence Monitor should track work on the
current local project. Read `shared/safety-boundaries.md` before acting.

## Establish the project

1. Read the project's instructions and determine the protocol it requires.
2. Resolve the project root as an absolute path.
3. Confirm `ai-presence --help` succeeds. If it does not, report the missing
   prerequisite rather than installing or initializing anything.
4. Use project scope unless the project explicitly requires another scope.

## Start once

After accepting concrete work, run one start command with the absolute project
path, configured protocol and a short task description:

```bash
ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "Accepted work started"
```

Do not repeat `start` as a heartbeat.

## Record real activity

Let installed lifecycle hooks record normal activity. If hooks are unavailable,
use `touch` only after a meaningful checkpoint:

```bash
ai-presence touch \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "Verified checkpoint completed"
```

Elapsed time, a timer callback or a scheduled poll is not evidence of work.
Report nonzero command status instead of silently retrying.

## Finish once

After implementation, applicable validation and the required session commit:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "Accepted work completed"
```

Do not use `finish` for a brief pause while the same work remains assigned.
