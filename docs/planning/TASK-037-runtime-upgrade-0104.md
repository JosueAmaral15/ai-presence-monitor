# Task 037 - Runtime upgrade to 0.10.4

## Goal

Upgrade the dedicated Linux runtime from 0.10.3 to 0.10.4 through the supported
transactional path while preserving a verified rollback package, SQLite
snapshot, controls and the original state of managed services.

## Authorization and scope

The owner explicitly requested the upgrade on 2026-10-14. The authorization
covered one 0.10.3-to-0.10.4 transaction and the required tray replacement. It
did not authorize a rollback, tag, GitHub release or public artifact.

## Inputs

- target: the 0.10.4 wheel from the clean Task 036 release bundle;
- rollback: the 0.10.3 wheel preserved by the completed 0.10.2-to-0.10.3
  transaction;
- configuration: the existing private project `.env`, without printing or
  changing its values;
- database: the configured user database, schema version 1.

The target wheel hash matched its release manifest. The rollback wheel hash
matched the completed prior transaction manifest.

## Result

1. Preflight found runtime 0.10.3, an integral current schema, active monitor,
   active Discord reply observer and one active transient tray.
2. Dry-run returned `would_upgrade` from 0.10.3 to 0.10.4.
3. The old tray unit was stopped before package replacement.
4. One authorized upgrade returned `completed` and created a private rollback
   manifest under the managed user-state backup directory.
5. Runtime and strict doctor reported 0.10.4 and `ok`; schema 1 remained current
   and integral.
6. Monitor and reply observer returned to `active`.
7. The root launcher started one new tray process in an active transient user
   unit.
8. Rollback dry-run returned `would_rollback` from 0.10.4 to 0.10.3. No package
   or database restoration was performed.

The rollback manifest is mode `0600`, has status `completed`, retains the two
wheel hashes and SQLite snapshot, and records both previously active managed
services. Its absolute path remains local operational state and is not copied
into the repository.

## Residual boundary

The hosted GitHub Quality workflow remains externally blocked by account
billing and supplied no test evidence for 0.10.4. This runtime upgrade relies
on the already documented version-specific local exception, release gate and
live operational checks. A future upgrade or real rollback requires a new
explicit authorization and must not reuse this one-shot approval.
