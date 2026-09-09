# AI-worker Instructions

Before operating this project or using the monitor from another project, read:

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
6. Do not execute `continue`, `dispatch-answer`, or any GUI automation without
   explicit user authorization for that action.
7. Treat a successful GUI input as `input_emitted`, not proof that Codex
   processed it. A later hook is the confirmation signal.
8. Check command exit status. Report failures instead of silently retrying GUI
   input.
9. If the local alarm is audible, run `ai-presence stop-alarm` immediately.
10. End each work session with a commit on its task branch. Promote validated,
    functional work to `develop`. Promote `develop` to `main` only when all
    required release checks and real integrations have passed; keep unresolved
    external validation documented instead of declaring the release ready.
