# Task 046 - Integrated Chat and Recovery Release

## Objective

Release the conversation surface and durable usage-recovery observer as one
validated Linux product candidate.

## Gates

1. Run focused tests, full quality gate and Python 3.10-3.12 matrix.
2. Build and verify a clean release bundle from the exact committed revision.
3. Prove schema-1 to schema-2 upgrade and database rollback in an isolated copy.
4. Install the wheel transactionally with the authentic previous wheel.
5. Install exactly one prompt-rule observer service and verify zero restart
   loops.
6. Run `doctor --strict` and check monitor, Discord observer, prompt observer,
   tray and hooks.
7. Perform one exact-session chat E2E with a unique marker not typed manually.
8. Perform a bounded recovery E2E using controlled evidence; do not deliberately
   exhaust account tokens.

## Promotion

Validated implementation advances to `develop`. `main` requires all local
release gates plus the real integrations above. Hosted CI blocked before any
steps remains external failed evidence and must not be described as passing.

## Rollback

Stop the new observer and tray, restore the pre-upgrade database backup and old
wheel transactionally, restore the previous service set, then rerun strict
doctor. Never run the schema-1 runtime against a schema-2 database.

## 2026-11-02 evidence

- clean 0.11.2 bundle verified from `83a5c66`;
- 357 tests passed on Python 3.10, 3.11 and 3.12 with 87% coverage;
- isolated schema 1 to 2 migration and database-backup restoration passed;
- transactional runtime upgrades completed with authentic rollback wheels;
- strict doctor passed on 0.11.2 with all three services active;
- prompt-rule observer and tray each reported `NRestarts=0`;
- exact-session chat reached later `delivery_confirmed` evidence;
- isolated real observer reached `usage_available` and one `dispatch_started`.

Hosted GitHub CI remains external failed evidence. This candidate may advance
to `develop`, but `main` still requires the repository's release decision for
that unresolved external gate.
