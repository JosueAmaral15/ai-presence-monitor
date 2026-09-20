# Task 025 - Transactional Upgrade and Rollback

## Objective

Replace the manual package-upgrade runbook with a deterministic Linux
transaction that preserves an exact rollback package, database snapshot and
managed-service state.

## Scope

- Local target and rollback wheels only.
- Installed-version and database preflight.
- Permission-restricted backup directory and atomic SHA-256 manifest.
- SQLite backup API before package mutation.
- Original active-service preservation across success and failure.
- Postflight version, migration and sanitized health validation.
- One automatic rollback attempt after failed mutation.
- Explicit manual rollback with checksum validation and database-loss
  acknowledgement.
- Human and AI-worker operational documentation.

This phase does not publish a package, create a Git tag, restore hosted CI,
support Windows upgrades, restart the desktop tray or authorize deployment to
the currently installed runtime.

## Safety Contract

- No package index or dependency resolution during the transaction.
- No shell execution.
- No `.env` values or secrets in manifests or command output.
- No package mutation in dry-run.
- No real upgrade without `--authorize-once`.
- No manual database restoration without both `--authorize-once` and
  `--restore-database`.
- No silent retry after failure or uncertainty.
- A service stopped before another stop fails is restarted before return.
- A service started under the target package is stopped before rollback.

## Validation

- [x] Focused updater and CLI tests cover dry-run and authorization.
- [x] Successful transaction writes private artifacts and restarts only the
  originally active services.
- [x] Failed postflight restores package, database and services.
- [x] Partial service stop is reversed before package installation.
- [x] Partial service start is stopped before automatic rollback.
- [x] Manual rollback restores the pre-upgrade database snapshot.
- [x] Tampered rollback artifact fails checksum validation.
- [x] Filesystem backup failure returns a controlled error before installation.
- [x] Complete local quality gate passes: 285 tests, 86% coverage, Ruff, mypy,
  compileall, build and diff checks.
- [x] Supported Python 3.10, 3.11 and 3.12 matrix passes with 285 tests on each.
- [x] Built-wheel isolated installation passes version, init, schema, doctor
  and updater command-help smokes.
- [ ] Authorized real installed-runtime upgrade and rollback E2E passes.
- [ ] Validated work is committed and integrated into `develop`.

## Release Boundary

The implementation may enter `develop` after local code, documentation and
package gates pass. It must not enter `main` or be tagged as a release until a
real installed-runtime transaction is explicitly authorized and validated.
The existing hosted-CI billing lock remains an external non-pass and must be
re-evaluated for any new release exception.
