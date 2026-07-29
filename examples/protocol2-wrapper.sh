#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$#" -lt 2 ]; then
  echo "Uso: $0 <nome-da-tarefa> <comando> [args...]"
  exit 2
fi

TASK="$1"
shift

python3 -m ai_presence_monitor start \
  --protocol protocol2 \
  --task "$TASK" \
  --message "execucao iniciada"

"$@" &
PID="$!"

while kill -0 "$PID" 2>/dev/null; do
  python3 -m ai_presence_monitor touch \
    --protocol protocol2 \
    --task "$TASK" \
    --message "processo ainda ativo"
  sleep 240
done

wait "$PID"
RESULT="$?"

python3 -m ai_presence_monitor finish \
  --protocol protocol2 \
  --task "$TASK" \
  --message "execucao finalizada com codigo $RESULT"

exit "$RESULT"
