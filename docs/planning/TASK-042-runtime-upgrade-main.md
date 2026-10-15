# Task 042 - Runtime 0.10.7 Upgrade and Main Promotion

## Goal

Install the validated Linux 0.10.7 candidate transactionally, prove that the
system tray and managed services remain stable, and promote the same private
Linux candidate from `develop` to `main` after all available gates pass.

## Scope

- validate authentic 0.10.5 rollback and 0.10.7 target wheels;
- run an upgrade dry-run before each real installation;
- perform one real upgrade, one manual rollback with database restoration and
  one final upgrade to 0.10.7;
- preserve the database, controls, Codex hooks and original managed-service
  state;
- restart exactly one tray instance with the installed runtime;
- exercise the installed desktop-notification observer without using the real
  operational database;
- rerun the complete local, supported-Python and clean-release gates;
- record the hosted Quality result honestly and apply only the explicitly
  authorized, version-specific private Linux exception;
- fast-forward the validated history through `develop` and `main` without a
  tag, release or public artifact publication.

## Operational Evidence

- Target wheel SHA-256:
  `d0433e5d3fb38f98ae14a0de1d5e05578475d205c55753fca959cd34f9245260`.
- Rollback wheel SHA-256:
  `71b9f1d931e485bee01e057e2b6f8d7a94e636c0a7cf9a62838b101160f0810c`.
- The initial dry-run returned `would_upgrade` from 0.10.5 to 0.10.7.
- The first transaction completed, strict doctor returned only `ok` checks,
  the schema was current and integral, and both managed services were active.
- The manual rollback returned `manually_rolled_back`, restored the database,
  returned the runtime to 0.10.5 and preserved service health.
- A second dry-run returned `would_upgrade`; the final transaction completed
  and left the installed runtime at 0.10.7.
- `control.json` and Codex hook files retained their original SHA-256 values
  and private mode `0600` across the complete cycle.
- Monitor, Discord reply observer and tray are active with one PID each and
  `NRestarts=0`; `tray --check` reports the Linux Mint tray as available.
- An installed-runtime smoke used an isolated temporary database. Three new
  lifecycle/Stop/red-alert events produced three typed notices and no replay
  on the next poll.

## Local Gate Evidence

- 342 tests passed with 86% aggregate coverage.
- Ruff, mypy, compileall, shell syntax, package build and `git diff --check`
  passed.
- The same 342 tests passed on Python 3.10, 3.11 and 3.12.
- The clean 0.10.7 bundle built from `b767a7a` passed checksum, manifest,
  isolated-installation, launcher and two-project verification.
- A final clean release gate must be rerun after this planning record is
  committed so the promoted candidate itself is verified.

## Hosted CI Exception

Hosted Quality run
[`38748215221`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/38748215221)
targets `develop` commit `b767a7a`. Its Python 3.10, 3.11 and 3.12 Linux jobs
each executed zero steps. GitHub annotated the jobs with an account-level
billing lock. This is a failed external gate and supplies no test evidence.

The owner requested the necessary work for the 0.10.7 main promotion after
stating that the billing lock cannot currently be resolved. The private Linux
candidate may therefore use the version-specific exception recorded in
`docs/DECISIONS.md` only after the final exact-candidate local and operational
gates pass.

## Stop Conditions

- Any uncertain upgrade, rollback or input result stops the task; no blind
  retry is allowed.
- Any schema, strict-doctor, service, tray, checksum, quality, matrix or
  release-verification failure blocks promotion.
- Divergence that prevents fast-forward-only promotion blocks the operation.
- The exception does not authorize a tag, GitHub release, public artifact,
  Windows production support or a future version.

## Rollback

The validated 0.10.5 wheel and private transaction manifests remain outside
Git. If the installed 0.10.7 runtime fails later, stop the tray, dry-run
`rollback-upgrade` against the latest completed manifest, obtain explicit
one-operation authorization, restore the database snapshot and restart the
tray only after strict health checks pass. Source rollback uses a new revert
commit; shared branch history is never rewritten.
