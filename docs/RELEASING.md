# Private Linux Release Process

## Candidate Requirements

Use a dedicated task branch from current `develop`. The root `README.md`
remains English. Release code, runtime constant and documentation must identify
the same semantic version.

The release builder refuses a dirty worktree by default and binds the bundle to
the exact Git commit. `--allow-dirty` exists only for development validation;
such a bundle records `source_dirty=true` and the normal verifier rejects it.

## Local Candidate Gate

From a clean candidate commit:

```bash
./scripts/release-gate.sh "$PWD/dist/release-0.9.0"
```

This executes:

1. compilation, full tests, coverage, Ruff, mypy, shell syntax, package build
   and diff checks;
2. tests on locally installed Python 3.10, 3.11 and 3.12;
3. a clean wheel and sdist build without package-index access;
4. release manifest and SHA-256 generation;
5. offline verification in a fresh virtual environment and temporary home;
6. two-project identity isolation.

The output directory must not already exist. This prevents stale artifacts
from being mixed into a release bundle.

## Hosted CI

The `Quality` workflow defines Ubuntu jobs for Python 3.10, 3.11 and 3.12.
Windows is manual, experimental and non-blocking. A zero-step failure caused by
account billing is an external non-pass, not test evidence.

A private Linux release may bypass that external gate only through a new,
version-specific documented user decision after all local and real integration
gates pass. An exception for 0.8.0 does not automatically cover 0.9.0.

## Operational Gate

Preserve the authentic prior wheel and record its checksum. Run the updater
dry-run before requesting authorization. A real gate must prove:

- upgrade from the installed prior version;
- schema and doctor health;
- original service-state restoration;
- controls and hooks preserved;
- one manual rollback with database restoration;
- final upgrade back to the candidate;
- any release-required external integration with unique correlation.

Do not retry uncertain transactions or input. Do not tag while the machine is
left on the rollback version.

## Promotion and Tag

After every gate passes on the exact candidate:

```bash
git switch develop
git merge --ff-only TASK_BRANCH
git push origin develop

git switch main
git merge --ff-only develop
git push origin main

git tag -a v0.9.0 -m "AI Presence Monitor 0.9.0"
git push origin v0.9.0
```

Create a canonical archive containing the complete verified bundle directory
and publish a separate SHA-256 sidecar for that archive. This preserves the
required `.env.example` filename; GitHub renames a leading-dot file when it is
uploaded individually. Users must verify the sidecar, extract the archive, then
run both `sha256sum -c SHA256SUMS` and `python3 verify_release.py .` inside it.

Individual bundle files may be attached as supplementary assets, but they are
not the canonical downloadable set. Do not attach a real `.env`, SQLite
databases, control state, service logs or local backup manifests. After upload,
download the canonical archive into a fresh directory and repeat both checksum
layers and the isolated verifier.

Confirm the release tag, main commit and `release-manifest.json` source commit
agree at publication before declaring the release complete.
