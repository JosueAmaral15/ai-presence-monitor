# Task 025 - Product Diagnostics and Schema Contract

## Objective

Create deterministic, read-only preflight primitives that a future
transactional updater can trust.

## Scope

- Deterministic product version output.
- Explicit SQLite schema version and migration status.
- Read-only database integrity and required-table inspection.
- Sanitized health checks for local product dependencies.
- Text and JSON output with strict warning exit behavior.

This phase does not install packages, create backups, restart services, send
input, contact notification endpoints or perform rollback.

## Validation

- 277 tests pass with 87% total coverage.
- Ruff, mypy over 37 source files, compileall, build and diff checks pass.
- A temporary legacy database migrates to schema 1.
- A newer schema fails closed without downgrade.
- Missing-database inspection creates no file.
- A source smoke reports all configured local checks as `ok`.
- Database checksum remains unchanged across the real `doctor` smoke.
- JSON output contains no configured Discord or Telegram token values.

## Checklist

- [x] Add deterministic `ai-presence --version`.
- [x] Add schema version 1 and read-only `schema-status`.
- [x] Add sanitized `doctor` with strict mode.
- [x] Add focused migration, future-version and sanitization tests.
- [x] Pass the complete local quality gate.
- [ ] Commit and integrate the validated phase into `develop`.

