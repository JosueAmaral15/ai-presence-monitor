# Respostas Remotas do Discord para o Codex GUI

## Objetivo

Este recurso permite que um AI-worker:

1. publique uma pergunta em um canal dedicado do Discord;
2. aguarde uma resposta de um usuario autorizado;
3. correlacione a resposta com a pergunta original;
4. entregue o texto na janela exata do Codex GUI;
5. pressione Enter;
6. aguarde um hook posterior do Codex para confirmar nova atividade.

Esta e uma integracao de fallback. Uma API nativa de entrada por MCP ou App
Server deve ser preferida quando estiver disponivel, pois controle de GUI pode
ser afetado por foco, titulo de janela, sessao grafica e mudancas visuais.

## Arquitetura

```text
AI-worker
    |
    | ai-presence ask-user
    v
Webhook do canal de perguntas
    |
    | mensagem Discord com ID conhecido
    v
Usuario autorizado usa "Responder"
    |
    | GET /channels/{id}/messages?after=...
    v
Observer local -> allowlist + referencia + SQLite
    |
    | resposta aceita
    v
adaptador GUI da plataforma -> janela exata -> texto -> Enter
    |
    | proximo evento do hook do mesmo worker
    v
delivery_confirmed
```

O observer usa polling da API REST. Nao abre porta local e nao expoe servidor
HTTP na Internet.

## Pre-requisitos

- bot e webhook do Discord;
- hook do Codex instalado para confirmar a entrega;
- observer `observe-replies` em execucao.

No Linux, use uma sessao X11 com `xdotool` e `xclip`:

Verifique:

```bash
command -v xdotool
command -v xclip
printf 'sessao=%s display=%s\n' "$XDG_SESSION_TYPE" "$DISPLAY"
```

No Windows 10/11, use uma sessao de desktop interativa e desbloqueada. A
automacao usa a API Win32 nativa, sem dependencia GUI externa. Wayland e macOS
nao estao implementados.

## Criar o Bot no Discord

