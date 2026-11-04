#!/usr/bin/env bash
set -euo pipefail

package="${1:-}"

if [[ -z "$package" || ! -f "$package" || "$package" != *.deb ]]; then
    printf 'Usage: %s /absolute/path/package.deb\n' "$0" >&2
    exit 2
fi
package="$(realpath -e -- "$package")"

images=(
    "debian:12-slim"
    "ubuntu:22.04"
    "ubuntu:24.04"
)

for image in "${images[@]}"; do
    printf '==> %s\n' "$image"
    docker run --rm \
        --mount "type=bind,src=$package,dst=/tmp/ai-presence-monitor.deb,readonly" \
        "$image" \
        sh -eu -c '
            export DEBIAN_FRONTEND=noninteractive
            apt-get update
            apt-get install -y --no-install-recommends /tmp/ai-presence-monitor.deb
            test "$(dpkg-query -W -f="\${Status}" ai-presence-monitor)" = "install ok installed"
            ai-presence --version
            home="$(mktemp -d)"
            export HOME="$home"
            export XDG_CONFIG_HOME="$home/.config"
            export XDG_STATE_HOME="$home/.local/state"
            mkdir -p "$XDG_CONFIG_HOME/ai-presence-monitor"
            cp /usr/share/ai-presence-monitor/.env.example "$XDG_CONFIG_HOME/ai-presence-monitor/.env"
            chmod 600 "$XDG_CONFIG_HOME/ai-presence-monitor/.env"
            ai-presence init
            ai-presence schema-status --json
            ai-presence doctor --json >/tmp/doctor.json || test "$?" -eq 2
            python3 -c "import json; data=json.load(open(\"/tmp/doctor.json\")); assert data[\"version\"]"
            apt-get remove -y ai-presence-monitor
            test ! -e /usr/bin/ai-presence
            test ! -e /usr/lib/python3/dist-packages/ai_presence_monitor
        '
done

printf 'Debian package container matrix passed: %s\n' "${images[*]}"
