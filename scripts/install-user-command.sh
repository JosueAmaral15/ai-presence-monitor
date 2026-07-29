#!/usr/bin/env bash
set -euo pipefail

source_command="${1:-$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence}"
target_command="${2:-$HOME/.local/bin/ai-presence}"

if [[ ! -x "$source_command" ]]; then
    printf 'Comando de origem nao encontrado ou nao executavel: %s\n' "$source_command" >&2
    exit 2
fi

mkdir -p "$(dirname "$target_command")"
ln -sfn "$source_command" "$target_command"

printf 'Comando instalado: %s -> %s\n' "$target_command" "$source_command"
printf 'Abra um novo terminal se %s ainda nao estiver no PATH.\n' "$(dirname "$target_command")"
