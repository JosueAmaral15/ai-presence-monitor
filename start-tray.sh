#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unit_name="ai-presence-tray-session.service"

notify_user() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send --app-name="AI Presence Monitor" "$1" "$2" >/dev/null 2>&1 || true
    fi
}

fail() {
    printf 'AI Presence Monitor: %s\n' "$1" >&2
    notify_user "AI Presence Monitor" "$1"
    exit 1
}

if [[ -n "${AI_PRESENCE_BIN:-}" ]]; then
    ai_presence_bin="$AI_PRESENCE_BIN"
elif command -v ai-presence >/dev/null 2>&1; then
    ai_presence_bin="$(command -v ai-presence)"
else
    ai_presence_bin="$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence"
fi

[[ -x "$ai_presence_bin" ]] || fail "Installed ai-presence command was not found."

if [[ -n "${AI_PRESENCE_ENV_FILE:-}" ]]; then
    env_file="$AI_PRESENCE_ENV_FILE"
elif [[ -f "$project_root/.env" ]]; then
    env_file="$project_root/.env"
else
    env_file="$HOME/.config/ai-presence-monitor/.env"
fi

[[ -r "$env_file" ]] || fail "No readable environment file was found."
[[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] || fail "Start this launcher inside the graphical desktop session."
command -v systemctl >/dev/null 2>&1 || fail "systemctl is not available."
command -v systemd-run >/dev/null 2>&1 || fail "systemd-run is not available."

if systemctl --user is-active --quiet "$unit_name"; then
    printf 'AI Presence Monitor tray is already running.\n'
    notify_user "AI Presence Monitor" "The system tray icon is already running."
    exit 0
fi

if pgrep -u "$(id -u)" -f "$ai_presence_bin .* tray$" >/dev/null 2>&1; then
    printf 'AI Presence Monitor tray is already running outside the launcher unit.\n'
    notify_user "AI Presence Monitor" "The system tray icon is already running."
    exit 0
fi

"$ai_presence_bin" --env-file "$env_file" tray --check >/dev/null \
    || fail "Tray prerequisites are unavailable. Run the launcher from a terminal for details."

systemctl --user reset-failed "$unit_name" >/dev/null 2>&1 || true
systemd-run --user \
    --quiet \
    --unit=ai-presence-tray-session \
    --collect \
    --property=Type=exec \
    --property=Restart=on-failure \
    --property=RestartSec=5s \
    "$ai_presence_bin" --env-file "$env_file" tray

for _ in 1 2 3 4 5 6 7 8 9 10; do
    if systemctl --user is-active --quiet "$unit_name"; then
        printf 'AI Presence Monitor tray started.\n'
        notify_user "AI Presence Monitor" "The system tray icon is now running."
        exit 0
    fi
    sleep 0.5
done

fail "The tray did not remain active. Check: journalctl --user-unit $unit_name -n 30"
