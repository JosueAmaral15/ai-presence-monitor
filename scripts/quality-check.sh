#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python_command="${PYTHON:-python3}"
exec "$python_command" scripts/quality_check.py
