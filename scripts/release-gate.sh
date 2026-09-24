#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$project_root"
version="$(python3 -c 'from pathlib import Path; from scripts.release_lib import project_version; print(project_version(Path.cwd()))')"
output="${1:-$project_root/dist/release-$version}"
./scripts/quality-check.sh
./scripts/test-python-matrix.sh
python3 scripts/build_release.py --output "$output"
python3 scripts/verify_release.py "$output"

printf 'Release gate passed: %s\n' "$output"
