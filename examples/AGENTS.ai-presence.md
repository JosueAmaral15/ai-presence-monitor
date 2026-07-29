# AI Presence Instructions

Read the canonical protocol:

```text
/home/josue/Documents/Informática/programming/Linguagens de programação/Python - My files/Utils/Programs that should be used/ai-tools/ai-presence-monitor/docs/AI-WORKER-COMMAND-PROTOCOL.md
```

For every accepted task:

1. Set `PROJECT` to this repository root.
2. Run `ai-presence start --project "$PROJECT" --protocol protocol2`.
3. Let installed Codex hooks record normal work.
4. Run `ai-presence finish --project "$PROJECT" --protocol protocol2` only
   after the requested work is complete.

Never print monitor credentials or run GUI automation without explicit user
authorization.

