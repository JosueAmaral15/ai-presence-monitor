# Plano de Acao: Hardening Operacional e E2E Discord-Codex

## TL;DR

Esta tarefa fecha as lacunas encontradas depois da migracao do banco e da
ativacao real do observer Discord. O trabalho desta sessao deve:

1. limitar reinicios do observer quando Discord ou credenciais falharem;
2. corrigir o gate de lint local;
3. reinstalar e validar o pacote atualizado;
4. executar um E2E autorizado entre Discord e a janela exata do Codex GUI;
5. usar a resposta do E2E para decidir o destino de workers historicos ainda
   marcados como ativos;
6. registrar evidencias e qualquer dependencia externa que nao possa ser
   concluida localmente.

## Contexto Verificado

Em 2026-09-08:

- o checkout esta na branch
  `COM-6e997b50-9ace-4c24-acbf-c99b949b9882`;
- o pacote instalado e o codigo-fonte estao na versao `0.5.0`;
- monitor e observer estao ativos e habilitados, sem reinicios acumulados;
- o banco canonico fica fora do checkout e passou na verificacao de
  integridade;
- perguntas remotas, allowlist e entrega GUI estao habilitadas;
- existe uma unica janela X11 visivel intitulada `ChatGPT`;
- o alvo anterior nao correspondia a janela reinstalada e foi atualizado para
  o padrao exato `^ChatGPT$`;
- o usuario autorizou explicitamente o teste E2E Discord-Codex, incluindo a
  entrega GUI da resposta;
- dois workers historicos continuam `active` e precisam de decisao humana:
  `AmaralAgenda-23813ab6` e
  `O-Juramento-da-Herdeira-de-Vinterholm-e7e0651f`.

## Escopo

### Incluido nesta sessao

- protecao systemd especifica para o reply observer;
- testes unitarios da definicao gerada;
- correcao do gate `scripts/quality_check.py`;
- atualizacao de requisitos, arquitetura, seguranca, rollback, decisoes,
  changelog e documentacao operacional;
- build e instalacao da versao de correcao;
- reinstalacao idempotente dos servicos;
- teste real com pergunta, resposta direta autorizada, polling, entrega GUI e
  confirmacao posterior por hook;
- atualizacao incremental deste plano com evidencias reais.

### Fora do escopo local

- reiniciar o computador sem solicitacao especifica do usuario;
- corrigir cobranca ou executar jobs bloqueados na conta GitHub;
- alterar permissoes externas do Discord sem acesso administrativo;
- reenviar automaticamente entrada GUI com resultado incerto.

## Decisao Tecnica

O monitor principal preserva `Restart=always` e `RestartSec=5`. O reply
observer recebe uma politica propria:

```ini
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Restart=on-failure
RestartSec=30
```

O limite interrompe uma tempestade de reinicios depois de tres falhas em cinco
minutos. O intervalo de 30 segundos reduz carga e ruido antes de o limite ser
atingido. Essa decisao se aproxima do Task Scheduler Windows, que ja limita
reinicios em falha, sem enfraquecer a recuperacao do monitor principal.

## Fases e Checkpoints

| Fase | Entrega | Status |
|---|---|---|
| 1 | Auditoria de runtime, servicos, banco e janela | concluida |
| 2 | Plano e Task 013 registrados | concluida |
| 3 | Hardening systemd, testes e lint | concluida |
| 4 | Suite, cobertura, tipos, build e instalacao | concluida |
| 5 | E2E Discord para Codex GUI | concluida |
| 6 | Decisao e saneamento dos workers historicos | concluida: manter ambos |
| 7 | Evidencias finais e dependencias externas | concluida |

## Roteiro E2E Autorizado

1. Confirmar uma unica janela correspondente a `^ChatGPT$`.
2. Confirmar observer ativo, allowlist valida e ausencia de pergunta pendente.
3. Publicar no Discord uma pergunta que tambem resolva os workers historicos.
4. O usuario deve usar **Responder** na mensagem publicada.
5. O observer deve aceitar somente a resposta correlacionada e autorizada.
6. O dispatcher deve revalidar o mesmo ID e titulo, clicar no prompt, colar a
   resposta e pressionar Enter.
