# Planejamento Solo: Alerta Vermelho por Episodio

## 1. Objetivo

Enviar o alerta vermelho somente uma vez durante cada periodo continuo de
inatividade de um worker. Uma atividade valida rearma o alerta para um futuro
episodio de inatividade.

## 2. Regra

- amarelo e laranja podem repetir conforme a configuracao existente;
- vermelho nao repete, mesmo se estiver listado em
  `PRESENCE_ALERT_REPEAT_LEVELS`;
- `start`, `heartbeat`, `touch` e observacoes autorizadas limpam o ultimo alerta
  e rearmam todos os niveis;
- `finish` retira o worker do monitoramento por deixa-lo inativo.

## 3. Criterios de Aceite

- [x] O primeiro vermelho envia Discord/Telegram e a escalada configurada.
- [x] Novos ciclos do monitor nao reenviam vermelho sem atividade intermediaria.
- [x] Uma atividade valida rearma o vermelho.
- [x] Amarelo e laranja preservam a repeticao configuravel.
- [x] Configuracao, arquitetura, seguranca e rollback ficam documentados.
- [x] Suite, cobertura, lint, tipos, build e matriz Python passam.

## 4. Riscos e Rollback

O risco principal e silenciar um incidente novo por nao reconhecer a atividade.
O teste deve provar explicitamente o ciclo `vermelho -> silencio -> atividade ->
vermelho`.

Para rollback, reverta somente a alteracao de politica em `_should_send_alert`
e restaure a lista documentada de niveis repetiveis. Nao ha migracao de banco.
