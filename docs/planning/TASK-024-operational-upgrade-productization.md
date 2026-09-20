# Task 024 - Operational Upgrade to 0.8.0

## Objective

Deploy the validated private Linux 0.8.0 release into the dedicated user
virtual environment without exposing configuration, losing operational data or
silently broadening automation permissions.

## Scope

- Upgrade the installed package from 0.7.0 to 0.8.0.
- Preserve the existing `.env`, SQLite database, controls and systemd units.
- Keep the monitor and Discord reply observer enabled.
- Create a local rollback bundle before package replacement.
- Validate the installed artifact rather than importing from the checkout.

This task does not enable task automation, GUI fallback, remote input or
activity synchronization. It also does not publish a new package version.

## Preflight Finding

The checkout contains ignored generated `egg-info` directories. Running
`importlib.metadata.version()` from the repository root could therefore report
the stale value 0.3.0 even though the dedicated environment contained 0.7.0.
Inspection outside the checkout and the imported module both confirmed that
0.7.0 was the actual operational version before this deployment.

Installed-version checks must run outside the source checkout or resolve the
distribution path explicitly until productized version reporting is available.

## Deployment

1. Confirmed that both user services were enabled and active.
2. Stored the 0.7.0 wheel, wheel checksums, service units and dependency list in
   a permission-restricted local rollback directory.
3. Stopped the monitor and reply observer.
4. Created a consistent SQLite backup with the Python SQLite backup API.
5. Installed the validated 0.8.0 wheel with `--no-deps`.
6. Ran the additive database initialization.
7. Restarted both services.

The rollback bundle is stored under:

```text
$HOME/.local/share/ai-presence-monitor/backups/
  upgrade-0.7.0-to-0.8.0-20260920-152133/
```

It contains no committed secrets and remains outside the repository.

## Validation Evidence

- Installed distribution metadata: 0.8.0.
- Imported module version: 0.8.0.
- Operational SQLite `PRAGMA integrity_check`: `ok`.
- `recover-diagnostic-incident --help`: available.
- Tray dependency check: available; no persistent icon started.
- Codex hook installer dry-run: passed.
- Monitor and reply-observer installer dry-runs: passed.
- Both user services: enabled, active and stable with zero restarts after the
  deployment observation window.
- Existing controls preserved: native input enabled; task automation, GUI
  fallback, remote input and activity synchronization disabled.

No real `continue`, recovery, GUI input, Discord notification or alarm was
executed during the upgrade.

## Rollback

If an operational regression is confirmed:

1. Stop both user services.
2. Reinstall the saved 0.7.0 wheel with the dedicated virtual environment.
3. Restore the saved SQLite database only if the database migration itself is
   implicated; otherwise retain current operational data.
4. Restore unit files only if they were changed after this deployment.
5. Reload user systemd, start both services and repeat the integrity and
   stability checks.

Rollback must not overwrite newer operational data without explicit review.

## Productization Follow-up

The runtime is deployed, but a distributable software product still needs a
repeatable release and support surface. Recommended next work:

1. Add a deterministic `ai-presence --version` command that cannot be shadowed
   by generated checkout metadata.
2. Add a transactional `upgrade` command with preflight, backup manifest,
   health checks and an explicit rollback command.
3. Record and expose database schema version and migration status.
4. Produce tagged release artifacts with published SHA-256 checksums.
5. Restore hosted Linux CI after the external billing lock and define the
   supported release gate without claiming skipped jobs as passed.
6. Add a sanitized `doctor` command for package, configuration, database,
   hooks, controls and service health.
7. Define installation, upgrade and support policies before any public
   distribution.

