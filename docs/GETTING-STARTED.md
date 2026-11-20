# Getting Started on Linux

This guide takes a first-time user from a downloaded release to a healthy
local worker. Start with local monitoring. Add Discord, automatic continuation
and other integrations only after the base installation passes its checks.

## What the Product Does

AI Presence Monitor records when an AI worker starts, performs meaningful
activity and finishes. It can evaluate inactivity protocols, show desktop or
Discord alerts, receive correlated Discord answers and, when explicitly
enabled, send a prompt to an exact Codex session.

It does not judge work quality and does not assume that a running process is
productive. Automatic input is disabled until the operator enables the
corresponding controls.

## Choose One Installation Method

Use the per-user wheel bundle when you want the tray and the easiest rollback.
It needs no `sudo` and is the recommended default.

Use the `.deb` when you want the CLI installed under `/usr/bin` and managed by
APT. The `.deb` deliberately does not configure your account, start services
or install optional PySide6.

Do not install both methods without checking which command wins:

```bash
command -v ai-presence
readlink -f "$(command -v ai-presence)"
```

## Verify the Download

From the extracted canonical release directory:

```bash
sha256sum -c SHA256SUMS
python3 verify_release.py .
```

For a standalone Debian package, keep its `.sha256` sidecar beside it:

```bash
sha256sum -c ai-presence-monitor_0.15.1-1_all.deb.sha256
python3 verify_deb.py \
  ai-presence-monitor_0.15.1-1_all.deb \
  --expected-version 0.15.1
```

Stop if a checksum, source commit or offline verifier fails.

## Install

### Recommended per-user installation

```bash
./install-linux.sh \
  --wheel ./ai_presence_monitor-0.15.1-py3-none-any.whl
```

### Debian, Ubuntu or Linux Mint package

```bash
sudo apt install ./ai-presence-monitor_0.15.1-1_all.deb
/usr/bin/ai-presence --version
```

The Debian package installs the guides under:

```text
/usr/share/doc/ai-presence-monitor/
```

## First Health Check

Run these commands before adding integrations:

```bash
ai-presence --version
ai-presence schema-status --json
ai-presence doctor --json --strict
```

A fresh installation may report warnings for hooks, services, Codex CLI or
tray autostart because those components are optional. Database, environment,
runtime and platform checks must not report errors.

## Create or Review Configuration

The per-user installer creates a private template when no configuration
exists. For the Debian package:

```bash
mkdir -p "$HOME/.config/ai-presence-monitor"
install -m 600 \
  /usr/share/ai-presence-monitor/.env.example \
  "$HOME/.config/ai-presence-monitor/.env"
```

Review it with a local editor. Never paste the complete file into chat, commit
it or send webhook and bot tokens in command arguments. A local-only setup can
leave Discord and Telegram values empty.

Initialize only after confirming `PRESENCE_DB_PATH` points to the intended
location:

```bash
ai-presence init
ai-presence schema-status --json
```

## Start One Project Worker

In the project that the AI is working on:

```bash
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"

ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Describe the current task" \
  --message "Work started"
```

Protocol 2 is the recommended default for coding agents. It records start and
finish publicly while Codex hooks record meaningful internal activity.

When the work ends:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Describe the current task" \
  --message "Work finished"
```

Always pass the absolute project path. Different projects receive independent
worker identities and automation settings.

## Add Optional Components One at a Time

Review every dry-run before installation:

```bash
ai-presence --dry-run install-codex-hook
ai-presence install-codex-hook

ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor

ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer

ai-presence --dry-run install-background-service --component prompt-rule-observer
ai-presence install-background-service --component prompt-rule-observer
```

After each component:

```bash
systemctl --user --no-pager status UNIT_NAME
ai-presence doctor --json --strict
```

## Optional Tray

The wheel installation can add PySide6 inside its dedicated environment:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install PySide6
ai-presence tray --check
./start-tray.sh
```

The tray is where a human enables automation, chooses exact Codex sessions,
creates Prompt Rules and Availability Recovery rules, and opens agent chat.
The AI worker may disable its own project's automation but may not enable or
redirect another profile.

## Optional Discord

Use separate channels and webhooks for attendance and alerts. Remote questions
need a Discord application bot, channel ID and allowed user IDs in addition to
webhooks. Configure one integration at a time, restart only the affected
service and inspect its journal before enabling automatic input.

## Automatic Input Safety

Prompt Rules and Availability Recovery require both **Enable task automation**
and **Enable native Codex input** for the selected profile. Use an exact
session. A transport start is preliminary; later canonical session activity is
required for confirmation.

Inspect sanitized history without exposing prompt text or raw session IDs:

```bash
ai-presence dispatch-audit --profile WORKER_ID --limit 20 --json
```

## Common Problems

### The command is not found

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --version
```

If that works, ensure `~/.local/bin` is in `PATH` or use the absolute command.

### The wrong installation runs

Compare `command -v`, `readlink -f` and `/usr/bin/ai-presence --version`.
Do not remove either installation until you have a rollback plan.

### A service is failed

```bash
systemctl --user status UNIT_NAME --no-pager -l
journalctl --user-unit UNIT_NAME -n 80 --no-pager
```

Do not repeatedly restart a service before reading its first failure.

### Schema is newer than the runtime

Do not lower `PRAGMA user_version` or delete tables. Install the matching newer
runtime through the transactional upgrade procedure or restore a reviewed
pre-upgrade database snapshot with explicit authorization.

### The tray does not appear

Run `ai-presence tray --check` inside the graphical desktop session. Verify
PySide6 and inspect `journalctl --user-unit ai-presence-tray-session.service`.

### Disk space is low

Stop release work before SQLite or package tools fail. Identify large paths,
then obtain operator approval before deleting personal caches or artifacts.

## Next Reading

- [Linux installation](INSTALL-LINUX.md)
- [Debian package](INSTALL-DEB.md)
- [Environment configuration](CONFIGURANDO-ENV.md)
- [Tool usage for humans and AI workers](USO-COMO-FERRAMENTA.md)
- [System tray](SYSTEM-TRAY-NATIVE-INPUT.md)
- [Transactional upgrade](TRANSACTIONAL-UPGRADE.md)
- [Support and compatibility](SUPPORT.md)
