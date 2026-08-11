# AI Presence Monitor

[Portuguese documentation](README.pt-BR.md)

AI Presence Monitor is a local worker-presence monitor for AI coding agents.
It records lifecycle and activity evidence in SQLite, evaluates configurable
inactivity protocols, and sends alerts through Discord and optionally Telegram.

The project also provides:

- passive Codex activity observation through hooks;
- per-project and per-session worker identities;
- work-hour alert policies;
- remote Discord questions with an optional guarded GUI fallback;
- scheduled `continue` input for the Codex GUI;
- one-shot red alerts with a bounded local alarm;
- native operational adapters for Linux and Windows.

## Presence Protocols

### Protocol 1: periodic public check-in

The AI worker must publicly signal that it is still working every five minutes.
The point channel receives these heartbeat messages.

Alert thresholds:

- yellow: 7 minutes without a new signal;
- orange: 15 minutes without a new signal;
- red: 30 minutes without a new signal.

### Protocol 2: lifecycle plus observed activity

The AI worker publicly signals only when work starts and finishes. During the
task, silent `touch` events or Codex hooks update the local activity clock
without posting to the point channel.

Alert thresholds:

- yellow: 5 minutes without activity;
- orange: 10 minutes without activity;
- red: 15 minutes without activity.

Yellow and orange alerts may repeat at a configured interval. A red alert is
sent only once per continuous inactivity episode. A valid `start`, `heartbeat`,
`touch`, or Codex observation rearms red alerts for a future episode.

## Documentation

Detailed operational documentation is currently available in Portuguese:

- [Documentation index](docs/INDEX.md)
- [Environment setup](docs/CONFIGURANDO-ENV.md)
- [Environment and architecture guide](docs/ENVIRONMENT-GUIDE.md)
- [Integrated Codex continue command](docs/CONTINUE-CODEX.md)
- [AI worker command protocol](docs/AI-WORKER-COMMAND-PROTOCOL.md)
- [Portability](docs/PORTABILIDADE.md)
- [Remote Discord responses](docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md)
- [Security checklist](docs/security/SECURITY.md)
- [Rollback procedures](docs/rollback/ROLLBACK.md)

The Portuguese version of this README is preserved in
[README.pt-BR.md](README.pt-BR.md).

## Requirements

- Python 3.10, 3.11, or 3.12;
- Linux or Windows for the complete local integration family;
- on Linux: `/proc`, GNU `timeout`, and optionally systemd/X11/`xdotool`/`xclip`;
- on Windows: an interactive unlocked desktop for GUI input and Task Scheduler
  for optional continuous execution.

Linux has no third-party runtime Python dependency. On Windows, `pip` installs
the platform-neutral `tzdata` package because the standard library does not
ship the IANA time-zone database there.

## Installation

Recommended isolated installation:

```bash
python3 -m venv "$HOME/.local/share/ai-presence-monitor/venv"
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install /path/to/ai-presence-monitor
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
```

To expose the installed command in the current user's `PATH`:

```bash
./scripts/install-user-command.sh
ai-presence --help
```

Windows PowerShell installation, without administrator privileges:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\install-user-command.ps1
& "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\ai-presence.exe" --help
```

For development directly from the checkout:

```bash
cd /path/to/ai-presence-monitor
python3 main.py
```

The interactive menu can create the environment file, initialize the database,
record worker events, run the monitor, configure integrations, and stop a local
alarm. Use `run_interactive.sh` on Linux or `run_interactive.bat` on Windows:

```bash
./run_interactive.sh
```

```powershell
.\run_interactive.bat
```

Use dry-run mode to inspect behavior without sending real notifications:

```bash
python3 main.py --dry-run
```

## Configuration

Create the local environment file:

```bash
cp .env.example .env
```

Never commit the real `.env`. At minimum, configure separate Discord webhooks
for point messages and alerts:

```env
DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

A Discord webhook belongs to one channel, so the point and alert channels need
different URLs.

To restrict alerts to work hours and repeat yellow/orange notices while a worker
remains overdue:

```env
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange
```

The red level never repeats during the same inactivity episode, even if an old
configuration still lists `red` in `PRESENCE_ALERT_REPEAT_LEVELS`.

## Basic Usage

Initialize the database:

```bash
ai-presence init
```

List available protocols:

