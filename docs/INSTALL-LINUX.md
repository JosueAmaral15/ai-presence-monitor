# Linux Installation and Multi-Project Use

## Supported Installation

AI Presence Monitor 0.9.0 is distributed as a private Linux release bundle.
The bundle contains a wheel, source archive, configuration template, installer,
offline verifier, release manifest and `SHA256SUMS`.

Requirements:

- Linux;
- Python 3.10, 3.11 or 3.12 with `venv` and `pip`;
- a per-user installation, without `sudo`;
- optional user systemd for continuous monitor and Discord reply observer;
- optional Codex CLI with `codex queue` for native session input;
- optional PySide6 for the tray;
- optional X11, `xdotool` and `xclip` only for guarded GUI fallback.

Windows modules remain in the package but are not supported by this release and
stay disabled unless an operator explicitly enables the experimental runtime.

## Verify the Bundle

From the extracted bundle directory:

```bash
sha256sum -c SHA256SUMS
python3 verify_release.py .
```

The verifier checks every declared artifact, package name/version, required
Linux and preserved Windows modules, and a fresh offline wheel installation. It
uses an isolated temporary home, initializes SQLite, runs schema and doctor
checks, and proves two absolute project paths create distinct workers.

Do not install a bundle that records `source_dirty=true`, fails a checksum or
does not report the expected release version.

## Fresh Installation

Run the bundled installer:

```bash
./install-linux.sh \
  --wheel ./ai_presence_monitor-0.9.0-py3-none-any.whl
```

Default locations:

```text
runtime:  $XDG_DATA_HOME/ai-presence-monitor/venv
          or ~/.local/share/ai-presence-monitor/venv
command:  ~/.local/bin/ai-presence
config:   $XDG_CONFIG_HOME/ai-presence-monitor/.env
          or ~/.config/ai-presence-monitor/.env
database: <config directory>/data/presence.db with the bundled template
controls: $XDG_STATE_HOME/ai-presence-monitor/control.json
          or ~/.local/state/ai-presence-monitor
```

The installer:

- accepts only an existing local wheel;
- requires a supported Python version;
- installs with `--no-index --no-deps`;
- creates the command link without requiring a shell alias;
- installs the configuration template with mode `600` when absent;
- preserves an existing configuration;
- initializes the configured SQLite database;
- does not install services, hooks, tray autostart or automation permissions.

It refuses an existing runtime. Existing installations must use the
transactional updater rather than bypassing its backup and rollback contract.

## Configure and Validate

Edit the private configuration without posting its values in prompts or logs:

```bash
chmod 600 ~/.config/ai-presence-monitor/.env
ai-presence --version
ai-presence schema-status --json
ai-presence doctor --json --strict
```

Add Discord or Telegram integration only after local initialization succeeds.
Use separate Discord webhooks for point and alert channels. Remote Discord
questions additionally require a bot token, channel ID and user allowlist.

## Install Optional Components

Review every dry-run first:

```bash
ai-presence --dry-run install-codex-hook
ai-presence install-codex-hook

ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor

ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer
```

The generated hooks and services use the installed virtual-environment Python,
not the source checkout. Service installation is optional; CLI lifecycle
commands work without systemd.

For the tray, install PySide6 into the dedicated environment from a trusted
source, then run:

```bash
ai-presence tray --check
ai-presence tray
```

The base Linux product has no third-party runtime Python dependency. The tray
extra is intentionally separate and is not part of the offline base bundle.

## Use from Another Project

The monitor is installed once per user and reused by absolute project path:

```bash
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"

ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Current task" \
  --message "AI-worker started work"

# Codex hooks record meaningful activity while this worker is active.

ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Current task" \
  --message "AI-worker finished work"
```

Do not copy the monitor database into each project. Project-scoped worker IDs
are derived from canonical absolute paths and remain isolated in the shared
user database. Moving a project creates a new identity by design.

## Upgrade and Rollback

Keep the current installed wheel before every upgrade. Follow
[TRANSACTIONAL-UPGRADE.md](TRANSACTIONAL-UPGRADE.md):

```bash
ai-presence --dry-run upgrade \
  --package /absolute/path/new.whl \
  --rollback-package /absolute/path/current.whl \
  --json
```

Real upgrade and database-restoring rollback require explicit authorization.
Never retry an uncertain package or input operation automatically.
