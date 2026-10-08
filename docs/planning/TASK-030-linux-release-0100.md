# Task 030 - Private Linux Release 0.10.0

## Objective

Produce a reproducible private Linux 0.10.0 release from the exact validated
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

- Exact artifact source: `d54842b391f5e1311a14449a66f242b6a19ae431`;
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
  `09532662983a0c73a0766a06f198ffc2134b8e3bdf59e5b99c67205e50aa53b2`.
- Candidate sdist SHA-256:
  `1cbf10fcb2ac710603ef82601a7d9d27fe827887f4913831a8888001169589f9`.
- Canonical archive SHA-256:
  `3d6a52a8e852fd7236849d446b243870b7bf7d90ef6ca6d8e792cbdcc5bbfe65`;
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
- The exception is limited to private Linux release 0.10.0. The hosted Quality
  failures executed zero steps and remain an external non-pass rather than test
  evidence; the local and real gates below replace that evidence only for this
  private release.
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

## Phase 4 - Tag and Private Prerelease

After the operational gate and a version-specific private CI exception are
both recorded, request explicit publication authorization. Then:

1. promote any release-record commit by fast-forward to `develop` and `main`;
2. create and push annotated tag `v0.10.0` on the exact release commit;
3. create a private GitHub prerelease;
4. upload the canonical archive, sidecar and approved supplementary assets;
5. download the canonical files into a fresh directory;
6. verify the sidecar, `SHA256SUMS`, offline verifier, tag, manifest and source
   commit agreement.

## Completion Evidence

Record exact commit IDs, hashes, artifact sizes, transaction manifests,
service-state comparisons, health summaries, tag and release URL in this plan
and `docs/TASKS.md`. Do not call 0.10.0 released until every required item is
complete.
