# Task 030 - Public Linux Prerelease 0.10.0

## Objective

Produce a reproducible Linux 0.10.0 prerelease from the exact validated
source, prove transactional upgrade and rollback from the installed authentic
0.9.0 runtime, then publish a canonical archive whose contents can be verified
offline.

## Boundaries

- Linux is the only supported runtime for this release.
- Windows code remains preserved, disabled and unsupported.
- The failed Discord reply observer is diagnosed but independent; this task
  does not restart it or consume pending replies.
- Building and verifying local artifacts does not authorize installation, tag
  creation, push, GitHub release creation or upload.
- Each real upgrade, rollback restoration and external publication step needs
  explicit authorization at its execution boundary.
- No `.env`, database, control state, logs or local backup manifest may enter
  the release bundle.

## Initial Preflight

- `main`, `develop`, `origin/main` and `origin/develop` identify commit
  `6b2bbb7` before release-planning changes.
- Installed runtime: 0.9.0.
- Database schema and integrity: healthy and current.
- Main monitor: active.
- Five Codex hooks and `codex queue`: available.
- Tray autostart: configured.
- Reply observer: failed and out of scope.
- The GitHub Quality run for `6b2bbb7` failed all Linux jobs with zero steps;
  it supplies no hosted test evidence.
- The feature candidate passed 312 tests on Python 3.10, 3.11 and 3.12,
  86% aggregate coverage, Ruff, mypy, compileall, shell syntax, package build,
  tray smoke and a real isolated prompt-rule E2E.

## Phase 1 - Clean Candidate

1. Commit this version-specific plan on a task branch from `develop`.
2. Run `scripts/release-gate.sh` into a new ignored output directory.
3. Verify the manifest version, source commit, clean-source flag and artifact
   checksums.
4. Create the canonical `.tar.gz` plus a separate `.sha256` sidecar without
   changing bundle contents.

## Phase 2 - Prior Runtime and Dry Run

1. Retrieve the authentic 0.9.0 wheel from the existing private prerelease.
2. Verify its published digest
   `0399782b78b7ab69175230d6116b94f1f1a10ba21594795711aded49e114bd53`.
3. Preserve service, hook, control and database state before the transaction.
4. Run the 0.10.0 updater dry-run with the authentic 0.9.0 wheel as rollback
   package.

## Phase 1 and 2 Evidence

- Exact artifact source: `447f3091cf676d347a628207a36cb3eae1d75094`;
  the release manifest records `source_dirty=false`.
- The first bundle smoke exposed that the isolated `doctor` still observed the
  host's failed reply-observer unit. Commit `ced1f14` made release verification
  require the intrinsic runtime, platform, environment, database and control
  checks while treating hooks, services, Codex and tray state as host-dependent.
- A second preflight found that the installed 0.9.0 updater would apply the same
  host-state coupling during a real transaction. Commit `d54842b` added a
  bundled candidate-side bootstrap and the same fail-closed intrinsic checks
  to transactional postflight.
- The final complete gate passed 315 tests, 86% aggregate coverage, Ruff, mypy,
  compileall, shell syntax, package build and Python 3.10, 3.11 and 3.12.
- Offline installation, schema, command, updater help and two-project isolation
  smokes passed from the built wheel.
- Candidate wheel SHA-256:
  `acef4d3a47b84b8692c935b0d30d9bef85a535adc897b981c690e7ab07debde6`.
- Candidate sdist SHA-256:
  `89c66601155672f7272e14d948998509c1f40c64fab715f4129c282f8cc91efb`.
- Canonical archive SHA-256:
  `106d0aaf853381826d63416b61712cdd406c4602eb9088d79da3eb23fc4a3144`;
  its listing includes the complete bundle, `.env.example` and
  `upgrade-linux.sh`.
- The authentic private-release 0.9.0 wheel was downloaded and matched its
  published SHA-256:
  `0399782b78b7ab69175230d6116b94f1f1a10ba21594795711aded49e114bd53`.
- The candidate-side bootstrap, using the dedicated installed 0.9.0 Python,
  returned `status=would_upgrade`,
  `from_version=0.9.0`, `to_version=0.10.0` and no manifest during dry-run.
- The dry-run did not change the installed runtime or restart the failed reply
  observer.

## Phase 3 - Authorized Operational Gate

After explicit authorization immediately before the transaction:

1. upgrade 0.9.0 to the exact candidate wheel;
2. verify version, schema, doctor, controls, hooks and service restoration;
3. perform one authorized rollback with database restoration;
4. verify the authentic 0.9.0 runtime and restored state;
5. upgrade once more to the same 0.10.0 wheel;
6. repeat health checks and leave the machine on 0.10.0.

An uncertain transaction is a stop condition and must not be retried
automatically.

## Phase 3 Evidence

- On 2026-10-08, the user explicitly approved both the version-specific private
  CI exception and the real upgrade, database-restoring rollback and final
  upgrade transaction.
- The exception was initially limited to a private Linux 0.10.0 release. The
  hosted Quality failures executed zero steps and remain an external non-pass
  rather than test evidence. On 2026-10-09, the user separately authorized a
  public prerelease with that limitation disclosed; the local and real gates
  below replace hosted evidence only for this prerelease.
- Pre-transaction state was 0.9.0 with schema 1 current and integral, five Codex
  hooks, `codex queue`, tray autostart and the main monitor healthy. The reply
  observer was already failed and was not restarted or consumed.
