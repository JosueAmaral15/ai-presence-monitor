# Task 053 - Linux Release 0.12.0

## Objective

Release bidirectional project/session-scoped Discord chat synchronization and
the schema-3 delivery audit contract under a distinct minor version. Keep the
installed 0.11.3 runtime and schema 2 available as one verified transactional
rollback unit until the complete operational gate passes.

## Gates

1. Keep Task 052's authorized real Discord-to-Codex exact-session E2E as the
   integration evidence for this candidate.
2. Run the full quality gate, Python 3.10-3.12 matrix and hosted Linux CI on the
   release branch, `develop` and `main`.
3. Build and verify a clean canonical 0.12.0 bundle tied to the exact final
   source commit.
4. Run the candidate-side updater dry-run against the authentic installed
   0.11.3 runtime and its verified rollback wheel.
5. Upgrade transactionally, migrate the operational database from schema 2 to
   schema 3 and restore the original active service set.
6. Prove one manual rollback with database restoration, then perform the final
   upgrade back to 0.12.0.
7. Restart the tray as a fresh top-level process and verify strict doctor,
   hooks, controls, services, schema, tray stability and absence of an alarm.
8. Promote only by fast-forward after the corresponding hosted CI passes.

## Publication Boundary

This task prepares the local product release, upgrades the authorized runtime
and promotes repository branches. It does not create a Git tag, publish a
GitHub release or upload assets without a separate explicit authorization.

## Rollback

Use the manifest produced by the transactional upgrade. Manual rollback must
restore both the preserved 0.11.3 wheel and its schema-2 database snapshot.
Never lower `PRAGMA user_version` manually. Leave the machine on 0.12.0 after
the rollback proof and final re-upgrade complete.
