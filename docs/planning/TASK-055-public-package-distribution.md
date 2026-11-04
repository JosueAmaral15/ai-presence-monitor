# Task 055 - Public Package Distribution

## Goal

Prepare AI Presence Monitor for public distribution through a canonical GitHub
release and, in later independently approved steps, PyPI, Snap Store and an APT
repository or Ubuntu PPA.

## Current boundary

The repository is public and project-owned source is licensed under
Apache-2.0. Python and Debian package metadata use the same licence, and the
previous untraceable MP3 has been replaced by an original reproducible WAV.
No upload, package-name reservation, store registration or visibility change
belongs to this task without a separate approval at that external boundary.

## Plan

1. Audit source ownership, bundled assets and runtime dependency licences.
2. Record the owner's licence decision and add matching repository, Python and
   Debian metadata in one reviewable change.
3. Rebuild the canonical source, wheel, Linux archive and Debian package from a
   clean tagged commit; verify checksums and clean installation.
4. Prepare a PyPI project description and trusted-publishing workflow without
   uploading it.
5. Prepare a Snap recipe. Because the monitor invokes host tools, observes
   user services and works with arbitrary projects, assume classic confinement
   requires store review unless the implementation proves strict confinement.
6. Prepare an APT/PPA source package and signing/runbook. Treat official Debian
   or Ubuntu archive inclusion as a separate, longer review process.
7. Publish channels one at a time, retaining rollback and provenance evidence.

## Gates

- licence and dependency audit has no unresolved distribution conflict;
- package metadata agrees across all formats;
- quality gate, Python matrix and clean-install tests pass;
- generated artifacts contain `.env.example` but no `.env`, token or webhook;
- each external upload has explicit approval and is verified after publication.
