# Support and Compatibility Policy

## Product Status

AI Presence Monitor 0.13.0 is a Linux prerelease candidate. It is suitable for
controlled local evaluation across multiple projects and Linux computers after
the documented installation and verification gates pass. It is not a hosted
service, public SaaS, package-index distribution, stable release or multi-tenant
security boundary.

## Supported Platform

| Area | Supported contract |
|---|---|
| Operating system | Linux |
| Python | CPython 3.10, 3.11 and 3.12 |
| Package | Dedicated per-user wheel or verified Debian package |
| Database | Local SQLite, schema version 3 |
| Background runtime | User systemd when available; direct CLI otherwise |
| Codex activity | Installed hooks and explicit lifecycle commands |
| Native Codex input | Codex CLI providing `codex queue` |
| Discord | HTTPS webhooks; bot polling only when explicitly configured |
| Telegram | Optional Bot API notification integration |
| Tray | Optional PySide6 desktop extra |
| GUI fallback | Optional X11 only; disabled by default |

Linux Mint 21.3 is the current real workstation baseline. Debian 12, Ubuntu
22.04 and Ubuntu 24.04 package installation, CLI, SQLite and removal are
validated in disposable containers. Ubuntu-compatible hosted
jobs are defined but are not considered passing while GitHub executes zero
steps because of the account billing lock. Other Linux distributions are
supported at the base CLI level when they provide a supported CPython, SQLite
and standard POSIX user environment. Distribution-specific service, desktop or
audio behavior is best effort until validated there.

## Unsupported or Experimental

- Windows runtime is preserved but disabled and unsupported for this release.
- Wayland GUI mouse/keyboard fallback is unsupported. Native `codex queue`
  remains the preferred transport when available.
- Python 3.9 and Python 3.13 or newer are outside the 0.13.0 support contract.
- Shared multi-user databases and containers are not supported deployment
  targets; containers are package-compatibility test environments only.
- Public Internet endpoints, inbound web servers and automatic package
  downloads are not part of the product.
- A hook, transport state or timer does not prove useful AI work.

## Version and Data Compatibility

- Package and runtime versions must match exactly.
- A runtime refuses a SQLite schema newer than it understands.
- Schema migrations are additive unless a future release explicitly documents
  otherwise.
- Supported upgrade is sequential from the immediately previous validated
  release with its exact rollback wheel.
- The transactional updater preserves both wheels, a database snapshot,
  service state and checksums before mutation.
- Manual database rollback may discard newer events and requires explicit
  acknowledgement.
- Backups and release bundles are user-owned local files and must not contain
  `.env` secrets.

## Release Support

The current release and its immediate rollback release are retained for
controlled operation. A release is supported only when:

1. the source commit is clean and identified in the release manifest;
2. source quality and supported Python matrix pass;
3. bundle hashes and isolated installation verify;
4. required real integrations pass with unique evidence;
5. the installed runtime and services pass postflight;
6. `develop`, `main`, tag and release artifacts identify the same candidate.

There is no response-time SLA. Operational defects should include sanitized
version, command exit status, schema status and doctor output. Never attach the
real `.env`, database, tokens, webhooks, prompts or message contents.

## End of Support

A release leaves normal support when a newer release is validated and its
rollback window no longer requires the older version. Keep any wheel and
database snapshot needed for an active transaction until the newer release has
remained stable and the operator explicitly archives or removes them.