```bash
ai-presence protocols
```

Run one monitoring cycle:

```bash
ai-presence monitor --once
```

Run continuously:

```bash
ai-presence monitor
```

Inspect worker state:

```bash
ai-presence status
```

## AI Worker Operation

An AI responsible for operating this project must read [AGENTS.md](AGENTS.md)
and the [AI worker command protocol](docs/AI-WORKER-COMMAND-PROTOCOL.md).
Those documents define lifecycle commands, observed activity, remote questions,
GUI safety boundaries, exit codes, and completion requirements.

Use an explicit absolute project path for project-scoped workers:

```bash
ai-presence start \
  --ai codex \
  --protocol protocol2 \
  --project /absolute/path/to/project \
  --task "Implement feature X"
```

Finish only when the task is actually complete:

```bash
ai-presence finish \
  --ai codex \
  --protocol protocol2 \
  --project /absolute/path/to/project \
  --message "Task completed"
```

## Protocol 1 Example

Start work:

```bash
ai-presence start \
  --ai codex \
  --protocol protocol1 \
  --task "refactor-x" \
  --message "Starting the task"
```

Send a public heartbeat every five minutes:

```bash
ai-presence heartbeat \
  --ai codex \
  --protocol protocol1 \
  --task "refactor-x" \
  --message "Still working on the task"
```

Finish work:

```bash
ai-presence finish \
  --ai codex \
  --protocol protocol1 \
  --message "Task completed"
```

## Protocol 2 Example

Start work:

```bash
ai-presence start \
  --ai codex \
  --protocol protocol2 \
  --task "algorithm-y" \
  --message "Execution started"
```

Record silent internal activity without posting to Discord:

```bash
ai-presence touch \
  --ai codex \
  --protocol protocol2 \
  --task "algorithm-y" \
  --message "Internal step completed"
```

Finish work:

```bash
ai-presence finish \
  --ai codex \
  --protocol protocol2 \
  --message "Execution finished"
```

## Codex Observer

The recommended Codex integration uses hooks as passive observers. A hook
receives Codex JSON events, records local activity in SQLite, and exits quickly.
It does not send Discord or Telegram messages directly; the monitor remains the
single alert policy engine.

This avoids false Protocol 2 alerts during long tasks when Codex continues to
produce prompt, tool, or turn events.

Example configuration:

```env
PRESENCE_DEFAULT_PROTOCOL=protocol2
PRESENCE_CODEX_WORKER_ID=your-computer:codex
PRESENCE_CODEX_AI_NAME=codex
PRESENCE_CODEX_PROTOCOL=protocol2
PRESENCE_CODEX_TASK=
PRESENCE_CODEX_WORKER_SCOPE=project
PRESENCE_CODEX_AUTO_START=false
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false
```

With `PRESENCE_CODEX_AUTO_START=false`, hooks record activity only for an
already active worker. Use `start` and `finish` as explicit public lifecycle
boundaries.

With `PRESENCE_CODEX_WORKER_SCOPE=project`, run lifecycle commands from the
project root or pass `--project`. Other scopes are `global`, `session`, and
`project-session`.

### Install Codex hooks

Use [examples/codex/hooks.json](examples/codex/hooks.json) as a reference, or
run the idempotent installer with backup support:

```bash
ai-presence --dry-run install-codex-hook
ai-presence install-codex-hook
```

Remove only AI Presence Monitor hooks:

```bash
ai-presence uninstall-codex-hook
```

Manual hook smoke test:

```bash
printf '%s\n' '{"hook_event_name":"PostToolUse","tool_name":"Bash","session_id":"test","cwd":"/tmp/project"}' \
  | ai-presence codex-hook --verbose
```

Observer limitations:

- hook events prove activity signals, not work quality;
- a long command may emit `PreToolUse` at the start and `PostToolUse` only at
  the end;
- additional process, workspace, or log observers may still be useful.

## Continuous Background Execution

The portable command selects systemd on Linux and Task Scheduler on Windows:

```bash
ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor
```

On Windows, the second command registers `AI Presence Monitor` for the current
user at logon. Start or inspect it with:

```powershell
schtasks.exe /Run /TN "AI Presence Monitor"
schtasks.exe /Query /TN "AI Presence Monitor" /V /FO LIST
```

Remove the platform-managed definition:

