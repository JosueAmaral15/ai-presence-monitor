# Linux Distribution Channels

This document separates build readiness from external publication. A verified
artifact can be uploaded to a GitHub release immediately after release gates,
but package indexes and stores impose additional identity, signing and review
requirements.

## Canonical Source of Truth

The canonical release is the complete Linux archive produced from the tagged
commit. It contains the wheel, source archive, `.deb`, checksum files, offline
verifiers, configuration template, installer, upgrade bootstrap, licence,
notices and first-run guides.

Every other channel must identify the same version and source commit. Do not
rebuild an artifact after tagging and publish it under the same version.

## GitHub Releases

Recommended first public channel:

- canonical complete Linux archive plus its SHA-256 sidecar;
- wheel and source archive as supplementary assets;
- `.deb` and its SHA-256 sidecar;
- release notes with supported Linux/Python versions and known limitations.

After upload, download the canonical archive into a fresh directory and repeat
both checksum layers and `verify_release.py`. Verify that tag, `main` commit and
release manifest source commit are identical.

## Standalone Debian Package

The release `.deb` can be attached to GitHub and installed with:

```bash
sudo apt install ./ai-presence-monitor_0.15.1-1_all.deb
```

This is an official project artifact, but it is not an APT repository. Users
must download each update themselves. The package is `Architecture: all`, uses
system Python 3.10 through 3.12 and leaves user configuration untouched.

## Project APT Repository

An APT repository provides `apt update` and normal upgrade discovery. It needs:

1. a dedicated OpenPGP signing key controlled by the project owner;
2. repository hosting with HTTPS;
3. `Packages`, `Release`, `InRelease` and by-hash metadata;
4. a documented key rotation and revocation procedure;
5. automated publication from an exact tagged artifact;
6. install, upgrade and rollback tests against the published repository.

Tools such as `reprepro` or `aptly` can generate repository metadata. GitHub
Pages may host static APT content, but availability, key management and cache
semantics remain the owner's responsibility. Never commit the private signing
key or inject it into an untrusted pull-request workflow.

## Ubuntu PPA

A Launchpad PPA requires a Launchpad account, an uploaded OpenPGP public key
and a signed Debian source package. The current binary `.deb` is not sufficient
for PPA publication. Before preparing a source package, review Debian source
layout, build dependencies, reproducible build behavior and Launchpad policy.

PPAs target Ubuntu releases. Linux Mint users can often consume the matching
Ubuntu base repository, but that compatibility must be documented and tested.

## Debian Official Archive

Inclusion in Debian is a community review process, not a file upload. Typical
steps include:

- file an Intent To Package (ITP) bug;
- produce policy-compliant source packaging;
- pass current `lintian` and reproducibility checks;
- find a Debian sponsor or maintainer;
- address review, copyright and dependency questions;
- maintain the package over time.

The project currently builds a safe standalone upstream `.deb`; it does not
claim Debian archive acceptance.

## PyPI

PyPI is appropriate for the base Python CLI and per-user virtual-environment
installation. Recommended publication uses Trusted Publishing from a protected
GitHub environment rather than a long-lived API token.

Before first upload:

1. confirm the project name is available through the operator's account;
2. add package description links and support/security URLs;
3. build wheel and sdist from the exact tag;
4. run `twine check` or the equivalent metadata validation;
5. publish to TestPyPI first and perform an isolated install;
6. approve the production upload separately.

PyPI cannot install user systemd services or create private configuration.
Those remain explicit post-install steps.

## Snap Store

The monitor interacts with arbitrary project paths, Codex CLI, user systemd,
desktop notifications and optional X11 tools. Strict confinement is therefore
unlikely to expose the required host surface. A classic-confinement snap needs
manual store approval and a clear justification.

Prepare a snap only after deciding whether a reduced strictly confined edition
is useful. Do not promise feature parity before testing services, tray, Codex
input and configuration paths inside the selected confinement model.

## Flathub and AppImage

Flathub is optimized for sandboxed desktop applications. The current product
is primarily a CLI and user-service integration tool, so filesystem, systemd
and external CLI access conflict with normal sandbox expectations. A future
desktop companion could be suitable, but packaging the current monitor as a
Flatpak would require a reduced architecture and explicit portals.

AppImage can package a GUI but does not naturally manage the CLI, hooks or user
services. It is not a priority over the wheel and `.deb` channels.

## Homebrew on Linux

A Homebrew formula is possible for the Python CLI, but it needs a stable source
archive URL and checksum, formula tests and a clear policy for optional PySide6
and systemd integration. Consider it after GitHub, PyPI and APT delivery are
stable.

## Recommended Publication Order

1. GitHub release with canonical archive and `.deb`.
2. TestPyPI, then PyPI after isolated installation succeeds.
3. Signed project APT repository or Launchpad PPA.
4. Snap only after confinement review.
5. Debian archive, Homebrew or a separate desktop companion as longer-term
   channels.

Each external upload requires a channel-specific approval. Building and
verifying artifacts does not authorize account creation, name reservation,
signing-key generation or publication.

## Product UX Roadmap

The most useful next improvements for first-time users are:

- a non-destructive `ai-presence setup` wizard that writes only reviewed local
  configuration and shows the resulting paths;
- a tray onboarding checklist with runtime, database, hooks, services and
  Codex connectivity states;
- direct links from tray errors to the relevant local guide section;
- an exportable sanitized support report with no tokens, webhooks, prompt text
  or raw session identifiers;
- desktop launchers installed by an optional user command, not by package
  maintainer scripts;
- translations kept separate from command and state identifiers.

These are product enhancements, not prerequisites for the verified `0.15.1`
CLI and Debian release.