7. Registrar `input_emitted`, sem tratar isso como confirmacao de processamento.
8. Confirmar `delivery_confirmed` apenas por hook posterior do mesmo worker.
9. Nao repetir automaticamente se o resultado for incerto.

Pergunta planejada:

```text
Teste E2E e decisao operacional: os workers historicos AmaralAgenda-23813ab6 e O-Juramento-da-Herdeira-de-Vinterholm-e7e0651f ainda representam trabalhos em andamento? Responda usando Responder com uma destas opcoes: ENCERRAR AMBOS; MANTER AMARALAGENDA; MANTER VINTERHOLM; MANTER AMBOS.
```

## Criterios de Aceite

- [x] O monitor principal mantem a politica de reinicio existente.
- [x] O reply observer limita reinicios a tres falhas em cinco minutos.
- [x] Testes verificam as duas politicas separadamente.
- [x] O gate completo local passa com cobertura minima de 80%.
- [x] O wheel atualizado e instalado no ambiente dedicado.
- [x] Servicos gerados usam o Python instalado e o `.env` central.
- [x] Cada pergunta autorizada e publicada uma unica vez, sem retry automatico.
- [x] A resposta e aceita somente por correlacao e allowlist.
- [x] A entrega GUI chega a `input_emitted` sem retry automatico.
- [x] Um hook posterior confirma `delivery_confirmed`.
- [x] Workers historicos sao encerrados ou mantidos conforme a resposta.
- [x] Tudo que depender de sistema externo fica registrado abaixo.

## Rollback

1. Interromper somente o observer:

   ```bash
   systemctl --user disable --now ai-presence-reply-observer.service
   ```

2. Restaurar o backup da unidade criado pelo instalador ou reinstalar o wheel
   `0.5.0`.
3. Executar `systemctl --user daemon-reload` e reativar somente depois de um
   `observe-replies --once` bem-sucedido.
4. Em falha GUI incerta, consultar `ai-presence questions` e nao executar
   `dispatch-answer` sem confirmar visualmente que nada foi enviado.
5. Para liberar o limite apos corrigir credenciais ou rede:

   ```bash
   systemctl --user reset-failed ai-presence-reply-observer.service
   systemctl --user start ai-presence-reply-observer.service
   ```

## Dependencias Externas

- CI real em `windows-latest`: bloqueada pela cobranca da conta GitHub; manter
  registrada na Task 012.
- Persistencia depois de reboot/login: requer uma reinicializacao deliberada;
  validar em uma sessao operacional futura, sem reiniciar automaticamente.
- Resposta do E2E: concluida no canal Discord dedicado e registrada no SQLite
  como `delivery_confirmed`.

## Checkpoint de Continuidade

Em 2026-09-09, as duas perguntas E2E estao `expired`. A segunda republicacao
foi solicitada explicitamente pelo usuario e nao foi um retry automatico. O
observer deve continuar ativo. Como nao existe mais entrega pendente, o worker
desta sessao pode ser encerrado sem impedir confirmacao por hook. Um novo E2E
deve executar `start`, publicar uma pergunta somente com autorizacao explicita
e manter o worker ativo ate `delivery_confirmed` ou expiracao.

Uma mensagem do usuario autorizado foi lida as `07:13:49`, mas chegou como
mensagem normal (`type=0`), sem `message_reference` e com `content` vazio. O
observer a rejeitou corretamente e nao acionou a GUI. Para a proxima tentativa
na mesma pergunta:

1. habilitar **Message Content Intent** em **Discord Developer Portal >
   Applications > aplicativo do bot > Bot > Privileged Gateway Intents**;
2. salvar a alteracao;
3. na mensagem da pergunta, usar a acao **Responder** e confirmar que o editor
   mostra a resposta vinculada;
