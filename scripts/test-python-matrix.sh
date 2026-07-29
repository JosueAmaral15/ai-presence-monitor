#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

tested=0
for python_command in python3.10 python3.11 python3.12; do
    if ! command -v "$python_command" >/dev/null 2>&1; then
        continue
    fi

    echo "==> $python_command"
    "$python_command" -m compileall -q ai_presence_monitor hooks tests main.py
    "$python_command" -m unittest discover -s tests -q
    tested=$((tested + 1))
done

if [[ "$tested" -eq 0 ]]; then
    echo "Nenhuma versao Python 3.10-3.12 encontrada." >&2
    exit 1
fi

echo "Matriz concluida: $tested versoes testadas."
