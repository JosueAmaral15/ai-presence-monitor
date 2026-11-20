# Task 071 - Release 0.15.1, Debian Package and Onboarding

## Problem

Runtime `0.15.0` is installed and schema 4 is healthy, but the continuous
automation observer exited after a temporary Codex App Server
`account/rateLimits/read` error. The Debian and installation documentation also
still presents older artifact names, and the release bundle lacks a concise
beginner path from download to first healthy worker.

## Scope

1. Make a temporary account-read failure fail closed for one poll while the
   continuous observer remains alive and no prompt is dispatched.
2. Release the correction as `0.15.1`, because an installed `0.15.0` runtime
   already exists and must never share a version with different code.
3. Add English and Portuguese first-run guides covering installation choice,
   local-only setup, optional integrations, tray setup, health checks, normal
   operation and recovery from common mistakes.
4. Include the onboarding guides in the canonical Linux bundle and Debian
   package, with current checksums and source-commit provenance.
5. Build and verify the wheel, source archive, Linux bundle and
   `Architecture: all` Debian package for the supported Linux matrix.
6. Run local, hosted and operational gates before promoting `develop` to
   `main` and creating tag `v0.15.1`.

## Distribution Boundaries

- The canonical GitHub release may contain the complete Linux archive, its
  sidecar, wheel, source archive and `.deb` as separately verifiable assets.
- PyPI requires a separately approved upload or Trusted Publishing setup.
- An APT repository or Ubuntu PPA requires signing identity, repository
  hosting and source-package policy; a standalone `.deb` is not itself an APT
  channel.
- Snap classic confinement requires store review because the product invokes
  host tools, reads arbitrary project paths and manages user services.
- No external store account, package name or upload is created implicitly by
  this implementation task.

## Gates

- full tests and coverage at or above 80%;
- Ruff, mypy, shell syntax, package build and clean diff;
- Python 3.10, 3.11 and 3.12 matrix;
- clean release verifier, `.deb` verifier and `lintian`;
- disposable Debian 12, Ubuntu 22.04 and Ubuntu 24.04 package tests when the
  local container engine is available;
- strict doctor, schema integrity, hooks, controls and service stability after
  the authorized operational upgrade;
- green hosted Linux CI for the exact candidate commit;
- no `.env`, database, control state, webhook, token, session ID or local
  backup manifest in any public artifact.

## Promotion Boundary

Natural Availability Recovery E2E remains valuable long-running evidence, but
it must not be fabricated by consuming quota. It is not a source-code gate for
this patch release because the recovery mechanism predates the release and
the new dispatch audit fails closed. The release notes must retain that
evidence boundary instead of claiming an unobserved natural transition.