- The first candidate-bootstrap upgrade completed in
  `upgrade-0.9.0-to-0.10.0-20261008-190256-bc0a5ef5/manifest.json`. Its private
  mode-0600 manifest records only the main monitor as previously active and the
  exact target and rollback wheel hashes listed above.
- Post-upgrade checks confirmed 0.10.0, healthy current schema, all intrinsic
  doctor checks, five hooks, `codex queue`, tray autostart and restored main
  monitor service. The known reply-observer error remained unchanged.
- The rollback dry-run returned `would_rollback`; the authorized rollback then
  returned `manually_rolled_back`, restored 0.9.0 and its database snapshot,
  and left schema, controls, hooks and original service state healthy. The main
  monitor resumed normal writes after restoration, so later database file
  hashes are not expected to remain byte-identical to the stored snapshot.
- The final candidate-bootstrap upgrade completed in
  `upgrade-0.9.0-to-0.10.0-20261008-190405-ce260738/manifest.json` and left the
  installed runtime on 0.10.0.
- Control SHA-256 remained
  `7a1b91a82d02de2266d1887e35b13e99207f9adea140d76fbc5c8cb973a80c39`;
  hook SHA-256 remained
  `f95963bf0416a93dbf93c1da771553758aadd7c0068b15e31eb67fe3942e703b`.
- The tray process was cleanly restarted after final upgrade under the
  collectable current-session unit `ai-presence-tray-session.service`, so it
  loaded installed 0.10.0 code; the existing XDG entry remains responsible for
  later graphical logins. No transaction or input was retried automatically.

## Publication Preflight Correction

The operational gate above validated the executable candidate from `d54842b`.
Before publication, review found that current installation and support guides
still named 0.9.0 as the distributed release. Publishing that tag would leave
0.10.0 package metadata and source documentation inconsistent.

The current guides must identify 0.10.0 and the bundled upgrade bootstrap, then
the clean bundle, hashes and exact source commit must be regenerated. Because
the root README is package metadata, this changes the wheel bytes even though
runtime code is unchanged. The rebuilt exact wheel therefore needs a final
bounded installed-runtime validation before promotion and publication. No old
artifact or hash may be reused.

Commit `447f309` completed that correction. Its clean release gate passed 315
tests, 86% aggregate coverage, Ruff, mypy, compileall, shell syntax, build,
Python 3.10/3.11/3.12 and the isolated bundle verifier. All 40 packaged Python
modules are byte-identical to the operationally validated `d54842b` wheel; only
release documentation and package metadata differ. The final hashes are the
ones recorded in Phase 1 and 2 Evidence above.

On 2026-10-09, the user authorized one final rollback and upgrade with the
rebuilt exact wheel. The stored transaction was rolled back to authentic 0.9.0,
including its database snapshot, and then upgraded exactly once with the
candidate-side bootstrap. The final transaction completed in
`upgrade-0.9.0-to-0.10.0-20261009-053347-9abee693/manifest.json`; its private
mode-0600 manifest records target SHA-256
`acef4d3a47b84b8692c935b0d30d9bef85a535adc897b981c690e7ab07debde6`
and rollback SHA-256
`0399782b78b7ab69175230d6116b94f1f1a10ba21594795711aded49e114bd53`.
The installed runtime is 0.10.0, schema 1 is current and integral, the main
monitor is active, and controls and hooks retain their recorded hashes. The
known failed reply observer remained untouched. The current-session tray was
restarted successfully from the installed 0.10.0 runtime. No transaction was
retried automatically.

## Phase 4 - Tag and Public Prerelease

After the operational gate and a version-specific CI exception are both
recorded, request explicit publication authorization. Then:

1. promote any release-record commit by fast-forward to `develop` and `main`;
2. create and push annotated tag `v0.10.0` on the exact release commit;
3. create the authorized GitHub prerelease with its support limits disclosed;
4. upload the canonical archive, sidecar and approved supplementary assets;
5. download the canonical files into a fresh directory;
6. verify the sidecar, `SHA256SUMS`, offline verifier, tag, manifest and source
   commit agreement.

## Completion Evidence

On 2026-10-09, repository preflight showed that the GitHub repository was
public. Publication stopped before release creation, and the user explicitly
authorized a public prerelease. The release notes disclose Linux-only support,
disabled/unsupported Windows operation, the hosted CI non-pass and the local
and operational evidence that replaced it for this prerelease only.

- `develop` and `main` were fast-forwarded to exact artifact source commit
  `447f3091cf676d347a628207a36cb3eae1d75094` before tagging.
- Annotated tag `v0.10.0` resolves to that same source commit.
- Public prerelease:
  `https://github.com/JosueAmaral15/ai-presence-monitor/releases/tag/v0.10.0`.
- Canonical archive: 345657 bytes, SHA-256
  `106d0aaf853381826d63416b61712cdd406c4602eb9088d79da3eb23fc4a3144`.
- The first downloaded sidecar exposed a build-local `dist/` path. It was
  corrected to the archive basename, replaced once, and downloaded again.
- Portable sidecar: 106 bytes, SHA-256
  `5feefeb6720c8dc5694477617956e20d50af2043e4c2dd57e87cee5ab9a9cbf6`.
- The fresh download passed the outer sidecar, every internal `SHA256SUMS`
  entry and `python3 verify_release.py .`; its clean manifest identifies
  version 0.10.0 and source commit `447f3091cf676d347a628207a36cb3eae1d75094`.
- The tag target, hosted asset digest and size, downloaded bytes and bundle
  manifest all agree.

Task 030 is complete. Hosted CI must be restored before a stable public
release; the explicit exception applies only to this prerelease.
