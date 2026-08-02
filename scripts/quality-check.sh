#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python_command="${PYTHON:-python3}"
export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"

"$python_command" -m compileall -q src/ai_presence_monitor hooks tests main.py
"$python_command" -m unittest discover -s tests -q
"$python_command" -m coverage erase
"$python_command" -m coverage run -m unittest discover -s tests
"$python_command" -m coverage report --fail-under=80
"$python_command" -m ruff check src hooks tests main.py
"$python_command" -m mypy src/ai_presence_monitor

build_workspace="$(mktemp -d)"
trap 'rm -rf "$build_workspace"' EXIT
(
    cd "$build_workspace"
    PYTHONPATH= "$python_command" -m build \
        "$project_root" \
        --outdir "$project_root/dist"
)

git diff --check
