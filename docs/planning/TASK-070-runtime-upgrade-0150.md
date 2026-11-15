# Task 070 - Transactional Runtime Upgrade 0.15.0

## Incident

The package smoke test for Task 069 set `DB_PATH`, which is not an application
configuration key. Because no isolated `--env-file` was supplied, the command
loaded the project environment and migrated the operational database from
schema 3 to schema 4 while runtime `0.14.0` was still installed.

The older runtime failed closed as designed. The monitor and observer units
entered restart attempts until the mismatch was identified. All product units
and the tray were then stopped. No schema marker was lowered, no table was
dropped and no database snapshot was restored over newer operational data.

## Recovery Plan

1. Verify the `0.15.0` candidate and preserved `0.14.0` rollback wheel hashes.
2. Confirm schema 4 integrity, available disk space and inactive services.
3. Record explicit authorization for exactly one real transactional upgrade.
4. Execute the transaction once and require a `completed` manifest.
5. Validate installed version, schema, integrity and strict product health.
6. Start the three managed services and exactly one tray instance.
7. Observe service restart counters and inspect recent journals.
8. Record the isolation failure and require `PRESENCE_DB_PATH` plus an explicit
   temporary `--env-file` for future smoke tests.

## Result

Completed on 2026-11-15. The authorized transaction upgraded runtime `0.14.0`
to `0.15.0` and produced:

`~/.local/state/ai-presence-monitor/backups/upgrade-0.14.0-to-0.15.0-20261115-195149-c70e2e4c/manifest.json`

The installed command reports `ai-presence 0.15.0`; schema 4 is current and
SQLite integrity is `ok`. Monitor, Discord reply observer, Prompt Rule observer
and the tray are `active/running`, each with zero restarts after recovery. One
tray process exists. The final `doctor --strict --json` status is `ok`.

The first post-start Codex queue probe exceeded its five-second health timeout.
A direct non-dispatching `codex queue --help` probe completed in 1.32 seconds,
and the next strict doctor check passed. No prompt was sent during validation.

## Future Isolation Rule

Do not rely on a generic `DB_PATH` variable. A disposable package test must:

1. create a temporary private `.env`;
2. set `PRESENCE_DB_PATH` inside it to an absolute temporary path;
3. pass it through `--env-file` on every command;
4. verify the resolved database path before running `init`;
5. assert afterwards that the operational database metadata did not change.
