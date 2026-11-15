# Task 064 - Host Storage Recovery and Service Stability

## Problem

The root volume reached 100% utilization and SQLite returned `database or disk
is full`. The monitor and Discord reply observer entered restart loops while
the Prompt Rule observer remained active. This host condition prevented a
credible production-promotion decision even though the `0.13.1` runtime and
database schema were otherwise healthy.

## Action Plan

1. Confirm repository, runtime, schema, database and service state without
   mutating user data.
2. Identify large cache directories and check whether active processes hold
   files inside them.
3. Preserve repositories, databases, rollback manifests, Poetry virtual
   environments and the active Codex primary runtime.
4. Remove only regenerable Poetry artifacts, inactive Playwright browser
   downloads and temporary `codex-runtime-install-*` staging directories.
5. Re-run schema and strict doctor checks.
6. Observe all managed services for five minutes without resetting their
   restart counters, then compare the counters and inspect journals.
7. Document remaining external release gates separately.

## Operational Evidence

Authorized recovery completed on 2026-11-15:

- free space increased from 629 MB at 100% utilization to 7.1 GB at 97%;
- 1.9 GB of Poetry artifacts, 1.3 GB of inactive Playwright browsers and
  approximately 3.4 GB of temporary Codex runtime installers were removed;
- `codex-primary-runtime`, Poetry virtual environments, projects, databases,
  configuration and transactional rollback manifests were preserved;
- schema 3 and SQLite integrity remained healthy;
- six samples over five minutes kept restart counters unchanged at 49 for the
  monitor, 19 for the Discord reply observer and zero for the Prompt Rule
  observer;
- all three services remained `active/running` through repeated real cycles;
- a single Codex queue probe warning was transient: the immediate repeat and
  direct `codex queue --help` check passed.

## Remaining Boundary

The host is operational again but still at 97% utilization. Capacity should be
monitored and maintained above a practical safety margin. Promotion to `main`
also remains separate from the natural Token Recovery E2E, which requires an
actual exhausted-to-available quota transition and must not be simulated by
consuming the user's quota.