```bash
ai-presence uninstall-background-service --component monitor
```

### Linux systemd compatibility commands

Generate and enable the user-level systemd service after installing the package:

```bash
ai-presence --dry-run install-systemd-service
ai-presence install-systemd-service
systemctl --user daemon-reload
systemctl --user enable --now ai-presence-monitor.service
```

Inspect service health:

```bash
systemctl --user status ai-presence-monitor.service
journalctl --user -u ai-presence-monitor.service -n 100 --no-pager
```

## Remote Questions and Answers

Remote questions are disabled by default. The monitor can publish a correlated
question in a dedicated Discord channel, accept only a direct reply from an
allowlisted user, and optionally deliver the answer to the exact Codex GUI
window.

Keep GUI delivery disabled until the Discord correlation flow has been tested.
See the [remote response guide](docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md).

```bash
ai-presence --dry-run ask-user --worker worker-id --question "May I proceed?"
ai-presence ask-user --worker worker-id --question "May I proceed?"
ai-presence observe-replies --once
ai-presence observe-replies
ai-presence questions
```

Install the separate reply observer service:

```bash
ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer
```

On Linux, run the printed `systemctl` commands. On Windows, the task is
registered at logon and the printed `schtasks.exe /Run` command starts it now.

## Integrated Codex Continue Command

The package can schedule the default `continue` message for the Codex GUI:

```bash
ai-presence --dry-run continue \
  --worker EXACT_WORKER_ID \
  --window-title 'Codex'

ai-presence continue \
  --worker EXACT_WORKER_ID \
  --window-title 'Codex'
```

The default delay is 60 seconds. The target must resolve to exactly one visible
window and is validated again after the wait. Linux uses X11; Windows uses the
native Win32 window API and Unicode `SendInput` without replacing the clipboard.

For terminals that dynamically change the full title, combine an explicit
window ID with a stable project title pattern:

```bash
ai-presence continue \
  --window-id EXACT_WINDOW_ID \
  --window-title 'stable project name' \
  --allow-title-change
```

This mode still validates the same window ID and title pattern. It relaxes only
full-title equality.

After successful input emission, an already active Protocol 2 worker may record
`observation:automation:continue`, updating `last_activity_at`. A later Codex
hook remains the confirmation that the session actually resumed.

Protocol 1 never treats `continue` as a public heartbeat. Scheduling, dry-run,
GUI failure, and inactive workers do not count as activity.

See [docs/CONTINUE-CODEX.md](docs/CONTINUE-CODEX.md) for background execution,
synchronization, safety checks, and rollback.

## Red Alert Escalation

Discord and Telegram carry alert messages. A red alert may additionally run a
local alarm or call an external telephony webhook.

The red message and its external escalation happen once per continuous
inactivity episode. Valid worker activity rearms a future red alert.

Linux local alarm example:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
```

Windows local alarm example:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=ffplay.exe -nodisp -loop 0 "C:\Sounds\alarm.mp3"
```

Every red episode starts the local command once. Linux uses GNU `timeout`;
Windows uses a dedicated Python runner and terminates its process tree with
`taskkill`. Both enforce the configured maximum duration and validate process
identity before manual interruption.

Stop the current alarm before the limit:

```bash
ai-presence stop-alarm
```

External phone escalation example:

```env
RED_NOTIFICATION_MODE=phone
PHONE_WEBHOOK_URL=https://your-telephony-service.example/webhook
```

The monitor sends JSON to the configured service; it does not place calls by
itself.

## Dry-Run Examples

Use `--dry-run` to inspect payloads and decisions without calling external
services or controlling the GUI:

```bash
ai-presence --dry-run heartbeat --ai codex --message "test"
ai-presence --dry-run monitor --once
ai-presence --dry-run continue --worker worker-id --window-title 'Codex'
```

## Development

The package source lives in `src/ai_presence_monitor`.

Install development tools and run the full local quality gate:

```bash
python3 -m pip install -e '.[dev]'
./scripts/quality-check.sh
```

The gate runs compilation, unit tests, coverage, Ruff, mypy, package build, and
`git diff --check`. The release matrix covers Python 3.10, 3.11, and 3.12:

```bash
./scripts/test-python-matrix.sh
```

Current automated coverage is maintained above the configured 80% threshold.
