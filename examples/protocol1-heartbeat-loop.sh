#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TASK="${1:-tarefa-padrao}"
AI_NAME="${AI_NAME:-codex}"

finish() {
  python3 -m ai_presence_monitor finish \
    --ai "$AI_NAME" \
    --protocol protocol1 \
    --task "$TASK" \
    --message "loop de ponto encerrado"
}

trap finish EXIT

python3 -m ai_presence_monitor start \
  --ai "$AI_NAME" \
  --protocol protocol1 \
  --task "$TASK" \
  --message "inicio do trabalho"

while true; do
  python3 -m ai_presence_monitor heartbeat \
    --ai "$AI_NAME" \
    --protocol protocol1 \
    --task "$TASK" \
    --message "continuo trabalhando"
  sleep 300
done
