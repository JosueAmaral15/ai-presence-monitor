#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install-linux.sh --wheel PATH [options]

Options:
  --install-root PATH     Default: $XDG_DATA_HOME/ai-presence-monitor
  --config-template PATH  Default: .env.example beside this script
  --command-link PATH     Default: $HOME/.local/bin/ai-presence
  --python COMMAND        Default: python3
  --help                  Show this help

This installer is for a fresh Linux installation. Existing installations must
use `ai-presence upgrade` with an exact rollback wheel.
EOF
}

wheel=""
python_command="${PYTHON:-python3}"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
install_root="$data_home/ai-presence-monitor"
config_template="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env.example"
command_link="$HOME/.local/bin/ai-presence"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wheel)
            wheel="${2:-}"
            shift 2
            ;;
        --install-root)
            install_root="${2:-}"
            shift 2
            ;;
        --config-template)
            config_template="${2:-}"
            shift 2
            ;;
        --command-link)
            command_link="${2:-}"
            shift 2
            ;;
        --python)
            python_command="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
    printf 'This release installer supports Linux only.\n' >&2
    exit 2
fi
if [[ -z "$wheel" || ! -f "$wheel" || "$wheel" != *.whl ]]; then
    printf 'Provide an existing local wheel with --wheel PATH.\n' >&2
    exit 2
fi
if ! command -v "$python_command" >/dev/null 2>&1; then
    printf 'Python command was not found: %s\n' "$python_command" >&2
    exit 2
fi
"$python_command" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 2)' || {
    printf 'Python 3.10, 3.11, or 3.12 is required.\n' >&2
    exit 2
}

if [[ "$install_root" != /* || "$install_root" == "/" || "$install_root" == "$HOME" ]]; then
    printf 'Install root must be an absolute, dedicated non-root directory.\n' >&2
    exit 2
fi
if [[ -L "$install_root" ]]; then
    printf 'Install root must not be a symbolic link: %s\n' "$install_root" >&2
    exit 2
fi
if [[ "$command_link" != /* ]]; then
    printf 'Command link must be an absolute path.\n' >&2
    exit 2
fi
if [[ -e "$command_link" && ! -L "$command_link" ]]; then
    printf 'Command link path exists and is not a symbolic link: %s\n' "$command_link" >&2
    exit 2
fi

venv_root="$install_root/venv"
if [[ -e "$venv_root" ]]; then
    printf 'Installation already exists: %s\n' "$venv_root" >&2
    printf 'Use the installed `ai-presence upgrade` command instead.\n' >&2
    exit 2
fi

mkdir -p "$install_root" "$(dirname "$command_link")"
install_complete=false
created_venv=false
cleanup() {
    if [[ "$created_venv" == true && "$install_complete" != true ]]; then
        rm -rf -- "$venv_root"
    fi
}
trap cleanup EXIT

"$python_command" -m venv "$venv_root"
created_venv=true
installed_python="$venv_root/bin/python"
installed_command="$venv_root/bin/ai-presence"
"$installed_python" -m pip install --no-index --no-deps "$wheel"
"$installed_command" --version

config_dir="$config_home/ai-presence-monitor"
config_file="$config_dir/.env"
if [[ ! -e "$config_file" && -f "$config_template" ]]; then
    mkdir -p "$config_dir"
    install -m 600 "$config_template" "$config_file"
    printf 'Configuration template installed: %s\n' "$config_file"
elif [[ -e "$config_file" ]]; then
    printf 'Existing configuration preserved: %s\n' "$config_file"
else
    printf 'Configuration template not found; create: %s\n' "$config_file" >&2
fi

if [[ -f "$config_file" ]]; then
    "$installed_command" --env-file "$config_file" init
fi

ln -sfn "$installed_command" "$command_link"
install_complete=true
printf 'Installed command: %s -> %s\n' "$command_link" "$installed_command"
printf 'Next: edit %s, then run `ai-presence doctor --strict`.\n' "$config_file"
printf 'Services and Codex hooks are not installed automatically.\n'
