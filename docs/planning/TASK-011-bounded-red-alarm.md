# Planejamento Solo: Duracao Limitada do Alarme Vermelho

## 1. Objetivo

Garantir um unico disparo sonoro finito quando um episodio alcancar o nivel
vermelho, inclusive se `RED_ALERT_COMMAND` contiver um loop continuo.

## 2. Regra

- o vermelho dispara no maximo uma vez por episodio de inatividade;
- o comando local executa por no maximo 15 segundos por padrao;
- `RED_ALERT_MAX_DURATION_SECONDS` permite ajustar a duracao;
- `ai-presence stop-alarm` continua interrompendo imediatamente;
- nova atividade rearma um futuro episodio e um novo disparo finito.

## 3. Criterios de Aceite

- [x] Comando continuo termina automaticamente no limite.
- [x] Termino automatico remove o estado do alarme e coleta o processo.
- [x] Duracao invalida falha antes de iniciar o processo.
- [x] Parada manual e deduplicacao continuam funcionando.
- [x] Configuracao, seguranca e rollback ficam documentados.
- [x] Suite, cobertura, tipos, lint, build e matriz Python passam.

## 4. Risco e Rollback

O limite depende de GNU `timeout`, disponivel no Linux operacional atual. Se o
executavel nao existir, o alarme falha fechado sem iniciar um processo sem
controle. O rollback restaura a versao anterior e mantem `stop-alarm` como
parada manual.
