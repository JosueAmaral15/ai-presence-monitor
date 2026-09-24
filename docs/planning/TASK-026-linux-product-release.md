# Task 026 - Professional Linux Product Release 0.9.0

## Objective

Finish AI Presence Monitor as a private, reusable Linux product that can be
installed on another supported Linux computer and used by multiple projects
without depending on the source checkout.

## Release Boundary

- Release version: `0.9.0`.
- Supported operating system: Linux.
- Supported Python versions: 3.10, 3.11 and 3.12.
- Tested desktop/runtime baseline: Linux Mint and Ubuntu-compatible userland.
- Windows implementation remains preserved, experimental and disabled by
  default. It is not a release gate for 0.9.0.
- Distribution remains private. No public package index publication is part of
  this task.

## Phase 1 - Product Contract

- [x] Define installation, upgrade, rollback, compatibility and support policy.
- [x] Document fresh-machine prerequisites and post-install verification.
- [x] Document multi-project operation with absolute project identity.
- [x] Record the latest hosted-CI zero-step external failure accurately.

## Phase 2 - Release Tooling

- [x] Bump package and runtime version together to 0.9.0.
- [x] Add a fresh Linux installer that consumes a local wheel.
- [x] Preserve an existing private configuration and never print secrets.
- [x] Add a release builder that emits wheel, sdist, installer, configuration
  template, manifest and SHA-256 checksums without stale artifacts.
- [x] Add an offline verifier that checks hashes, package metadata and an
  isolated installed-runtime smoke.

## Phase 3 - Portable Validation

- [x] Full local quality gate passes.
- [x] Python 3.10, 3.11 and 3.12 matrix passes.
- [x] Release artifacts verify offline from a clean temporary home.
- [x] Fresh installer E2E passes without source-checkout imports.
- [x] Two separate project roots produce separate workers and preserve their
  own lifecycle state.
- [x] Linux services, hooks and tray checks remain package-relative.
- [x] Windows remains disabled by default and Windows modules remain packaged.

## Phase 4 - Operational Transaction

- [x] Preserve an authentic 0.8.0 rollback wheel and verify its checksum.
- [x] Run a no-mutation transactional dry-run against the installed runtime.
- [ ] Obtain explicit authorization immediately before stopping live services
  or restoring the operational database.
- [ ] Upgrade the dedicated runtime from 0.8.0 to 0.9.0.
- [ ] Verify version, schema, doctor, controls, hooks, services and tray.
- [ ] Roll back once to authentic 0.8.0 and verify package/database/services.
- [ ] Upgrade again to 0.9.0 so the machine ends on the release candidate.
- [ ] Perform only the real external integrations explicitly required by the
  release plan, with unique correlation and no uncertain retry.

## Phase 5 - Publication

- [x] Commit each completed phase on the task branch.
- [ ] Integrate and push validated work to `develop`.
- [ ] Re-run final release gates at the exact candidate commit.
- [ ] Promote `develop` to `main` only after Phase 4 passes.
- [ ] Create and push an annotated `v0.9.0` tag only at the validated main
  commit.
- [ ] Publish private release artifacts and checksums without secrets.

## Stop Conditions

Do not promote or tag when any of these is true:

- package/runtime versions differ;
- the rollback wheel is not authentic or its checksum is unknown;
- a service, database or artifact verification is uncertain;
- a required real E2E lacks explicit authorization or unique evidence;
- the live machine is left on the rollback version;
- uncommitted or unrelated work is present;
- hosted CI is described as passing when no job steps executed.

## Rollback

Source changes remain isolated on the task branch until validated. The live
transaction uses the Task 025 manifest and snapshot contract. Manual database
restoration requires explicit acknowledgement because it discards writes made
after the snapshot. Failed or uncertain delivery, upgrade or rollback is never
retried automatically.

## Evidence - 2026-09-24

- Full local gate: 291 tests passed, coverage 86%, Ruff and mypy passed, shell
  syntax passed, offline wheel/sdist build passed and `git diff --check` passed.
- Supported matrix: the same 291 tests passed sequentially on Python 3.10,
  3.11 and 3.12.
- Development bundle verification passed from an isolated temporary home,
  including schema/doctor checks and two distinct absolute project identities.
- Fresh installer E2E returned version 0.9.0, schema 1 healthy, mode-0600
  configuration and the expected command link; a second run refused the
  existing runtime.
- Authentic rollback wheel was built from historical commit `5205ca4` and
  verified as `ai-presence-monitor` 0.8.0 with SHA-256
  `05a7fa214ca1dd79f2b0f8f0fb3acc4f7946ecb2c26a2746b3efae6e89fac3db`.
- Clean-source bundle verification passed for commit `8ed6c76`, with
  `source_dirty=false`, six declared artifacts and an isolated installed smoke.
- The real installed 0.8.0 runtime accepted the authentic wheel pair in a
  host-level `--dry-run` and returned `would_upgrade` to 0.9.0. The first
  sandboxed attempt failed closed because user-systemd bus access was denied;
  no live service or database mutation has been performed.
