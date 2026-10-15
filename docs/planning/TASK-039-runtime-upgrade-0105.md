# Task 039 - Runtime upgrade to 0.10.5

## Goal

Upgrade the dedicated Linux runtime from 0.10.4 to 0.10.5 through the supported
transactional path while preserving a verified rollback package, SQLite
snapshot, controls and the original state of managed services.

## Authorization and scope

The owner explicitly requested the upgrade on 2026-10-15. The authorization
covered one 0.10.4-to-0.10.5 transaction and the required tray replacement. It
did not authorize a rollback, tag, GitHub release or promotion to `main`.

## Inputs

- target: the 0.10.5 wheel from the clean Task 038 release bundle;
- rollback: the 0.10.4 wheel preserved by the completed prior transaction;
- configuration: the existing private project `.env`, without printing or
  changing its values;
- database: the configured user database, schema version 1.

The target wheel hash matched `SHA256SUMS`, the release manifest and the wheel
metadata. The rollback wheel was read from the prior completed transaction.

## Result

1. Preflight found runtime 0.10.4, an integral current schema, active monitor,
   active Discord reply observer and one active transient tray.
2. Strict doctor reported `ok` before the operation.
3. Dry-run returned `would_upgrade` from 0.10.4 to 0.10.5.
4. The old tray unit was stopped before package replacement.
5. One authorized upgrade returned `completed` and created a private rollback
   manifest under the managed user-state backup directory.
6. Runtime and strict doctor reported 0.10.5 and `ok`; schema 1 remained current
   and integral.
7. Monitor and reply observer returned to `active`, and the root launcher
   started exactly one active tray process.
8. The installed runtime exposed `disable-current-prompt-rules`.
9. Rollback dry-run returned `would_rollback` from 0.10.5 to 0.10.4. No package
   or database restoration was performed.

The rollback manifest is mode `0600` and has status `completed`. Its absolute
path remains local operational state and is not copied into the repository.

## Residual boundary

The hosted GitHub Quality workflow remains externally blocked by account
billing and supplied no test evidence for 0.10.5. The release candidate relies
on the documented local release gate, supported Python matrix and installed
isolated E2E. `main` remains at 0.10.4 until the owner makes a separate
promotion decision. A future upgrade or real rollback requires a new explicit
authorization and must not reuse this one-shot approval.
