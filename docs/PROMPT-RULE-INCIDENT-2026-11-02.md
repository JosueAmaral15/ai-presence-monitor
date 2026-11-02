# Incidente de prompt rule em 2026-11-02

## Relato

Uma regra `after_delay` foi salva perto de 10:00 com atraso de 52 minutos. O
prompt nao chegou a sessao Codex ate 13:03.

## Evidencias sanitizadas

- runtime instalado durante o incidente: `0.10.7`;
- vencimento persistido da regra: `2026-11-02 10:40:38 -03`;
- regra ainda habilitada, sem ocorrencias e sem tentativa de transporte;
- estado persistido: `waiting_for_usage`;
- opcao **Require available Codex usage**: habilitada;
- nenhuma evidencia `account_limit/usage_available` existia no banco;
- `ai-presence-prompt-rule-observer.service`: nao instalado;
- bandeja antiga estava aberta, mas nao substitui o produtor persistente de
  evidencia de uso da versao seguinte.

Nenhum prompt foi perdido depois de uma tentativa de fila: a tentativa nunca
comecou. A regra falhou fechada porque exigia evidencia fresca de uso e nenhum
observer instalado podia produzi-la.

## Correcao

O codigo candidato inclui um observer dedicado que:

1. localiza somente regras habilitadas, vencidas, associadas a sessao exata e
   condicionadas a uso;
2. consulta o App Server somente quando existe alvo elegivel;
3. registra evidencia sanitizada por worker e sessao;
4. despacha uma unica vez quando o uso comum esta disponivel;
5. desarma a regra antes do transporte e aguarda hook posterior para confirmar
   atividade.

A regressao automatizada reproduz exatamente 52 minutos, com worker encerrado,
prova que a bandeja nao disputa a regra e que o observer envia uma unica vez.

## Fechamento operacional

O incidente so pode ser considerado corrigido no computador depois de:

- instalar transacionalmente o novo wheel;
- instalar e ativar uma unica unidade
  `ai-presence-prompt-rule-observer.service`;
- confirmar `doctor --strict`, zero loop de reinicio e ciclo ocioso;
- executar um E2E autorizado em uma sessao Codex exata com marcador exclusivo.

Enquanto isso, desmarcar **Require available Codex usage** permite que uma regra
puramente temporal seja avaliada pela bandeja, mas reduz a protecao contra
tentativas durante indisponibilidade de tokens. Isso e uma escolha do usuario,
nao a correcao definitiva.

O primeiro dry-run do upgrade tambem revelou um bloqueador separado: o
preflight do candidato comparava o schema 1 com as tabelas finais do schema 2 e
rejeitava a migracao antes de inicia-la. O contrato agora declara as tabelas
minimas por versao; schema 1 integro e aceito, enquanto schema 1 corrompido
continua rejeitado.

Depois do upgrade 0.11.0, o E2E operacional revelou que o systemd nao herdava o
diretorio NVM que continha `codex`. A unidade entrou em reinicio e foi
interrompida antes de qualquer despacho. O hotfix 0.11.1 grava o caminho
absoluto do executavel no `ExecStart` e aplica limite de reinicios ao observer.

O primeiro ciclo estavel do 0.11.1 confirmou `usage_available`, mas revelou que
o transporte `codex queue` ainda criava seu proprio cliente com o nome relativo
`codex`. As regras foram desarmadas como `failed_or_uncertain`, conforme a
politica de nao repeticao. O 0.11.2 reutiliza o mesmo caminho absoluto na coleta
e no transporte. Reabilitar uma regra desarmada continua sendo decisao humana
na bandeja.
