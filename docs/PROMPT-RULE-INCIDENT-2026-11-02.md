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
