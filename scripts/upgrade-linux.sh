#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: upgrade-linux.sh --package PATH --rollback-package PATH [options]

Options:
  --install-root PATH  Default: $XDG_DATA_HOME/ai-presence-monitor
  --env-file PATH      Default: $XDG_CONFIG_HOME/ai-presence-monitor/.env
  --python PATH        Installed runtime Python; overrides --install-root
  --dry-run            Validate only (default)
  --authorize-once     Perform one real transactional upgrade
  --help               Show this help

This bootstrap runs the updater from the target wheel while mutating only the
dedicated installed runtime. A real upgrade requires --authorize-once.
EOF
}

package=""
rollback_package=""
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
install_root="$data_home/ai-presence-monitor"
env_file="$config_home/ai-presence-monitor/.env"
python_command=""
dry_run=true
authorized=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --package)
            package="${2:-}"
            shift 2
            ;;
        --rollback-package)
            rollback_package="${2:-}"
            shift 2
            ;;
        --install-root)
            install_root="${2:-}"
            shift 2
            ;;
        --env-file)
            env_file="${2:-}"
            shift 2
            ;;
        --python)
            python_command="${2:-}"
            shift 2
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        --authorize-once)
            authorized=true
            dry_run=false
            shift
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
    printf 'Transactional upgrade supports Linux only.\n' >&2
    exit 2
fi
if [[ -z "$package" || ! -f "$package" || "$package" != *.whl ]]; then
    printf 'Provide an existing target wheel with --package PATH.\n' >&2
    exit 2
fi
if [[ -z "$rollback_package" || ! -f "$rollback_package" || "$rollback_package" != *.whl ]]; then
    printf 'Provide an existing rollback wheel with --rollback-package PATH.\n' >&2
    exit 2
fi
if [[ ! -f "$env_file" ]]; then
    printf 'Environment file was not found: %s\n' "$env_file" >&2
    exit 2
fi

package="$(realpath -e -- "$package")"
rollback_package="$(realpath -e -- "$rollback_package")"
if [[ "$package" == *:* ]]; then
    printf 'Target wheel path must not contain a colon.\n' >&2
    exit 2
fi
if [[ -z "$python_command" ]]; then
    python_command="$install_root/venv/bin/python"
fi
if [[ ! -x "$python_command" ]]; then
    printf 'Installed runtime Python is not executable: %s\n' "$python_command" >&2
    exit 2
fi

candidate_origin="$(
    env -u PYTHONHOME PYTHONPATH="$package" PYTHONNOUSERSITE=1 \
        "$python_command" -c 'import ai_presence_monitor; print(ai_presence_monitor.__file__)'
)"
if [[ "$candidate_origin" != "$package/"* ]]; then
    printf 'Target wheel could not bootstrap its own updater.\n' >&2
    exit 2
fi

arguments=(--env-file "$env_file")
if [[ "$dry_run" == true ]]; then
    arguments+=(--dry-run)
fi
arguments+=(
    upgrade
    --package "$package"
    --rollback-package "$rollback_package"
)
if [[ "$authorized" == true ]]; then
    arguments+=(--authorize-once)
fi
arguments+=(--json)

exec env -u PYTHONHOME PYTHONPATH="$package" PYTHONNOUSERSITE=1 \
    "$python_command" -m ai_presence_monitor "${arguments[@]}"