4. enviar uma das quatro opcoes exatas antes da expiracao.

A documentacao oficial do Discord informa que, sem esse intent, `content`,
`embeds`, `attachments` e `components` chegam vazios pela API:
<https://docs.discord.com/developers/resources/message>.

Quando a resposta chegar:

1. verificar o estado da pergunta sem reenviar entrada GUI;
2. exigir `input_emitted` e depois um hook com `delivery_confirmed`;
3. encerrar ou manter cada worker historico exatamente conforme a resposta;
4. concluir os criterios restantes e executar `finish` uma unica vez para o
   worker desta tarefa.

Se a pergunta expirar, nao publicar uma substituta automaticamente. Uma nova
publicacao e uma nova entrada GUI exigem autorizacao explicita do usuario.

## Registro de Evidencias

- 2026-09-08: runtime `0.5.0`, banco e servicos validados.
- 2026-09-08: alvo obsoleto detectado antes de qualquer entrada GUI.
- 2026-09-08: alvo atualizado para uma unica janela `ChatGPT`, ID X11
  `67108868`.
- 2026-09-08: gate local passou com 117 testes, cobertura total de 86%, Ruff,
  mypy, build de sdist e wheel `0.5.1`, alem de `git diff --check`.
- 2026-09-08: wheel `0.5.1` instalado no venv dedicado; unidades regeneradas
  com backups e reativadas a partir do `.env` central.
- 2026-09-08: monitor efetivo em `Restart=always`, `RestartSec=5`;
  reply observer em `Restart=on-failure`, `RestartSec=30`, tres falhas em cinco
  minutos. Ambos ativos, habilitados e com `NRestarts=0`.
- 2026-09-08: pergunta E2E `46a8b00c-f94a-4054-aeb3-977610486d72`
  publicada uma unica vez no Discord; estado inicial `pending`, janela X11
  capturada com ID `67108868` e titulo exato `ChatGPT`.
- 2026-09-09: primeira pergunta confirmada como `expired`, sem resposta nem
  entrada GUI.
- 2026-09-09: dois timeouts isolados do Discord causaram dois reinicios do
  observer as `03:17` e `03:19`; a politica de 30 segundos funcionou e o
  servico permaneceu estavel e ativo depois da recuperacao.
- 2026-09-09: nova pergunta autorizada
  `1d7f72b0-c1bd-4a8f-ac5a-fe8e5d73832f` publicada uma unica vez, com estado
  inicial `pending`, expiracao as `07:38:03` e o mesmo alvo X11 revalidado.
- 2026-09-09: segunda pergunta expirou sem resposta valida nem entrada GUI. A
  orientacao automatica resultante do diagnostico foi implementada na Task 014;
  um novo E2E depende de `Message Content Intent` e autorizacao do usuario.
- 2026-09-09: primeira resposta da nova pergunta lida, mas rejeitada por falta
  de correlacao direta e de conteudo visivel; zero entradas GUI emitidas.
- 2026-09-10: `Message Content Intent` habilitado e confirmado pela flag
  `GATEWAY_MESSAGE_CONTENT_LIMITED` (`524288`) da aplicacao.
- 2026-09-10: uma resposta que referenciava a orientacao foi rejeitada e
  recebeu novo aviso; nenhuma entrada GUI invalida foi emitida.
- 2026-09-10: resposta `MANTER AMBOS` do usuario autorizado referenciou a
  pergunta `7a22a705-8a91-41cc-81c9-93c3b041c837`, foi aceita uma unica vez,
  emitida para a janela revalidada e confirmada por hook como
  `delivery_confirmed`, sem falha GUI ou retry automatico.
- 2026-09-10: os workers historicos `AmaralAgenda-23813ab6` e
  `O-Juramento-da-Herdeira-de-Vinterholm-e7e0651f` foram mantidos `active`,
  conforme a decisao explicita `MANTER AMBOS`.
