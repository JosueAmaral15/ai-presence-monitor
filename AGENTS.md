# AI-worker Instructions

Before operating this project or using the monitor from another project, read:

- `docs/USO-COMO-FERRAMENTA.md`
- `docs/AI-WORKER-COMMAND-PROTOCOL.md`
- `docs/security/SECURITY.md`

Use the installed `ai-presence` command. If it is not in `PATH`, use:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence"
```

Operational rules:

0. Keep the root `README.md` in English. Put Portuguese content in
   `README.pt-BR.md` or under `docs/`.
1. Never print, copy, source, or commit the monitor `.env`.
2. Use an explicit absolute `--project` path for project-scoped workers.
3. Run `start` once when accepted work begins and `finish` once when it ends.
4. Let Codex hooks record normal activity. Use `touch` only after meaningful
   work when hooks are unavailable; do not emit timer-only activity.
5. Prefer a native user-input mechanism when one exists. Use Discord questions
   as a fallback, with correlation and allowlist enabled.
6. Ordinary native `continue` may use either the user's persistent
   `task-automation` grant or an explicit `--authorize-once`, after the
   normative continuation checks pass. Diagnostic recovery, `dispatch-answer`
   and GUI automation always require explicit one-invocation authorization;
   never infer it from a persistent control.
7. Treat `dispatch_started` and `input_emitted` as preliminary transport
   states, not proof that Codex processed the input. A later hook is necessary;
   an E2E claim also requires a unique marker that the human did not type.
8. Check command exit status. Report failures instead of silently retrying GUI
   input.
9. If the local alarm is audible, run `ai-presence stop-alarm` immediately.
10. End each work session with a commit on its task branch. Promote validated,
    functional work to `develop`. Promote `develop` to `main` only when all
    required release checks and real integrations have passed; keep unresolved
    external validation documented instead of declaring the release ready.
