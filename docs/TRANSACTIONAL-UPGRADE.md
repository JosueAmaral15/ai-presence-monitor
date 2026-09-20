# Transactional Upgrade and Rollback

## Purpose

The `upgrade` command replaces an installed Linux package from a local wheel
while preserving a verified rollback wheel, a consistent SQLite snapshot and
the state of managed user services. It does not download packages, resolve
dependencies, modify `.env`, send notifications or execute Codex input.

This is the supported workflow for future private Linux upgrades. Windows
adapters remain preserved, but transactional package upgrade is not yet a
supported Windows operation.

## Inputs

Prepare two trusted wheel files:

- `--package`: the new `ai-presence-monitor` wheel;
- `--rollback-package`: the wheel for the version currently installed in the
  same dedicated virtual environment.

The command rejects a rollback wheel whose version differs from the installed
runtime. Both files must contain package metadata for `ai-presence-monitor`.
Run the installed command, not a source-checkout interpreter.

## Preflight

Always begin without authorization:

```bash
ai-presence --version
ai-presence schema-status --json
ai-presence doctor --json --strict
ai-presence --dry-run upgrade \
  --package /absolute/path/ai_presence_monitor-NEW-py3-none-any.whl \
  --rollback-package /absolute/path/ai_presence_monitor-OLD-py3-none-any.whl \
  --json
```

Dry-run validates platform, wheel metadata, installed version, database
integrity/schema and current service state. It creates no backup and installs
nothing. A nonzero exit must be investigated; do not add authorization merely
to bypass a failed preflight.

## Authorized Upgrade

After reviewing the dry-run and confirming the wheel sources:

```bash
ai-presence upgrade \
  --package /absolute/path/ai_presence_monitor-NEW-py3-none-any.whl \
  --rollback-package /absolute/path/ai_presence_monitor-OLD-py3-none-any.whl \
  --authorize-once \
  --json
```

The command performs these phases:

1. creates a private backup directory under
   `$XDG_STATE_HOME/ai-presence-monitor/backups`, or
   `~/.local/state/ai-presence-monitor/backups` when `XDG_STATE_HOME` is unset;
2. copies both wheels and creates a consistent SQLite snapshot;
3. writes SHA-256 values and original active-service state to `manifest.json`;
4. stops only the managed services that were active;
5. installs the target wheel using `pip --no-index --no-deps`;
6. runs database initialization and a sanitized postflight `doctor`;
7. restarts the services that were active before the transaction;
8. records `completed` only after all phases succeed.

If a failure occurs after package installation begins, the command stops any
partially restarted services, reinstalls the preserved wheel, restores the
database snapshot, verifies the prior version and restarts the original active
services. It records the result instead of silently retrying.

The tray process is not a managed user service. Exit and reopen the tray after
a successful package upgrade so it loads the new Python code.

## Manual Rollback

First inspect the manifest path returned by the successful upgrade:

```bash
ai-presence --dry-run rollback-upgrade \
  --manifest /absolute/path/to/manifest.json \
  --json
```

Manual rollback intentionally restores the database snapshot from before the
upgrade. This discards operational data written after that snapshot. It
therefore requires two explicit acknowledgements:

```bash
ai-presence rollback-upgrade \
  --manifest /absolute/path/to/manifest.json \
  --authorize-once \
  --restore-database \
  --json
```

Before restoration, the command creates a snapshot of the current upgraded
database. It verifies every referenced artifact checksum and refuses manifests
outside the managed backup root. If rollback fails, it attempts to restore the
upgraded package and database state once. An uncertain or failed result must be
handled manually; do not rerun automatically.

## Manifest States

Important terminal states are:

- `completed`: target package and services passed postflight;
- `rolled_back_after_failure`: automatic rollback restored the old runtime;
- `manually_rolled_back`: an authorized manual rollback completed;
- `aborted_before_install`: service shutdown failed before package mutation;
- `rollback_failed`, `rollback_recovery_failed`, or a service-restore failure:
  manual inspection is required before another operation.

Manifest files contain paths, versions, service names, timestamps and hashes,
but no `.env` values, webhook URLs, tokens, prompts or Discord messages.

## Rules for AI Workers

An AI worker may run version, schema, doctor and both dry-runs as read-only
preflight. It must not execute a real `upgrade` or `rollback-upgrade` without
explicit authorization for that operation. It must report the exit status and
manifest state. It must not automatically retry an uncertain transaction,
delete backup artifacts, restore a database, restart the tray or promote a
release based only on unit tests.

Release readiness still requires the repository quality gate, supported Python
matrix, built-artifact installation checks and any real integration E2E named
by the release plan. Hosted CI that did not execute is not a passing gate.