Use somente o [Discord Developer Portal
oficial](https://discord.com/developers/applications).

1. Clique em **New Application** e crie a aplicacao.
2. Abra **Bot**.
3. Em **Token**, use **Reset Token** ou a opcao equivalente para gerar o token.
4. Guarde o token como senha. Ele sera `DISCORD_BOT_TOKEN`.
5. Em **Privileged Gateway Intents**, habilite **Message Content Intent**.
6. Abra **Installation**.
7. Em **Guild Install**, inclua o escopo `bot`.
8. Conceda somente `View Channel` e `Read Message History`.
9. Use o link de instalacao para adicionar o bot ao servidor.
10. No canal dedicado, confira se overrides nao negam essas permissoes.

O bot nao precisa enviar a pergunta: isso e feito pelo webhook. Portanto
`Send Messages` nao e necessario para este fluxo.

Referencias oficiais:

- [Bot e token](https://docs.discord.com/developers/quick-start/getting-started)
- [Get Channel Messages](https://docs.discord.com/developers/resources/message#get-channel-messages)
- [Message Content Intent](https://docs.discord.com/developers/events/gateway#message-content-intent)

## Criar o Canal e o Webhook

1. Crie um canal de texto dedicado, por exemplo `ai-perguntas`.
2. Nas configuracoes do canal, abra **Integracoes**.
3. Crie um webhook e copie a URL.
4. Essa URL sera `DISCORD_QUESTION_WEBHOOK_URL`.

O programa acrescenta `wait=true` ao webhook. Esse parametro faz o Discord
retornar a mensagem criada, incluindo o ID usado na correlacao. O payload
da pergunta desativa mencoes automaticas com `allowed_mentions`. Uma orientacao
de resposta invalida pode mencionar somente o autor que ja passou pela
allowlist; mencoes por texto continuam bloqueadas.

Referencia oficial:
[Execute Webhook](https://docs.discord.com/developers/resources/webhook#execute-webhook).

## Obter IDs do Canal e dos Usuarios

Ative **Configuracoes do Usuario > Avancado > Modo desenvolvedor**. Depois:

- clique com o botao direito no canal e use **Copiar ID do canal**;
- clique com o botao direito em cada usuario autorizado e use
  **Copiar ID do usuario**.

Guia oficial:
[Where can I find IDs?](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID).

## Configurar o `.env`

Comece com o recurso remoto ativo, mas a GUI ainda inativa:

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=true
DISCORD_QUESTION_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=token-secreto-do-bot
DISCORD_QUESTION_CHANNEL_ID=123456789012345678
DISCORD_ALLOWED_USER_IDS=111111111111111111
PRESENCE_QUESTION_POLL_INTERVAL_SECONDS=5
PRESENCE_QUESTION_TIMEOUT_SECONDS=1800

PRESENCE_GUI_ANSWER_ENABLED=false
PRESENCE_CODEX_GUI_WINDOW_TITLE=
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS=120
```

Para autorizar mais de um usuario:

```env
DISCORD_ALLOWED_USER_IDS=111111111111111111,222222222222222222
```

Nomes de usuario nao sao aceitos. IDs sao estaveis e evitam confusao por
renomeacao.

## Teste 1: Discord sem Controlar a GUI

Mantenha:

```env
PRESENCE_GUI_ANSWER_ENABLED=false
```

Publique:

```bash
ai-presence ask-user \
  --worker notebook-josue:codex \
  --question "Qual opcao devo usar: A ou B?"
```

No Discord, use **Responder** na mensagem da pergunta. Enquanto houver pergunta
pendente, uma mensagem solta de usuario autorizado e rejeitada e recebe uma
orientacao no proprio canal. Mensagens de outros usuarios continuam ignoradas.

Consulte uma vez:

```bash
ai-presence observe-replies --once
ai-presence questions
```

O estado esperado e `answered`. Nesta fase nenhum mouse, teclado ou Enter e
executado.

### Orientacao automatica para resposta invalida

Cada mensagem nova de usuario autorizado gera no maximo uma tentativa de
orientacao quando:

- nao foi enviada com **Responder**;
- referencia uma mensagem que nao corresponde a pergunta ainda pendente; ou
- o Discord entrega `content` vazio.

O aviso menciona somente o autor autorizado, informa quantas perguntas ainda
estao dentro do prazo e ensina a selecionar **Pergunta do AI-worker** e usar
**Responder**. Para texto vazio, tambem solicita a verificacao de **Message
Content Intent** em **Developer Portal > Applications > aplicativo > Bot >
Privileged Gateway Intents**.

O observer exibe `orientadas=N` e `falhas_orientacao=N`. O cursor avanca mesmo
quando o webhook do aviso falha, pois um timeout pode ocorrer depois de o
Discord ter aceitado a mensagem; repetir automaticamente poderia duplicar o
aviso.

Nenhuma dessas mensagens invalidas e persistida como resposta ou enviada a
GUI. Bots, webhooks, usuarios fora da allowlist e mensagens recebidas sem
pergunta pendente permanecem silenciosos.

## Identificar a Janela do Codex no Linux

Liste janelas candidatas sem mover o mouse:

```bash
xdotool search --onlyvisible --name 'Codex'
```

Para um ID retornado:

```bash
xdotool getwindowname ID_DA_JANELA
```

Defina uma expressao que encontre exatamente uma janela:

```env
PRESENCE_CODEX_GUI_WINDOW_TITLE=Codex
```

Se nenhuma janela ou mais de uma janela corresponder, `ask-user` falha antes de
publicar. Tambem e possivel passar um ID explicitamente:

```bash
ai-presence ask-user \
  --worker notebook-josue:codex \
  --window-id 12345678 \
  --question "Posso prosseguir?"
```

Mesmo com ID explicito, o titulo precisa corresponder ao padrao.

No Windows PowerShell, liste os titulos e identificadores de janelas principais:

```powershell
Get-Process | Where-Object MainWindowTitle | Select-Object Id, MainWindowHandle, MainWindowTitle
```

Use `MainWindowHandle` como `--window-id`. O identificador e o titulo sao
revalidados antes da entrega em ambas as plataformas.

## Teste 2: Entrega na GUI

Ative somente depois do Teste 1:

```env
PRESENCE_GUI_ANSWER_ENABLED=true
PRESENCE_CODEX_GUI_WINDOW_TITLE=Codex
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
```

Publique uma nova pergunta. A pergunta anterior, criada com GUI inativa, nao
possui alvo e nao deve ser usada para esse teste.

Quando a resposta autorizada chegar, o programa:

1. revalida o mesmo ID de janela;
2. exige o mesmo titulo capturado;
3. ativa a janela;
4. clica em 50% da largura e 90% da altura;
5. no Linux, salva o clipboard, cola a resposta e restaura o conteudo;
6. no Windows, digita texto Unicode por `SendInput`, sem usar o clipboard;
7. pressiona Enter.

O observer de respostas nao aplica o delay de continuidade. Sua latencia normal
e o intervalo de polling, por padrao ate 5 segundos, mais rede e tempo da GUI.
O antigo fluxo de `prosseguir_tarefas.py` foi integrado separadamente como
`ai-presence continue`; consulte `docs/CONTINUE-CODEX.md`.

## Executar Continuamente

Em terminal:

```bash
ai-presence observe-replies
```

Para inspecionar a definicao da plataforma sem instalar:

```bash
ai-presence --dry-run install-background-service --component reply-observer
```

No Linux, instale a unidade e depois habilite-a:

```bash
ai-presence install-background-service --component reply-observer
systemctl --user daemon-reload
systemctl --user import-environment DISPLAY XAUTHORITY XDG_RUNTIME_DIR
systemctl --user enable --now ai-presence-reply-observer.service
systemctl --user status ai-presence-reply-observer.service
journalctl --user -u ai-presence-reply-observer.service -n 100
```

No Windows PowerShell, registre e inicie a tarefa do usuario:

```powershell
ai-presence.exe install-background-service --component reply-observer
schtasks.exe /Run /TN "AI Presence Reply Observer"
schtasks.exe /Query /TN "AI Presence Reply Observer" /V /FO LIST
```

O Linux gera a unidade sem habilita-la. O Windows registra a tarefa para cada
logon interativo, mas o primeiro inicio imediato ainda e explicito.

### Falhas persistentes e HTTP 403

No Linux, a unidade do observer espera 30 segundos entre falhas e permite no
maximo tres inicios com falha em cinco minutos. Isso evita um ciclo agressivo
quando token, canal, permissoes ou rede estao incorretos. O monitor principal
nao usa esse limite.

Para `403`, confirme no canal dedicado as permissoes `View Channel`,
`Read Message History` e `Send Messages`. Teste uma leitura antes de reativar:

```bash
systemctl --user disable --now ai-presence-reply-observer.service
ai-presence observe-replies --once
systemctl --user reset-failed ai-presence-reply-observer.service
systemctl --user enable --now ai-presence-reply-observer.service
```

Nao regenere o token como primeira tentativa e nunca o publique em logs.

## Uso pelo AI-worker

Quando precisar de uma decisao humana, o AI-worker pode executar:

```bash
ai-presence ask-user \
  --worker ID_EXATO_DO_WORKER \
  --question "A pergunta objetiva ao usuario"
```

O observer recebe e entrega a resposta. O AI-worker nao deve publicar de novo
se a primeira tentativa tiver resultado incerto.

Com escopo `project`, o comando pode derivar o worker:

```bash
ai-presence ask-user \
  --scope project \
  --project "$PWD" \
  --question "Devo alterar tambem a API publica?"
```

## Estados e Auditoria

`ai-presence questions` mostra:

| Estado | Significado |
|---|---|
| `pending` | Pergunta publicada e dentro do prazo. |
| `publish_failed` | Publicacao falhou. |
| `answered` | Resposta autorizada persistida. |
| `input_emitted` | Texto, clique e Enter foram emitidos pela GUI. |
| `delivery_confirmed` | Hook posterior do mesmo worker registrou atividade. |
| `dispatch_failed` | A entrega GUI falhou ou ficou incerta. |
| `expired` | O prazo terminou antes de uma resposta valida. |

Uma falha GUI nao e reenviada automaticamente. Depois de verificar visualmente
que o texto nao foi enviado:

```bash
ai-presence dispatch-answer ID_DA_PERGUNTA
```

## Seguranca

- Mantenha o canal restrito.
- Autorize o menor numero possivel de IDs.
- Trate `DISCORD_BOT_TOKEN` e webhooks como senhas.
- Nunca publique o `.env`.
- O texto autorizado vira entrada do Codex e pode mudar o trabalho executado.
- Conta Discord comprometida dentro da allowlist equivale a controle do prompt.
- Respostas vazias e mensagens sem referencia de usuario autorizado recebem
  orientacao somente enquanto houver pergunta pendente; nao sao aceitas nem
  enviadas a GUI.
- Bots, webhooks e usuarios fora da allowlist sao ignorados sem feedback.
- O programa nao passa a resposta para shell.
- A entrega GUI fica desativada por padrao.
- `--dry-run` nao toca rede, banco ou GUI nos comandos novos.

## Limites

- Apenas Discord esta implementado para respostas nesta versao.
- Apenas texto e aceito.
- Mais de 1000 mensagens novas entre ciclos causam falha fechada e exigem
  intervencao manual; use um canal dedicado e restrito.
- A confirmacao por hook prova atividade posterior, nao interpretacao correta.
- Alteracao de titulo, fechamento da janela ou ausencia de desktop compativel causa
  `dispatch_failed`.
- O programa nao le a resposta diretamente na memoria interna desta conversa;
  ele usa o prompt visivel como fallback.

## Rollback

Desative:

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=false
PRESENCE_GUI_ANSWER_ENABLED=false
```

Depois, no Linux:

```bash
systemctl --user disable --now ai-presence-reply-observer.service
ai-presence uninstall-background-service --component reply-observer
systemctl --user daemon-reload
```

Se a unidade estiver bloqueada pelo limite de falhas, use `systemctl --user
reset-failed ai-presence-reply-observer.service` somente depois de corrigir a
causa.

No Windows PowerShell:

```powershell
ai-presence.exe uninstall-background-service --component reply-observer
```

Remova o token e o webhook do `.env` se nao forem mais usados. As tabelas novas
nao afetam os protocolos de presenca.
